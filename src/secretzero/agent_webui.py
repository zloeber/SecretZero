"""Temporary localhost FastAPI form for Vector 2 (secure human input, not agent context)."""

from __future__ import annotations

import asyncio
import logging
import secrets
import socket
import threading
import uuid
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from secretzero.agent import AgentSyncResult
from secretzero.lockfile import Lockfile
from secretzero.models import Secretfile

logger = logging.getLogger(__name__)


class WebAgentSession(BaseModel):
    """Server-side session for API Vector 2 (no secret values stored here until POST)."""

    session_id: str
    secret_names: list[str]
    done: bool = False
    error: str | None = None
    result_payload: dict[str, Any] | None = None


class WebSessionRegistry:
    """In-memory registry for /agent/sync web sessions (single-process API)."""

    def __init__(self) -> None:
        self._sessions: dict[str, WebAgentSession] = {}
        self._lock = threading.Lock()

    def create(self, secret_names: list[str]) -> WebAgentSession:
        sid = uuid.uuid4().hex
        sess = WebAgentSession(session_id=sid, secret_names=secret_names)
        with self._lock:
            self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> WebAgentSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def complete(self, session_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            s = self._sessions.get(session_id)
            if s:
                s.done = True
                s.result_payload = payload
                s.error = None

    def fail(self, session_id: str, message: str) -> None:
        with self._lock:
            s = self._sessions.get(session_id)
            if s:
                s.done = True
                s.error = message
                s.result_payload = None


web_session_registry = WebSessionRegistry()


def _pick_port(port_min: int, port_max: int) -> int:
    """Return a free TCP port in the inclusive range."""
    for _ in range(64):
        port = secrets.randbelow(port_max - port_min + 1) + port_min
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in range {port_min}-{port_max}")


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _build_form_html(secret_names: list[str], title: str = "SecretZero — manual secrets") -> str:
    rows = []
    for name in secret_names:
        safe = _escape_html(name)
        rows.append(
            f'<label for="{safe}"><strong>{safe}</strong></label>'
            f'<input id="{safe}" name="{safe}" type="password" autocomplete="off" required />'
        )
    body = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{_escape_html(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; }}
label {{ display: block; margin-top: 1rem; }}
input {{ width: 100%; padding: 0.5rem; margin-top: 0.25rem; }}
button {{ margin-top: 1.5rem; padding: 0.5rem 1rem; }}
p.note {{ color: #444; font-size: 0.9rem; }}
</style></head><body>
<h1>{_escape_html(title)}</h1>
<p class="note">Values are sent only to this local process and are not echoed to the agent or logs.</p>
<form method="post" action="/submit">
{body}
<button type="submit">Submit</button>
</form></body></html>"""


def _inject_static_values(secretfile: Secretfile, values: dict[str, str]) -> Secretfile:
    """Apply submitted values as ``static`` secret ``config.value`` entries."""
    new_secrets = []
    for sec in secretfile.secrets:
        if sec.name in values:
            cfg = {**sec.config, "value": values[sec.name]}
            new_secrets.append(sec.model_copy(update={"config": cfg}))
        else:
            new_secrets.append(sec)
    return secretfile.model_copy(update={"secrets": new_secrets})


def run_blocking_web_agent_form(
    *,
    pending_secret_names: list[str],
    secretfile: Secretfile,
    lockfile: Lockfile,
    lockfile_path: Path,
    secretfile_path: Path | None,
    secretfile_content: str | None,
    dry_run: bool,
    port_min: int,
    port_max: int,
    open_browser: bool,
) -> AgentSyncResult:
    """Start a one-shot localhost server, block until the form is submitted or timeout.

    Submitted values are merged into static ``config.value`` for listed secrets, then
    :class:`AgentSecretSynchronizer` runs again (same process, no stdout echo).
    """
    from secretzero.agent import AgentSecretSynchronizer

    if not pending_secret_names:
        synchronizer = AgentSecretSynchronizer(
            secretfile,
            lockfile,
            dry_run=dry_run,
            secretfile_path=secretfile_path,
            secretfile_content=secretfile_content,
        )
        return synchronizer.sync()

    port = _pick_port(port_min, port_max)
    done = threading.Event()
    error_box: list[str] = []
    result_holder: list[Any] = []

    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    async def form() -> str:
        return _build_form_html(pending_secret_names)

    @app.post("/submit")
    async def submit(request: Request) -> HTMLResponse:
        try:
            form_data = await request.form()
            values: dict[str, str] = {}
            for name in pending_secret_names:
                raw = form_data.get(name)
                if raw is None or str(raw).strip() == "":
                    error_box.append(f"Missing value for {name}")
                    return HTMLResponse(
                        "<html><body>Missing fields. Go back and try again.</body></html>",
                        status_code=400,
                    )
                values[str(name)] = str(raw)
            merged = _inject_static_values(secretfile, values)
            syncer = AgentSecretSynchronizer(
                merged,
                lockfile,
                dry_run=dry_run,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            result_holder.append(syncer.sync(sz_agent=False))
        except Exception as exc:
            logger.exception("Web agent form sync failed")
            error_box.append(str(exc))
        finally:
            done.set()
        return HTMLResponse(
            "<html><body><p>Submitted. You can close this window.</p></body></html>"
        )

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    def _run_server() -> None:
        try:
            asyncio.run(server.serve())
        except Exception as exc:
            error_box.append(str(exc))
            done.set()

    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/"
    logger.info("Agent web UI listening on %s", url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            logger.warning("Could not open browser; visit %s manually", url)

    # Wait for first sync result (form submission) or early failure
    if not done.wait(timeout=3600.0):
        server.should_exit = True
        raise TimeoutError("Timed out waiting for web form submission")

    server.should_exit = True
    thread.join(timeout=10.0)

    if error_box and not result_holder:
        raise RuntimeError(error_box[0])
    if result_holder:
        return result_holder[0]
    raise RuntimeError("Web form closed without result")


def create_web_app_for_session(
    *,
    session_id: str,
    pending_secret_names: list[str],
    secretfile: Secretfile,
    lockfile: Lockfile,
    lockfile_path: Path,
    secretfile_path: Path | None,
    secretfile_content: str | None,
    dry_run: bool,
    registry: WebSessionRegistry,
) -> FastAPI:
    """FastAPI sub-app used on a dedicated localhost port for one session."""
    from secretzero.agent import AgentSecretSynchronizer, build_agent_sync_json_payload

    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    async def form() -> str:
        return _build_form_html(pending_secret_names)

    @app.post("/submit")
    async def submit(request: Request) -> HTMLResponse:
        try:
            form_data = await request.form()
            values: dict[str, str] = {}
            for name in pending_secret_names:
                raw = form_data.get(name)
                if raw is None or str(raw).strip() == "":
                    registry.fail(session_id, f"Missing value for {name}")
                    return HTMLResponse(
                        "<html><body>Missing fields.</body></html>",
                        status_code=400,
                    )
                values[str(name)] = str(raw)
            merged = _inject_static_values(secretfile, values)
            syncer = AgentSecretSynchronizer(
                merged,
                lockfile,
                dry_run=dry_run,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
            )
            res = syncer.sync(sz_agent=False)
            if not dry_run:
                lockfile.save(lockfile_path)
            payload = build_agent_sync_json_payload(
                res,
                dry_run=dry_run,
                sz_agent=False,
                resolved_mode="web",
            )
            registry.complete(session_id, payload)
        except Exception as exc:
            logger.exception("Session web submit failed")
            registry.fail(session_id, str(exc))
        return HTMLResponse("<html><body><p>Submitted.</p></body></html>")

    return app


def start_web_session_server(
    *,
    session_id: str,
    pending_secret_names: list[str],
    secretfile: Secretfile,
    lockfile: Lockfile,
    lockfile_path: Path,
    secretfile_path: Path | None,
    secretfile_content: str | None,
    dry_run: bool,
    port_min: int,
    port_max: int,
    registry: WebSessionRegistry,
) -> tuple[str, int]:
    """Run a localhost server in a daemon thread; return (base_url, port)."""
    port = _pick_port(port_min, port_max)
    app = create_web_app_for_session(
        session_id=session_id,
        pending_secret_names=pending_secret_names,
        secretfile=secretfile,
        lockfile=lockfile,
        lockfile_path=lockfile_path,
        secretfile_path=secretfile_path,
        secretfile_content=secretfile_content,
        dry_run=dry_run,
        registry=registry,
    )
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    def _run() -> None:
        asyncio.run(server.serve())

    threading.Thread(target=_run, daemon=True).start()
    return f"http://127.0.0.1:{port}/", port
