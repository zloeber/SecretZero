"""One-shot network FastAPI UI for manual secret seeding (``secretzero web``)."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
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
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import DictLoader, Environment, select_autoescape

from secretzero.agent import secret_supports_automatic_generation
from secretzero.agent_webui import (
    _inject_static_values,
    build_pending_static_values_from_form,
    normalize_scalar_network_form,
    static_secret_edit_template_vars,
)
from secretzero.config import ConfigLoader
from secretzero.environment_resolution import apply_target_profile, resolve_environment_context
from secretzero.generators.traits import secret_prompts_like_static
from secretzero.lockfile import Lockfile
from secretzero.lockfile_import import run_lockfile_import
from secretzero.models import Secretfile
from secretzero.network_web_actions import run_validate_manifest
from secretzero.network_web_dashboard import (
    build_agent_instructions_payload,
    build_manifest_rows,
    build_secret_rows,
    make_sync_engine,
    target_groups_show_only_unsynced_lanes,
)
from secretzero.sync import SyncEngine

logger = logging.getLogger(__name__)

COOKIE_NAME = "sz_web_session"

_MAX_DEBUG_BLOCKS = 32

_DASHBOARD_TABS = ("dashboard", "secretfile", "interpolated", "graph")


def format_sync_results_for_debug(results: dict[str, Any]) -> str:
    """Format sync engine output for the web debug panel. Must not include secret values."""

    def _simplify_detail(d: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": d.get("name"),
            "kind": d.get("kind"),
            "generated": d.get("generated"),
            "stored": d.get("stored"),
            "skipped": d.get("skipped"),
            "reason": d.get("reason"),
        }
        errs = d.get("errors")
        if errs:
            out["errors"] = errs
        targets: list[dict[str, Any]] = []
        for t in d.get("targets") or []:
            if not isinstance(t, dict):
                continue
            targets.append(
                {
                    "provider": t.get("provider"),
                    "kind": t.get("kind"),
                    "status": t.get("status"),
                    "message": t.get("message"),
                }
            )
        if targets:
            out["targets"] = targets
        return {k: v for k, v in out.items() if v is not None}

    payload = {
        "secrets_stored": results.get("secrets_stored"),
        "secrets_skipped": results.get("secrets_skipped"),
        "secrets_processed": results.get("secrets_processed"),
        "errors": results.get("errors"),
        "details": [
            _simplify_detail(x) for x in results.get("details") or [] if isinstance(x, dict)
        ],
    }
    return json.dumps(payload, indent=2)


def _flatten_sync_errors(results: dict[str, Any]) -> list[str]:
    """Collect human-readable sync errors (no secret values)."""
    out: list[str] = []
    for e in results.get("errors") or []:
        if isinstance(e, str) and e.strip():
            out.append(e.strip())
    for d in results.get("details") or []:
        if not isinstance(d, dict):
            continue
        for e in d.get("errors") or []:
            if isinstance(e, str) and e.strip():
                out.append(e.strip())
    return out


def _append_debug_block(state: Any, title: str, body: str) -> None:
    from datetime import UTC, datetime

    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    block = f"=== {title} @ {ts} ===\n{body.strip()}"
    state.debug_blocks.append(block)
    while len(state.debug_blocks) > _MAX_DEBUG_BLOCKS:
        state.debug_blocks.pop(0)


def dashboard_redirect_url(
    *,
    notice: str | None = None,
    error: str | None = None,
    list_filter: str = "all",
    tab: str = "dashboard",
    graph_view: str = "mermaid",
    graph_type: str = "flow",
    environment: str | None = None,
) -> str:
    """Build /dashboard URL with optional notice, error, and list filter."""
    lf = list_filter if list_filter in ("all", "unsynced") else "all"
    tab_safe = tab if tab in _DASHBOARD_TABS else "dashboard"
    graph_view_safe = graph_view if graph_view in ("mermaid", "json") else "mermaid"
    graph_type_safe = (
        graph_type if graph_type in ("flow", "detailed", "architecture", "destination") else "flow"
    )
    parts: list[str] = [
        f"filter={quote(lf)}",
        f"tab={quote(tab_safe)}",
        f"graph_view={quote(graph_view_safe)}",
        f"graph_type={quote(graph_type_safe)}",
    ]
    if environment:
        parts.append(f"environment={quote(environment)}")
    if notice is not None:
        parts.insert(0, f"notice={quote(notice)}")
    if error is not None:
        parts.insert(0, f"error={quote(error)}")
    return "/dashboard?" + "&".join(parts)


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

    __slots__ = (
        "secretfile",
        "lockfile",
        "lockfile_path",
        "selected_environment",
        "resolved_var_files",
        "resolved_target_profile",
        "debug_blocks",
    )

    def __init__(
        self,
        secretfile: Secretfile,
        lockfile: Lockfile,
        *,
        lockfile_path: Path,
        selected_environment: str | None,
        resolved_var_files: list[Path],
        resolved_target_profile: str | None,
    ) -> None:
        self.secretfile = secretfile
        self.lockfile = lockfile
        self.lockfile_path = lockfile_path
        self.selected_environment = selected_environment
        self.resolved_var_files = resolved_var_files
        self.resolved_target_profile = resolved_target_profile
        self.debug_blocks: list[str] = []


def _renderable_mermaid(raw: str) -> str:
    """Return Mermaid source without Markdown fences for browser rendering."""
    lines = [ln.rstrip("\n") for ln in raw.splitlines()]
    if lines and lines[0].strip().startswith("```mermaid"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _json_graph_from_secretfile(secretfile: Secretfile) -> str:
    """Build machine-readable graph JSON from in-memory Secretfile."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    for secret in secretfile.secrets:
        nodes.append(
            {
                "id": secret.name,
                "type": "secret",
                "kind": secret.kind,
                "one_time": secret.one_time,
                "rotation_period": secret.rotation_period,
            }
        )
        edges.append({"from": secret.kind, "to": secret.name, "label": "generates"})
        for target in secret.targets:
            target_id = f"{target.provider}/{target.kind}"
            if not any(n["id"] == target_id for n in nodes):
                nodes.append(
                    {
                        "id": target_id,
                        "type": "target",
                        "provider": target.provider,
                        "kind": str(target.kind),
                    }
                )
            edges.append({"from": secret.name, "to": target_id, "label": "stored_in"})
    return json.dumps({"nodes": nodes, "edges": edges}, indent=2)


