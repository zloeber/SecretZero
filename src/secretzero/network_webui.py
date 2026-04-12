"""One-shot network FastAPI UI for manual secret seeding (``secretzero web``)."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import secrets
import socket
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import DictLoader, Environment, select_autoescape

from secretzero.agent_webui import _inject_static_values
from secretzero.lockfile import Lockfile
from secretzero.models import Secretfile
from secretzero.network_web_dashboard import (
    build_manifest_rows,
    build_secret_rows,
    make_sync_engine,
)

logger = logging.getLogger(__name__)

COOKIE_NAME = "sz_web_session"
COOKIE_MAX_AGE = 3600


@dataclass
class NetworkWebSessionStore:
    """Server-side auth state for the network web UI (single process)."""

    _token_digest: bytes
    bootstrap_consumed: bool = False
    sessions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_bootstrap_token(cls, token: str) -> NetworkWebSessionStore:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return cls(_token_digest=digest)

    def try_authenticate(self, offered: str) -> tuple[str, str] | None:
        """Validate bootstrap token once; create browser session + CSRF. Returns (sid, csrf) or None."""
        if self.bootstrap_consumed:
            return None
        offered_digest = hashlib.sha256(offered.encode("utf-8")).digest()
        if not secrets.compare_digest(offered_digest, self._token_digest):
            return None
        sid = secrets.token_urlsafe(24)
        csrf = secrets.token_urlsafe(32)
        self.sessions[sid] = csrf
        self.bootstrap_consumed = True
        self._token_digest = b""
        return sid, csrf

    def valid_session(self, sid: str | None) -> bool:
        return bool(sid and sid in self.sessions)

    def csrf_for(self, sid: str) -> str | None:
        return self.sessions.get(sid)

    def invalidate_session(self, sid: str) -> None:
        self.sessions.pop(sid, None)


def _pkg_templates_env() -> Environment:
    from secretzero.network_web_templates_jinja import TEMPLATES

    env = Environment(
        loader=DictLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        enable_async=False,
    )
    env.filters["uquote"] = lambda s: quote(str(s), safe="")
    return env


def pick_port_in_range(host: str, port_min: int, port_max: int) -> int:
    """Return a free TCP port in the inclusive range for the given bind host."""
    addr_family = socket.AF_INET6 if host == "::" else socket.AF_INET
    for _ in range(96):
        port = secrets.randbelow(port_max - port_min + 1) + port_min
        with socket.socket(addr_family, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in range {port_min}-{port_max} on host {host!r}")


def parse_san_entry(entry: str) -> tuple[str, Any]:
    """Return ('dns', str) or ('ip', ipaddress) for a --tls-san value."""
    entry = entry.strip()
    if not entry:
        raise ValueError("empty SAN")
    try:
        ip = ipaddress.ip_address(entry)
        return ("ip", ip)
    except ValueError:
        return ("dns", entry)


def generate_self_signed_tls_files(
    *,
    extra_sans: list[str],
    validity_days: int = 90,
) -> tuple[Path, Path, str]:
    """Write PEM cert and key to temp files; return paths and SHA-256 SPKI fingerprint (hex).

    Caller should delete the paths when done.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SecretZero"),
            x509.NameAttribute(NameOID.COMMON_NAME, "secretzero-web"),
        ]
    )
    san: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv6Address("::1")),
    ]
    for raw in extra_sans:
        kind, val = parse_san_entry(raw)
        if kind == "dns":
            san.append(x509.DNSName(val))
        else:
            san.append(x509.IPAddress(val))

    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .sign(key, hashes.SHA256())
    )

    spki = cert.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(spki).hexdigest()

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    cert_f = tempfile.NamedTemporaryFile(prefix="szweb-", suffix=".pem", delete=False)
    key_f = tempfile.NamedTemporaryFile(prefix="szweb-", suffix=".pem", delete=False)
    try:
        cert_f.write(cert_pem)
        cert_f.flush()
        key_f.write(key_pem)
        key_f.flush()
    finally:
        cert_f.close()
        key_f.close()
    Path(key_f.name).chmod(0o600)
    return Path(cert_f.name), Path(key_f.name), fingerprint


