"""Temporary localhost FastAPI form for Vector 2 (secure human input, not agent context)."""

from __future__ import annotations

import asyncio
import base64
import copy
import json
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
from secretzero.generators.traits import secret_prompts_like_static
from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile
from secretzero.sync_identity import collect_lockfile_sync_identity

logger = logging.getLogger(__name__)

_JSON_FIELD_PREFIX = "SzJson__"
_LEAF_FIELD_PREFIX = "SzLeaf__"


def _b64u_encode(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def json_bulk_field_key(secret_name: str) -> str:
    """Form field name for optional full-object JSON input (static dict secrets)."""
    return f"{_JSON_FIELD_PREFIX}{_b64u_encode(secret_name)}"


def leaf_field_key(secret_name: str, path: tuple[str, ...]) -> str:
    """Stable form field name for one dict leaf (sorted path segments)."""
    payload = json.dumps({"s": secret_name, "p": list(path)}, sort_keys=True, separators=(",", ":"))
    return f"{_LEAF_FIELD_PREFIX}{_b64u_encode(payload)}"


def effective_static_value(secret: Secret) -> Any:
    """Same source order as :class:`StaticGenerator` (``default`` overrides ``value``)."""
    if "default" in secret.config:
        return secret.config["default"]
    return secret.config.get("value")


def static_dict_needs_leaf_prompts(secret: Secret) -> bool:
    """True when this static-like secret uses a dict/object value with missing leaves."""
    if not secret_prompts_like_static(secret):
        return False
    from secretzero.generators.static import static_payload_needs_prompt

    value = effective_static_value(secret)
    return isinstance(value, dict) and static_payload_needs_prompt(value, nested=False)


def _walk_dict_leaves_needing_prompt(
    data: dict[str, Any], prefix: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], Any]]:
    from secretzero.generators.static import static_payload_needs_prompt

    out: list[tuple[tuple[str, ...], Any]] = []
    for key in sorted(data.keys()):
        raw = data[key]
        path = prefix + (key,)
        if isinstance(raw, dict):
            out.extend(_walk_dict_leaves_needing_prompt(raw, path))
        elif static_payload_needs_prompt(raw, nested=True):
            out.append((path, raw))
    return out


def operator_context_banner_html(secretfile_path: Path | None) -> str:
    """Non-secret identity context for the process (mirrors lockfile sync identity fields)."""
    cwd = secretfile_path.parent if secretfile_path is not None else None
    ident = collect_lockfile_sync_identity(client="agent", cwd=cwd)
    parts: list[str] = []
    if ident.os_user:
        parts.append(f"OS user: {_escape_html(ident.os_user)}")
    if ident.hostname:
        parts.append(f"Host: {_escape_html(ident.hostname)}")
    if ident.git_user_name:
        parts.append(f"Git user: {_escape_html(ident.git_user_name)}")
    if ident.ci_actor:
        parts.append(f"CI actor: {_escape_html(ident.ci_actor)}")
    if not parts:
        return ""
    inner = " · ".join(parts)
    return f'<p class="note" style="margin-top:0.5rem;"><strong>Session</strong> — {inner}</p>'


def _set_nested_leaf(tree: dict[str, Any], path: tuple[str, ...], value: str) -> None:
    cur: dict[str, Any] = tree
    for i, key in enumerate(path):
        if i == len(path) - 1:
            cur[key] = value
        else:
            nxt = cur.get(key)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[key] = nxt
            cur = nxt


def _merge_leaf_strings_into_template(
    template: dict[str, Any], updates: dict[tuple[str, ...], str]
) -> dict[str, Any]:
    out = copy.deepcopy(template)
    for path, val in updates.items():
        _set_nested_leaf(out, path, val)
    return out