def create_network_web_app(
    *,
    secretfile: Secretfile,
    lockfile: Lockfile,
    lockfile_path: Path,
    secretfile_path: Path | None,
    secretfile_content: str | None,
    var_file_paths: list[Path] | None,
    runtime_var_file_paths: list[Path] | None,
    runtime_lockfile: str | None,
    environment: str | None,
    dry_run: bool,
    debug: bool,
    auth: NetworkWebSessionStore,
    use_tls: bool,
    on_shutdown: Callable[[], None],
) -> FastAPI:
    """FastAPI app: bootstrap token, dashboard, per-secret sync/rotate, logout, shutdown."""
    env = _pkg_templates_env()
    state = _NetworkWebState(
        secretfile,
        lockfile,
        lockfile_path=lockfile_path,
        selected_environment=environment,
        resolved_var_files=var_file_paths or [],
        resolved_target_profile=None,
    )

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
        list_filter: str = "all",
        tab: str = "dashboard",
        graph_view: str = "mermaid",
        graph_type: str = "flow",
    ) -> HTMLResponse:
        sid = request.cookies.get(COOKIE_NAME)
        csrf = auth.csrf_for(sid or "") if sid else None
        assert csrf is not None
        current_tab = tab if tab in _DASHBOARD_TABS else "dashboard"
        current_graph_view = graph_view if graph_view in ("mermaid", "json") else "mermaid"
        current_graph_type = (
            graph_type
            if graph_type in ("flow", "detailed", "architecture", "destination")
            else "flow"
        )
        all_rows = build_secret_rows(state.secretfile, state.lockfile)
        row_total = len(all_rows)
        unsynced_count = sum(1 for r in all_rows if r.get("is_unsynced"))
        if list_filter == "unsynced":
            rows = []
            for r in all_rows:
                if not r.get("is_unsynced"):
                    continue
                r2 = dict(r)
                if r2.get("has_targets") and r2.get("target_groups"):
                    r2["target_groups"] = target_groups_show_only_unsynced_lanes(
                        r2["target_groups"]
                    )
                rows.append(r2)
        else:
            rows = all_rows
        tools_available = bool(secretfile_path and secretfile_path.exists())
        debug_log_text = "\n\n".join(state.debug_blocks) if debug else ""
        secretfile_text = secretfile_content
        if secretfile_text is None and secretfile_path and secretfile_path.exists():
            try:
                secretfile_text = secretfile_path.read_text()
            except OSError:
                secretfile_text = "Could not read Secretfile from disk."
        if secretfile_text is None:
            secretfile_text = "Secretfile content is not available in this session."
        mermaid_source = ""
        if secretfile_path and secretfile_path.exists():
            try:
                from secretzero.graph import generate_graph

                mermaid_raw = generate_graph(
                    secretfile_path=secretfile_path,
                    graph_type=current_graph_type,  # type: ignore[arg-type]
                    output_format="mermaid",
                )
                mermaid_source = _renderable_mermaid(mermaid_raw)
            except Exception:
                logger.exception("Graph generation failed for dashboard")
                mermaid_source = "flowchart LR\n    A[Graph generation failed]"
        graph_json = _json_graph_from_secretfile(state.secretfile)
        interpolated_manifest_yaml = yaml.safe_dump(
            state.secretfile.model_dump(mode="json", exclude_none=True),
            default_flow_style=False,
            sort_keys=False,
        )
        return _render(
            "dashboard.html",
            title="SecretZero — manifest",
            csrf_token=csrf,
            rows=rows,
            row_total=row_total,
            unsynced_count=unsynced_count,
            list_filter=list_filter,
            environment_profiles=(
                sorted(state.secretfile.environments.profiles.keys())
                if state.secretfile.environments
                else []
            ),
            selected_environment=state.selected_environment or "",
            tools_available=tools_available,
            manifest=build_manifest_rows(
                state.lockfile,
                secretfile_path,
                state.secretfile,
                selected_environment=state.selected_environment,
                resolved_var_files=state.resolved_var_files,
                resolved_target_profile=state.resolved_target_profile,
            ),
            dry_run=dry_run,
            debug=debug,
            debug_log_text=debug_log_text,
            current_tab=current_tab,
            graph_view=current_graph_view,
            graph_type=current_graph_type,
            secretfile_text=secretfile_text,
            interpolated_manifest_yaml=interpolated_manifest_yaml,
            mermaid_source=mermaid_source,
            graph_json=graph_json,
            notice=notice,
            error=error,
        )

    def _save_lock() -> None:
        if not dry_run:
            state.lockfile.save(state.lockfile_path)

    def _filter_param(request: Request) -> str:
        raw = request.query_params.get("filter", "all")
        return raw if raw in ("all", "unsynced") else "all"

    def _tab_param(request: Request) -> str:
        raw = request.query_params.get("tab", "dashboard")
        return raw if raw in _DASHBOARD_TABS else "dashboard"

    def _graph_view_param(request: Request) -> str:
        raw = request.query_params.get("graph_view", "mermaid")
        return raw if raw in ("mermaid", "json") else "mermaid"

    def _graph_type_param(request: Request) -> str:
        raw = request.query_params.get("graph_type", "flow")
        return raw if raw in ("flow", "detailed", "architecture", "destination") else "flow"

    def _env_param(request: Request) -> str | None:
        raw = request.query_params.get("environment")
        if raw is None:
            return state.selected_environment
        val = raw.strip()
        return val or state.selected_environment

    def _reload_environment(selected_env: str | None) -> None:
        if not secretfile_path or not secretfile_path.exists():
            return
        loader = ConfigLoader()
        base_secretfile = loader.load_file(secretfile_path)
        env_ctx = resolve_environment_context(
            secretfile=base_secretfile,
            secretfile_path=secretfile_path,
            environment=selected_env,
            runtime_var_files=runtime_var_file_paths or [],
            runtime_lockfile=runtime_lockfile,
        )
        next_secretfile = loader.load_file(
            secretfile_path, var_files=env_ctx.resolved_var_files or None
        )
        next_secretfile = apply_target_profile(next_secretfile, env_ctx.resolved_target_profile)
        state.secretfile = next_secretfile
        state.lockfile_path = env_ctx.resolved_lockfile
        state.lockfile = Lockfile.load(env_ctx.resolved_lockfile)
        state.selected_environment = env_ctx.selected_environment
        state.resolved_var_files = env_ctx.resolved_var_files
        state.resolved_target_profile = env_ctx.resolved_target_profile

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
        req_env = _env_param(request)
        if req_env != state.selected_environment:
            try:
                _reload_environment(req_env)
            except Exception as exc:
                return _dashboard_response(
                    request,
                    error=f"Environment switch failed: {exc}",
                    list_filter=_filter_param(request),
                    tab=_tab_param(request),
                    graph_view=_graph_view_param(request),
                    graph_type=_graph_type_param(request),
                )
        qn = request.query_params.get("notice")
        qe = request.query_params.get("error")
        return _dashboard_response(
            request,
            notice=qn,
            error=qe,
            list_filter=_filter_param(request),
            tab=_tab_param(request),
            graph_view=_graph_view_param(request),
            graph_type=_graph_type_param(request),
        )

    @app.get("/secret/{secret_name}/edit", response_model=None)
    async def secret_edit(request: Request, secret_name: str) -> HTMLResponse | RedirectResponse:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        name = secret_name
        if name not in _secret_names():
            return _dashboard_response(
                request,
                error=f"Unknown secret: {name}",
                list_filter=_filter_param(request),
            )
        sec = _get_secret(name)
        if not sec or not secret_prompts_like_static(sec):
            return _dashboard_response(
                request,
                error=f"'{name}' is not a static-like secret (set value in YAML or use Rotate).",
                list_filter=_filter_param(request),
            )
        csrf = auth.csrf_for(sid or "")
        assert csrf is not None
        qe = request.query_params.get("error")
        edit_lf = request.query_params.get("filter", "all")
        list_filter = edit_lf if edit_lf in ("all", "unsynced") else "all"
        assert sec is not None
        agent_instructions = build_agent_instructions_payload(state.secretfile, sec)
        edit_ctx = static_secret_edit_template_vars(sec, secretfile_path, state.lockfile)
        return _render(
            "secret_edit.html",
            title=f"Update — {name}",
            secret_name=name,
            csrf_token=csrf,
            error_message=qe,
            agent_instructions=agent_instructions,
            list_filter=list_filter,
            **edit_ctx,
        )

    @app.post("/secret/{secret_name}/apply", response_model=None)
    async def secret_apply(request: Request, secret_name: str) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        lf = str(form.get("list_filter") or "all")
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid CSRF token", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        name = secret_name
        sec_apply = _get_secret(name)
        if not sec_apply or not secret_prompts_like_static(sec_apply):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid secret", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        merged_form = normalize_scalar_network_form(name, form)
        parsed, perr = build_pending_static_values_from_form(
            [name],
            state.secretfile,
            merged_form,
        )
        if perr or not parsed:
            return RedirectResponse(
                f"/secret/{quote(name, safe='')}/edit?error={quote(perr or 'Value required')}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        val = parsed[name]
        try:
            state.secretfile = _inject_static_values(state.secretfile, {name: val})
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            # force_rotation: lockfile may already list all targets as synced; a new static value
            # must still be written to targets (otherwise sync skips with "All targets already synced").
            results = eng.sync(dry_run=dry_run, secret_names=[name], force_rotation=True)
            if debug:
                _append_debug_block(
                    state,
                    f"Apply static: {name}",
                    format_sync_results_for_debug(results),
                )
            _save_lock()
        except Exception as exc:
            logger.exception("Apply secret failed")
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        errs = _flatten_sync_errors(results)
        if errs:
            return RedirectResponse(
                dashboard_redirect_url(error=errs[0][:1200], list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        for d in results.get("details") or []:
            if isinstance(d, dict) and d.get("skipped") and (d.get("reason") or ""):
                r = str(d["reason"])
                return RedirectResponse(
                    dashboard_redirect_url(
                        notice=f"Value saved for {name} but sync skipped: {r}"[:1200],
                        list_filter=lf,
                    ),
                    status_code=status.HTTP_303_SEE_OTHER,
                )
        return RedirectResponse(
            dashboard_redirect_url(
                notice=f"Updated and synced: {name}",
                list_filter=lf,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/action/sync-secret", response_model=None)
    async def action_sync_secret(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        lf = str(form.get("list_filter") or "all")
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid CSRF token", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        name = str(form.get("secret_name") or "").strip()
        if name not in _secret_names():
            return RedirectResponse(
                dashboard_redirect_url(error="Unknown secret", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            results = eng.sync(dry_run=dry_run, secret_names=[name])
            if debug:
                _append_debug_block(
                    state,
                    f"Sync secret: {name}",
                    format_sync_results_for_debug(results),
                )
            _save_lock()
        except Exception as exc:
            logger.exception("Sync secret failed")
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        errs = _flatten_sync_errors(results)
        if errs:
            return RedirectResponse(
                dashboard_redirect_url(error=errs[0][:1200], list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            dashboard_redirect_url(notice=f"Synced: {name}", list_filter=lf),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/action/force-sync-target", response_model=None)
    async def action_force_sync_target(request: Request) -> Response:
        """Re-push the current secret value to one target (multi-target workflows)."""
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        lf = str(form.get("list_filter") or "all")
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid CSRF token", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        name = str(form.get("secret_name") or "").strip()
        tid = str(form.get("target_id") or "").strip()
        if name not in _secret_names() or not tid:
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid request", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        sec = _get_secret(name)
        if not sec or not sec.targets:
            return RedirectResponse(
                dashboard_redirect_url(error="Secret has no targets", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        allowed = {SyncEngine._build_target_id(t) for t in sec.targets}
        if tid not in allowed:
            return RedirectResponse(
                dashboard_redirect_url(error="Unknown target for this secret", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            results = eng.sync(
                dry_run=dry_run,
                secret_names=[name],
                force_targets={name: frozenset([tid])},
            )
            if debug:
                _append_debug_block(
                    state,
                    f"Force target {tid}: {name}",
                    format_sync_results_for_debug(results),
                )
            _save_lock()
        except Exception as exc:
            logger.exception("Force sync target failed")
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        errs = _flatten_sync_errors(results)
        if errs:
            return RedirectResponse(
                dashboard_redirect_url(error=errs[0][:1200], list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            dashboard_redirect_url(
                notice=f"Re-synced to target: {name} ({tid})",
                list_filter=lf,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/action/rotate-secret", response_model=None)
    async def action_rotate_secret(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        lf = str(form.get("list_filter") or "all")
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid CSRF token", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        name = str(form.get("secret_name") or "").strip()
        if name not in _secret_names():
            return RedirectResponse(
                dashboard_redirect_url(error="Unknown secret", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        sec_rot = _get_secret(name)
        if sec_rot is not None and secret_prompts_like_static(sec_rot):
            return RedirectResponse(
                f"/secret/{quote(name, safe='')}/edit?filter={quote(lf)}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        if sec_rot is None or not secret_supports_automatic_generation(sec_rot):
            return RedirectResponse(
                dashboard_redirect_url(
                    error="Rotate is only available for secrets that can be generated automatically.",
                    list_filter=lf,
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            results = eng.sync(dry_run=dry_run, force_rotation=True, secret_names=[name])
            if debug:
                _append_debug_block(
                    state,
                    f"Rotate: {name}",
                    format_sync_results_for_debug(results),
                )
            _save_lock()
        except Exception as exc:
            logger.exception("Rotate secret failed")
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        errs = _flatten_sync_errors(results)
        if errs:
            return RedirectResponse(
                dashboard_redirect_url(error=errs[0][:1200], list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            dashboard_redirect_url(notice=f"Rotated: {name}", list_filter=lf),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/action/sync-all", response_model=None)
    async def action_sync_all(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        lf = str(form.get("list_filter") or "all")
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid CSRF token", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            results = eng.sync(dry_run=dry_run)
            if debug:
                _append_debug_block(state, "Sync all", format_sync_results_for_debug(results))
            _save_lock()
        except Exception as exc:
            logger.exception("Sync all failed")
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        errs = _flatten_sync_errors(results)
        if errs:
            return RedirectResponse(
                dashboard_redirect_url(error=errs[0][:1200], list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            dashboard_redirect_url(notice="Full sync completed.", list_filter=lf),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    def _secretfile_text_for_import() -> tuple[Path, str]:
        if not secretfile_path or not secretfile_path.exists():
            raise ValueError("Secretfile path is not available")
        text = secretfile_content
        if not text:
            text = secretfile_path.read_text()
        return secretfile_path, text

    def _flatten_import_errors(summary: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for d in summary.get("details") or []:
            if not isinstance(d, dict):
                continue
            if d.get("status") == "error":
                nm = d.get("secret") or "?"
                out.append(f"{nm}: {d.get('detail', 'error')}")
            for f in d.get("fields") or []:
                if isinstance(f, dict) and f.get("status") == "error":
                    out.append(f"{d.get('secret')}.{f.get('field')}: {f.get('detail')}")
        return [x for x in out if x]

    def _import_success_notice(summary: dict[str, Any], *, scope: str) -> str:
        r = summary.get("refresh") or {}
        label = "Refresh (all)" if scope == "all" else f"Refresh ({scope})"
        bits = [
            f"{label}: imported={summary.get('imported', 0)}, updated={summary.get('updated', 0)}",
            f"unchanged={summary.get('unchanged', 0)}, skipped={summary.get('skipped', 0)}",
        ]
        if summary.get("would_apply"):
            bits.append(f"would_apply={summary['would_apply']}")
        if r.get("mismatch_targets"):
            bits.append(f"stale_targets_pruned={r['mismatch_targets']}")
        if summary.get("dry_run"):
            bits.append("dry_run")
        return ", ".join(bits)[:1180]

    @app.post("/action/import-all", response_model=None)
    async def action_import_all(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        lf = str(form.get("list_filter") or "all")
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid CSRF token", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            spath, scontent = _secretfile_text_for_import()
        except ValueError as exc:
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=spath,
                secretfile_content=scontent,
            )
            summary = run_lockfile_import(
                eng,
                secretfile=state.secretfile,
                secretfile_path=spath,
                secretfile_content=scontent,
                secret_names=None,
                active_var_files=state.resolved_var_files,
                dry_run=dry_run,
            )
            if debug:
                slim = {k: v for k, v in summary.items() if k != "details"}
                _append_debug_block(state, "Import all", json.dumps(slim, indent=2))
            _save_lock()
        except Exception as exc:
            logger.exception("Import all failed")
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        errs = _flatten_import_errors(summary)
        if errs:
            return RedirectResponse(
                dashboard_redirect_url(error=errs[0][:1200], list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            dashboard_redirect_url(
                notice=_import_success_notice(summary, scope="all"),
                list_filter=lf,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/action/import-secret", response_model=None)
    async def action_import_secret(request: Request) -> Response:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        lf = str(form.get("list_filter") or "all")
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid CSRF token", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        name = str(form.get("secret_name") or "").strip()
        if name not in _secret_names():
            return RedirectResponse(
                dashboard_redirect_url(error="Unknown secret", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            spath, scontent = _secretfile_text_for_import()
        except ValueError as exc:
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            eng = make_sync_engine(
                state.secretfile,
                state.lockfile,
                secretfile_path=spath,
                secretfile_content=scontent,
            )
            summary = run_lockfile_import(
                eng,
                secretfile=state.secretfile,
                secretfile_path=spath,
                secretfile_content=scontent,
                secret_names=[name],
                active_var_files=state.resolved_var_files,
                dry_run=dry_run,
            )
            if debug:
                slim = {k: v for k, v in summary.items() if k != "details"}
                _append_debug_block(state, f"Import: {name}", json.dumps(slim, indent=2))
            _save_lock()
        except Exception as exc:
            logger.exception("Import secret failed")
            return RedirectResponse(
                dashboard_redirect_url(error=str(exc), list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        errs = _flatten_import_errors(summary)
        if errs:
            return RedirectResponse(
                dashboard_redirect_url(error=errs[0][:1200], list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            dashboard_redirect_url(
                notice=_import_success_notice(summary, scope=name),
                list_filter=lf,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.post("/action/validate-manifest", response_model=None)
    async def action_validate_manifest(request: Request) -> HTMLResponse | RedirectResponse:
        sid = request.cookies.get(COOKIE_NAME)
        if not auth.valid_session(sid):
            return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
        form = dict(await request.form())
        lf = str(form.get("list_filter") or "all")
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return RedirectResponse(
                dashboard_redirect_url(error="Invalid CSRF token", list_filter=lf),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        if not secretfile_path or not secretfile_path.exists():
            return RedirectResponse(
                dashboard_redirect_url(
                    error="Validate requires the Secretfile path used to start this server.",
                    list_filter=lf,
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        try:
            body = run_validate_manifest(secretfile_path, var_file_paths)
        except Exception as exc:
            logger.exception("Validate manifest failed")
            body = f"Validate failed: {exc}"
        back = dashboard_redirect_url(list_filter=lf)
        return _render(
            "tool_result.html",
            title="SecretZero — validate manifest",
            tool_body=body,
            back_href=back,
            back_label="Back to manifest",
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
        lf = str(form.get("list_filter") or "all")
        if lf not in ("all", "unsynced"):
            lf = "all"
        if not auth.csrf_for(sid or "") or form.get("csrf_token") != auth.csrf_for(sid or ""):
            return _dashboard_response(
                request,
                error="Invalid CSRF token",
                list_filter=lf,
            )
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
    var_file_paths: list[Path] | None = None,
    runtime_var_file_paths: list[Path] | None = None,
    runtime_lockfile: str | None = None,
    environment: str | None = None,
    dry_run: bool,
    debug: bool = False,
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
        var_file_paths=var_file_paths,
        runtime_var_file_paths=runtime_var_file_paths,
        runtime_lockfile=runtime_lockfile,
        environment=environment,
        dry_run=dry_run,
        debug=debug,
        auth=auth,
        use_tls=use_tls,
        on_shutdown=shutdown_server,
    )

    # Uvicorn defaults timeout_graceful_shutdown to None; wait_for(..., None) then waits until
    # every connection closes. Browsers often keep HTTPS connections alive, so shutdown from
    # the UI would never finish. A bounded graceful period cancels stuck tasks and exits.
    config = uvicorn.Config(
        app,
        host=host,
        port=chosen,
        log_level="warning",
        ssl_certfile=ssl_cert,
        ssl_keyfile=ssl_key,
        timeout_graceful_shutdown=8,
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
    if host == "0.0.0.0":  # nosec B104
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