class _NetworkWebState:
    """Mutable Secretfile + lockfile for the dashboard session (single-threaded uvicorn)."""

    __slots__ = ("secretfile", "lockfile")

    def __init__(self, secretfile: Secretfile, lockfile: Lockfile) -> None:
        self.secretfile = secretfile
        self.lockfile = lockfile


def create_network_web_app(
    *,
    secretfile: Secretfile,
    lockfile: Lockfile,
    lockfile_path: Path,
    secretfile_path: Path | None,
    secretfile_content: str | None,
    dry_run: bool,
    auth: NetworkWebSessionStore,
    use_tls: bool,
    on_shutdown: Callable[[], None],
) -> FastAPI:
    """FastAPI app: bootstrap token, dashboard, per-secret sync/rotate, logout, shutdown."""
    env = _pkg_templates_env()
    state = _NetworkWebState(secretfile, lockfile)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def _cookie_kwargs() -> dict[str, Any]:
        return {
            "max_age": COOKIE_MAX_AGE,
            "httponly": True,
            "samesite": "lax",
            "secure": bool(use_tls),
            "path": "/",
        }

    def _render(name: str, **ctx: Any) -> HTMLResponse:
        tpl = env.get_template(name)
        html = tpl.render(**ctx)
        return HTMLResponse(html)

    def _secret_names() -> set[str]:
        return {s.name for s in state.secretfile.secrets}

    def _get_secret(name: str) -> Any | None:
        for s in state.secretfile.secrets:
            if s.name == name:
                return s
        return None

    def _dashboard_response(
        request: Request,
        *,
        notice: str | None = None,
        error: str | None = None,
    ) -> HTMLResponse:
        sid = request.cookies.get(COOKIE_NAME)
        csrf = auth.csrf_for(sid or "") if sid else None
        assert csrf is not None
        return _render(
            "dashboard.html",
            title="SecretZero — manifest",
            csrf_token=csrf,
            rows=build_secret_rows(state.secretfile, state.lockfile),
            manifest=build_manifest_rows(state.lockfile, secretfile_path),
            dry_run=dry_run,
            notice=notice,
            error=error,
        )

    def _save_lock() -> None:
        if not dry_run:
            state.lockfile.save(lockfile_path)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    async def _exchange_bootstrap(offered: str) -> Response:
        pair = auth.try_authenticate(offered)
        if not pair:
            msg = (
                "That access link is no longer valid. Run secretzero web again for a new token."
                if auth.bootstrap_consumed
                else "Invalid access token."
            )
            return _render(
                "login.html",
                title="SecretZero — access",
                bootstrap_consumed=auth.bootstrap_consumed,
                auth_error=msg,
            )
        sid, _csrf = pair
        resp = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        resp.set_cookie(COOKIE_NAME, sid, **_cookie_kwargs())
        return resp

    @app.get("/", response_model=None)
    async def root(
        request: Request,
        access_token: str | None = None,
    ) -> Response:
        if access_token:
            return await _exchange_bootstrap(access_token)
        sid = request.cookies.get(COOKIE_NAME)
        if auth.valid_session(sid):
            return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
        return _render(
            "login.html",
            title="SecretZero — access",
            bootstrap_consumed=auth.bootstrap_consumed,
            auth_error=None,
        )

    @app.post("/auth", response_model=None)
    async def auth_post(
        access_token: str = Form(...),
    ) -> Response:
        return await _exchange_bootstrap(access_token)

    @app.get("/form", response_model=None)
    async def legacy_form_redirect() -> RedirectResponse:
        return RedirectResponse("/dashboard", status_code=status.HTTP_301_MOVED_PERMANENTLY)

    @app.get("/dashboard", response_model=None)
    async def dashboard_get(request: Request) -> HTMLResponse | RedirectResponse:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        qn = request.query_params.get("notice")
        qe = request.query_params.get("error")
        return _dashboard_response(request, notice=qn, error=qe)

    @app.get("/secret/{secret_name}/edit", response_model=None)
    async def secret_edit(request: Request, secret_name: str) -> HTMLResponse | RedirectResponse:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        name = secret_name
        if name not in _secret_names():
            return _dashboard_response(request, error=f"Unknown secret: {name}")
        sec = _get_secret(name)
        if not sec or sec.kind != "static":
            return _dashboard_response(
                request, error=f"'{name}' is not a static secret (set value in YAML or use Rotate)."
            )
        csrf = auth.csrf_for(sid or "")
        assert csrf is not None
        qe = request.query_params.get("error")
        return _render(
            "secret_edit.html",
            title=f"Update — {name}",
            secret_name=name,
            csrf_token=csrf,
            error_message=qe,
        )

    @app.post("/secret/{secret_name}/apply", response_model=None)
    async def secret_apply(request: Request, secret_name: str) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                f"/dashboard?error={quote('Invalid CSRF token')}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        name = secret_name
        sec_apply = _get_secret(name)
        if not sec_apply or sec_apply.kind != "static":
            return RedirectResponse(
                f"/dashboard?error={quote('Invalid secret')}", status_code=status.HTTP_303_SEE_OTHER
            )
        raw = form.get("value")
        val = str(raw).strip() if raw is not None else ""
        if not val:
            return RedirectResponse(
                f"/secret/{quote(name, safe='')}/edit?error={quote('Value required')}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            state.secretfile = _inject_static_values(state.secretfile, {name: val})
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            eng.sync(dry_run=dry_run, secret_names=[name])
            _save_lock()
        except Exception as exc:
            logger.exception("Apply secret failed")
            return RedirectResponse(
                f"/dashboard?error={quote(str(exc))}", status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            f"/dashboard?notice={quote(f'Updated and synced: {name}')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/action/sync-secret", response_model=None)
    async def action_sync_secret(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                f"/dashboard?error={quote('Invalid CSRF token')}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        name = str(form.get("secret_name") or "").strip()
        if name not in _secret_names():
            return RedirectResponse(
                f"/dashboard?error={quote('Unknown secret')}", status_code=status.HTTP_303_SEE_OTHER
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            eng.sync(dry_run=dry_run, secret_names=[name])
            _save_lock()
        except Exception as exc:
            logger.exception("Sync secret failed")
            return RedirectResponse(
                f"/dashboard?error={quote(str(exc))}", status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            f"/dashboard?notice={quote(f'Synced: {name}')}", status_code=status.HTTP_303_SEE_OTHER
        )

    @app.post("/action/rotate-secret", response_model=None)
    async def action_rotate_secret(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                f"/dashboard?error={quote('Invalid CSRF token')}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        name = str(form.get("secret_name") or "").strip()
        if name not in _secret_names():
            return RedirectResponse(
                f"/dashboard?error={quote('Unknown secret')}", status_code=status.HTTP_303_SEE_OTHER
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            eng.sync(dry_run=dry_run, force_rotation=True, secret_names=[name])
            _save_lock()
        except Exception as exc:
            logger.exception("Rotate secret failed")
            return RedirectResponse(
                f"/dashboard?error={quote(str(exc))}", status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            f"/dashboard?notice={quote(f'Rotated: {name}')}", status_code=status.HTTP_303_SEE_OTHER
        )

    @app.post("/action/sync-all", response_model=None)
    async def action_sync_all(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                f"/dashboard?error={quote('Invalid CSRF token')}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            eng.sync(dry_run=dry_run)
            _save_lock()
        except Exception as exc:
            logger.exception("Sync all failed")
            return RedirectResponse(
                f"/dashboard?error={quote(str(exc))}", status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            "/dashboard?notice=" + quote("Full sync completed."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/logout", response_model=None)
    async def logout(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        form = dict(await request.form())
        if sid and auth.csrf_for(sid) and form.get("csrf_token") == auth.csrf_for(sid):
            auth.invalidate_session(sid)
        resp = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        resp.delete_cookie(COOKIE_NAME, path="/")
        return resp

    @app.post("/shutdown", response_model=None)
    async def shutdown(request: Request) -> HTMLResponse | RedirectResponse:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return _dashboard_response(request, error="Invalid CSRF token")
        _save_lock()
        if sid:
            auth.invalidate_session(sid)
        out = _render("stopped.html", title="SecretZero — stopped", dry_run=dry_run)
        out.delete_cookie(COOKIE_NAME, path="/")
        threading.Timer(0.25, on_shutdown).start()
        return out

    return app


def run_network_blocking_web_session(
    *,
    secretfile: Secretfile,
    lockfile: Lockfile,
    lockfile_path: Path,
    secretfile_path: Path | None,
    secretfile_content: str | None,
    dry_run: bool,
    host: str,
    port: int | None,
    port_min: int,
    port_max: int,
    bootstrap_token: str,
    tls_certfile: Path | None,
    tls_keyfile: Path | None,
    tls_self_signed: bool,
    tls_extra_sans: list[str],
    timeout: float,
    on_ready: Callable[[str, int, str | None], None] | None = None,
) -> tuple[str, int, str | None]:
    """Run uvicorn until shutdown or timeout. Returns (base_url, port, spki_fingerprint_or_none).

    ``on_ready`` is invoked after the server is listening (use to print URL + token while the UI is up).
    """
    server_box: list[uvicorn.Server | None] = [None]
    done = threading.Event()

    def shutdown_server() -> None:
        srv = server_box[0]
        if srv is not None:
            srv.should_exit = True
        done.set()

    chosen = port if port is not None else pick_port_in_range(host, port_min, port_max)

    ssl_cert: str | None = str(tls_certfile) if tls_certfile else None
    ssl_key: str | None = str(tls_keyfile) if tls_keyfile else None
    fingerprint: str | None = None
    cleanup_paths: list[Path] = []

    if tls_self_signed:
        cpath, kpath, fingerprint = generate_self_signed_tls_files(extra_sans=tls_extra_sans)
        ssl_cert, ssl_key = str(cpath), str(kpath)
        cleanup_paths.extend([cpath, kpath])

    use_tls = bool(ssl_cert and ssl_key)
    auth = NetworkWebSessionStore.from_bootstrap_token(bootstrap_token)
    app = create_network_web_app(
        secretfile=secretfile,
        lockfile=lockfile,
        lockfile_path=lockfile_path,
        secretfile_path=secretfile_path,
        secretfile_content=secretfile_content,
        dry_run=dry_run,
        auth=auth,
        use_tls=use_tls,
        on_shutdown=shutdown_server,
    )

    config = uvicorn.Config(
        app,
        host=host,
        port=chosen,
        log_level="warning",
        ssl_certfile=ssl_cert,
        ssl_keyfile=ssl_key,
    )
    server = uvicorn.Server(config)
    server_box[0] = server

    def _run() -> None:
        try:
            asyncio.run(server.serve())
        except Exception:
            logger.exception("Network web server failed")
            done.set()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.2)

    scheme = "https" if ssl_cert else "http"
    base = f"{scheme}://{host}:{chosen}/"
    if host == "0.0.0.0":
        base = f"{scheme}://127.0.0.1:{chosen}/"

    if on_ready is not None:
        on_ready(base, chosen, fingerprint)

    try:
        if not done.wait(timeout=timeout):
            server.should_exit = True
            raise TimeoutError("Timed out waiting for web UI shutdown or timeout")
    finally:
        server.should_exit = True
        thread.join(timeout=15.0)
        for p in cleanup_paths:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove temp TLS file %s", p)

    return base, chosen, fingerprint