def build_pending_static_values_from_form(
    pending_secret_names: list[str],
    secretfile: Secretfile,
    form_values: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Parse Vector 2 (or network) form data into ``{ secret_name: value }`` for injection."""
    from secretzero.generators.static import static_payload_needs_prompt

    by_name = {s.name: s for s in secretfile.secrets}
    out: dict[str, Any] = {}
    for name in pending_secret_names:
        sec = by_name.get(name)
        if sec is None:
            return None, f"Unknown secret {name!r}"
        if not secret_prompts_like_static(sec):
            raw = form_values.get(name)
            if raw is None or str(raw).strip() == "":
                return None, f"Missing value for {name}"
            out[name] = str(raw)
            continue

        eff = effective_static_value(sec)
        if isinstance(eff, dict) and static_payload_needs_prompt(eff, nested=False):
            jkey = json_bulk_field_key(name)
            jraw = form_values.get(jkey)
            if jraw is not None and str(jraw).strip() != "":
                try:
                    parsed = json.loads(str(jraw))
                except json.JSONDecodeError as exc:
                    return None, f"Invalid JSON for {name}: {exc}"
                if not isinstance(parsed, dict):
                    return None, f"JSON for {name} must be a JSON object"
                if static_payload_needs_prompt(parsed, nested=False):
                    return None, f"JSON for {name} still has empty or placeholder fields"
                out[name] = parsed
                continue

            leaves = _walk_dict_leaves_needing_prompt(eff)
            updates: dict[tuple[str, ...], str] = {}
            for path, _tpl in leaves:
                fkey = leaf_field_key(name, path)
                raw = form_values.get(fkey)
                if raw is None or str(raw).strip() == "":
                    disp = ".".join(path)
                    return None, f"Missing value for {name} — {disp}"
                updates[path] = str(raw).strip()
            merged = _merge_leaf_strings_into_template(eff, updates)
            if static_payload_needs_prompt(merged, nested=False):
                return None, f"Some fields for {name} are still empty or unresolved"
            out[name] = merged
            continue

        raw = form_values.get(name)
        if raw is None or str(raw).strip() == "":
            return None, f"Missing value for {name}"
        out[name] = str(raw)
    return out, None


def normalize_scalar_network_form(secret_name: str, form_values: dict[str, Any]) -> dict[str, Any]:
    """Map ``name="value"`` (network dashboard) to the secret-keyed form our parser expects."""
    merged = dict(form_values)
    if "value" in merged and secret_name not in merged:
        merged[secret_name] = merged.pop("value")
    return merged


def static_secret_edit_template_vars(
    secret: Secret, secretfile_path: Path | None
) -> dict[str, Any]:
    """Context for ``secretzero web`` static edit page (structured vs scalar)."""
    banner = operator_context_banner_html(secretfile_path)
    if not static_dict_needs_leaf_prompts(secret):
        return {
            "structured": False,
            "operator_banner_html": banner,
            "dict_leaves": [],
            "json_field_name": None,
        }
    eff = effective_static_value(secret)
    if not isinstance(eff, dict):
        return {
            "structured": False,
            "operator_banner_html": banner,
            "dict_leaves": [],
            "json_field_name": None,
        }
    leaves_out: list[dict[str, str]] = []
    for path, _tpl in _walk_dict_leaves_needing_prompt(eff):
        disp = ".".join(path)
        leaves_out.append(
            {
                "label": disp,
                "field_name": leaf_field_key(secret.name, path),
            }
        )
    return {
        "structured": True,
        "operator_banner_html": banner,
        "dict_leaves": leaves_out,
        "json_field_name": json_bulk_field_key(secret.name),
    }


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


def _build_form_html(
    pending_secret_names: list[str],
    secretfile: Secretfile,
    secretfile_path: Path | None,
    title: str = "SecretZero — manual secrets",
) -> str:
    by_name = {s.name: s for s in secretfile.secrets}
    sections: list[str] = []
    for name in pending_secret_names:
        sec = by_name.get(name)
        safe = _escape_html(name)
        if sec is not None and static_dict_needs_leaf_prompts(sec):
            eff = effective_static_value(sec)
            if not isinstance(eff, dict):
                sections.append(
                    f'<label for="{safe}"><strong>{safe}</strong></label>'
                    f'<input id="{safe}" name="{safe}" type="password" autocomplete="off" required />'
                )
                continue
            leaves = _walk_dict_leaves_needing_prompt(eff)
            leaf_rows: list[str] = []
            for path, _tpl in leaves:
                disp = ".".join(path)
                fkey = leaf_field_key(name, path)
                fid = _escape_html(fkey)
                leaf_rows.append(
                    f'<label for="{fid}"><strong>{safe}</strong> — {_escape_html(disp)}</label>'
                    f'<input id="{fid}" name="{fid}" type="password" autocomplete="off" required />'
                )
            jkey = json_bulk_field_key(name)
            jfid = _escape_html(jkey)
            json_block = (
                f'<details style="margin-top:1rem;"><summary style="cursor:pointer;">'
                f"Paste full JSON for <strong>{safe}</strong> instead</summary>"
                f'<label for="{jfid}" style="margin-top:0.75rem;">JSON object (optional; replaces per-field input)</label>'
                f'<textarea id="{jfid}" name="{jfid}" rows="6" style="width:100%;font-family:monospace;'
                f'margin-top:0.25rem;" placeholder="{{}}"></textarea>'
                f'<p class="note">If you fill JSON, leave per-field inputs empty or omit them.</p></details>'
            )
            sections.append(
                '<fieldset style="border:1px solid #ccc;padding:1rem;margin-top:1rem;border-radius:6px;">'
                f"<legend><strong>{safe}</strong> (structured)</legend>"
                + "\n".join(leaf_rows)
                + json_block
                + "</fieldset>"
            )
        else:
            sections.append(
                f'<label for="{safe}"><strong>{safe}</strong></label>'
                f'<input id="{safe}" name="{safe}" type="password" autocomplete="off" required />'
            )
    body = "\n".join(sections)
    banner = operator_context_banner_html(secretfile_path)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{_escape_html(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; }}
label {{ display: block; margin-top: 1rem; }}
input, textarea {{ width: 100%; padding: 0.5rem; margin-top: 0.25rem; box-sizing: border-box; }}
button {{ margin-top: 1.5rem; padding: 0.5rem 1rem; }}
p.note {{ color: #444; font-size: 0.9rem; }}
</style></head><body>
<h1>{_escape_html(title)}</h1>
<p class="note">Values are sent only to this local process and are not echoed to the agent or logs.</p>
{banner}
<form method="post" action="/submit" id="sz-agent-form">
{body}
<button type="submit">Submit</button>
</form>
<script>
(function () {{
  var form = document.getElementById("sz-agent-form");
  if (!form) return;
  form.addEventListener("submit", function () {{
    var textareas = form.querySelectorAll("textarea[name^=\"{_JSON_FIELD_PREFIX}\"]");
    textareas.forEach(function (ta) {{
      if (ta && ta.value && String(ta.value).trim() !== "") {{
        var fs = ta.closest("fieldset");
        if (!fs) return;
        fs.querySelectorAll("input[type=password]").forEach(function (inp) {{
          inp.removeAttribute("required");
        }});
      }}
    }});
  }});
}})();
</script>
</body></html>"""


def _inject_static_values(secretfile: Secretfile, values: dict[str, Any]) -> Secretfile:
    """Apply submitted values as ``static`` secret ``config.value`` entries.

    ``StaticGenerator`` prefers ``default`` over ``value`` when both exist; manifests
    often use ``default: ${ENV_VAR}`` as a placeholder. Drop ``default`` here so the
    submitted literal is not shadowed by an unresolved env reference.

    Values may be strings or structured dicts (for static object secrets from the web UI).
    """
    new_secrets = []
    for sec in secretfile.secrets:
        if sec.name in values:
            cfg = {**sec.config, "value": values[sec.name]}
            cfg.pop("default", None)
            new_secrets.append(sec.model_copy(update={"config": cfg}))
        else:
            new_secrets.append(sec)
    return secretfile.model_copy(update={"secrets": new_secrets})


def sync_pending_secrets_from_web_form(
    *,
    pending_secret_names: list[str],
    form_values: dict[str, Any],
    secretfile: Secretfile,
    lockfile: Lockfile,
    secretfile_path: Path | None,
    secretfile_content: str | None,
    dry_run: bool,
) -> tuple[Any | None, str | None]:
    """Merge ``form_values`` into static config and run :class:`AgentSecretSynchronizer`.

    Returns ``(result, None)`` on success, or ``(None, error_message)`` on validation failure.
    """
    from secretzero.agent import AgentSecretSynchronizer

    values, err = build_pending_static_values_from_form(
        pending_secret_names,
        secretfile,
        form_values,
    )
    if err or values is None:
        return None, err or "Invalid form data"
    merged = _inject_static_values(secretfile, values)
    syncer = AgentSecretSynchronizer(
        merged,
        lockfile,
        dry_run=dry_run,
        secretfile_path=secretfile_path,
        secretfile_content=secretfile_content,
    )
    return syncer.sync(sz_agent=False), None


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
        return _build_form_html(pending_secret_names, secretfile, secretfile_path)

    @app.post("/submit")
    async def submit(request: Request) -> HTMLResponse:
        try:
            form_data = await request.form()
            res, err = sync_pending_secrets_from_web_form(
                pending_secret_names=pending_secret_names,
                form_values=dict(form_data),
                secretfile=secretfile,
                lockfile=lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
                dry_run=dry_run,
            )
            if err:
                error_box.append(err)
                return HTMLResponse(
                    "<html><body>Missing fields. Go back and try again.</body></html>",
                    status_code=400,
                )
            result_holder.append(res)
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
    from secretzero.agent import build_agent_sync_json_payload

    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    async def form() -> str:
        return _build_form_html(pending_secret_names, secretfile, secretfile_path)

    @app.post("/submit")
    async def submit(request: Request) -> HTMLResponse:
        try:
            form_data = await request.form()
            res, err = sync_pending_secrets_from_web_form(
                pending_secret_names=pending_secret_names,
                form_values=dict(form_data),
                secretfile=secretfile,
                lockfile=lockfile,
                secretfile_path=secretfile_path,
                secretfile_content=secretfile_content,
                dry_run=dry_run,
            )
            if err:
                registry.fail(session_id, err)
                return HTMLResponse(
                    "<html><body>Missing fields.</body></html>",
                    status_code=400,
                )
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
