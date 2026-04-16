"""Tests for ``secretzero web`` network UI (auth, dashboard, shutdown)."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile
from secretzero.network_webui import (
    NetworkWebSessionStore,
    create_network_web_app,
    format_sync_results_for_debug,
    generate_self_signed_tls_files,
    pick_port_in_range,
)


def _minimal_secretfile() -> Secretfile:
    return Secretfile(secrets=[])


def _secretfile_one_static() -> Secretfile:
    return Secretfile(
        secrets=[
            Secret(name="s1", kind="static", config={"value": "x"}, targets=[]),
        ],
    )


def _secretfile_with_environments() -> Secretfile:
    return Secretfile(
        environments={
            "default": "dev",
            "profiles": {
                "dev": {"var_files": [], "lockfile": ".gitsecrets.dev.lock"},
                "prod": {"var_files": [], "lockfile": ".gitsecrets.prod.lock"},
            },
        },
        providers={"local": {"kind": "local"}},
        secrets=[
            Secret(name="s1", kind="static", config={"value": "x"}, targets=[]),
        ],
    )


def _minimal_lockfile(tmp: Path) -> Lockfile:
    p = tmp / ".gitsecrets.lock"
    p.write_text('{"version": "1.0", "secrets": {}}\n')
    return Lockfile.load(p)


def test_bootstrap_token_single_use() -> None:
    store = NetworkWebSessionStore.from_bootstrap_token("bootstrap-secret")
    a = store.try_authenticate("bootstrap-secret")
    assert a is not None
    assert store.bootstrap_consumed
    b = store.try_authenticate("bootstrap-secret")
    assert b is None


def test_pick_port_in_range_localhost() -> None:
    p = pick_port_in_range("127.0.0.1", 45000, 45010)
    assert 45000 <= p <= 45010


def test_self_signed_generates_pem(tmp_path: Path) -> None:
    cert_f, key_f, fp = generate_self_signed_tls_files(extra_sans=["10.0.0.5"], validity_days=30)
    try:
        assert cert_f.exists() and key_f.exists()
        assert len(fp) == 64
        text = cert_f.read_text()
        assert "BEGIN CERTIFICATE" in text
    finally:
        cert_f.unlink(missing_ok=True)
        key_f.unlink(missing_ok=True)


class _ImmediateTimer:
    """Run Timer callback synchronously on start (for tests)."""

    def __init__(
        self, interval: float, function: object, args: tuple = (), kwargs: dict | None = None
    ) -> None:
        self._fn = function
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._fn(*self._args, **self._kwargs)


def test_dashboard_auth_and_shutdown(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("tok")
    done: list[bool] = []

    def on_ok() -> None:
        done.append(True)

    lk_path = tmp_path / ".gitsecrets.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    lk = Lockfile.load(lk_path)

    app = create_network_web_app(
        secretfile=_minimal_secretfile(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=tmp_path / "Secretfile.yml",
        secretfile_content="version: '1.0'\nsecrets: []\n",
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=on_ok,
    )

    mock_eng = MagicMock()
    mock_eng.sync.return_value = {"errors": [], "details": []}

    with (
        patch("secretzero.network_webui.make_sync_engine", return_value=mock_eng),
        patch("secretzero.network_webui.threading.Timer", _ImmediateTimer),
    ):
        client = TestClient(app)
        r2 = client.post("/auth", data={"access_token": "tok"}, follow_redirects=False)
        assert r2.status_code == 302
        assert r2.headers["location"] == "/dashboard"

        r3 = client.get("/dashboard", cookies=r2.cookies)
        assert r3.status_code == 200
        assert "Manifest" in r3.text or "manifest" in r3.text.lower()
        r3u = client.get("/dashboard?filter=unsynced", cookies=r2.cookies)
        assert r3u.status_code == 200
        assert "Unsynced only" in r3u.text
        assert "Secretfile.yml" in r3u.text
        assert "Graph" in r3u.text

        m = re.search(r'name="csrf_token" value="([^"]+)"', r3.text)
        assert m
        csrf = m.group(1)

        r4 = client.post(
            "/shutdown",
            data={"csrf_token": csrf},
            cookies=r2.cookies,
        )
        assert r4.status_code == 200
        assert "stopped" in r4.text.lower()
        assert done == [True]


def test_dashboard_tabs_show_secretfile_and_graph(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("tabs")
    lk_path = tmp_path / ".gitsecrets.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    sf_path = tmp_path / "Secretfile.yml"
    sf_text = (
        "version: '1.0'\nsecrets:\n  - name: s1\n    kind: static\n    config:\n      value: x\n"
    )
    sf_path.write_text(sf_text)
    lk = Lockfile.load(lk_path)
    app = create_network_web_app(
        secretfile=_secretfile_one_static(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=sf_path,
        secretfile_content=sf_text,
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    client = TestClient(app)
    auth_resp = client.post("/auth", data={"access_token": "tabs"}, follow_redirects=False)
    assert auth_resp.status_code == 302
    cookies = auth_resp.cookies

    source_tab = client.get("/dashboard?tab=secretfile", cookies=cookies)
    assert source_tab.status_code == 200
    assert "Full rendered Secretfile content" in source_tab.text
    assert "name: s1" in source_tab.text

    graph_mermaid_tab = client.get("/dashboard?tab=graph&graph_view=mermaid", cookies=cookies)
    assert graph_mermaid_tab.status_code == 200
    assert 'class="mermaid"' in graph_mermaid_tab.text
    assert "Generated graph (JSON)" in graph_mermaid_tab.text
    assert "Destination" in graph_mermaid_tab.text

    graph_json_tab = client.get(
        "/dashboard?tab=graph&graph_view=json&graph_type=flow",
        cookies=cookies,
    )
    assert graph_json_tab.status_code == 200
    assert "nodes" in graph_json_tab.text
    assert "edges" in graph_json_tab.text

    dash_main = client.get("/dashboard?tab=dashboard", cookies=cookies)
    assert dash_main.status_code == 200
    assert "Check drift" not in dash_main.text
    assert "/action/import-all" in dash_main.text


def test_sync_all_invokes_engine(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("t2")
    lk_path = tmp_path / "x.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    lk = Lockfile.load(lk_path)

    app = create_network_web_app(
        secretfile=_secretfile_one_static(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=None,
        secretfile_content=None,
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    mock_eng = MagicMock()
    with patch("secretzero.network_webui.make_sync_engine", return_value=mock_eng):
        c = TestClient(app)
        r_auth = c.post("/auth", data={"access_token": "t2"}, follow_redirects=False)
        cookies = r_auth.cookies
        dash = c.get("/dashboard", cookies=cookies)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', dash.text)
        assert csrf
        c.post("/action/sync-all", data={"csrf_token": csrf.group(1)}, cookies=cookies)
        mock_eng.sync.assert_called()


def test_import_all_invokes_run_lockfile_import(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("imptok")
    lk_path = tmp_path / "imp.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    lk = Lockfile.load(lk_path)
    sf_path = tmp_path / "Secretfile.yml"
    sf_text = (
        "version: '1.0'\nsecrets:\n  - name: s1\n    kind: static\n    config:\n      value: x\n"
    )
    sf_path.write_text(sf_text)
    app = create_network_web_app(
        secretfile=_secretfile_one_static(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=sf_path,
        secretfile_content=sf_text,
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    with patch("secretzero.network_webui.run_lockfile_import") as mock_imp:
        mock_imp.return_value = {
            "errors": 0,
            "imported": 0,
            "updated": 0,
            "unchanged": 1,
            "skipped": 0,
            "would_apply": 0,
            "details": [],
            "refresh": {},
            "dry_run": True,
        }
        c = TestClient(app)
        r0 = c.post("/auth", data={"access_token": "imptok"}, follow_redirects=False)
        cookies = r0.cookies
        dash = c.get("/dashboard", cookies=cookies)
        m = re.search(r'name="csrf_token" value="([^"]+)"', dash.text)
        assert m
        r_imp = c.post(
            "/action/import-all",
            data={"csrf_token": m.group(1), "list_filter": "all"},
            cookies=cookies,
            follow_redirects=False,
        )
        assert r_imp.status_code == 303
        mock_imp.assert_called_once()


def test_check_drift_route_is_removed(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("drftok")
    lk_path = tmp_path / "d.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    lk = Lockfile.load(lk_path)
    app = create_network_web_app(
        secretfile=_secretfile_one_static(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=None,
        secretfile_content=None,
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    c = TestClient(app)
    r0 = c.post("/auth", data={"access_token": "drftok"}, follow_redirects=False)
    dash = c.get("/dashboard", cookies=r0.cookies)
    m = re.search(r'name="csrf_token" value="([^"]+)"', dash.text)
    assert m
    r404 = c.post(
        "/action/check-drift",
        data={"csrf_token": m.group(1), "list_filter": "all"},
        cookies=r0.cookies,
    )
    assert r404.status_code == 404


def test_format_sync_results_for_debug_omits_raw_secrets() -> None:
    payload = {
        "secrets_stored": 1,
        "errors": [],
        "details": [
            {
                "name": "n1",
                "kind": "static",
                "stored": True,
                "skipped": False,
                "targets": [
                    {
                        "provider": "local",
                        "kind": "file",
                        "status": "stored",
                        "message": "written",
                    }
                ],
            }
        ],
    }
    text = format_sync_results_for_debug(payload)
    assert "n1" in text
    assert "stored" in text
    assert "super-sensitive-token-123" not in text


def test_rotate_static_redirects_to_edit(tmp_path: Path) -> None:
    """Rotate on a static secret must not run sync (unresolved ${ENV} in YAML); use Set value UI."""
    auth = NetworkWebSessionStore.from_bootstrap_token("rottok")
    lk_path = tmp_path / "r.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    lk = Lockfile.load(lk_path)
    app = create_network_web_app(
        secretfile=_secretfile_one_static(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=None,
        secretfile_content=None,
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    with patch("secretzero.network_webui.make_sync_engine") as mock_make:
        c = TestClient(app)
        r0 = c.post("/auth", data={"access_token": "rottok"}, follow_redirects=False)
        ck = r0.cookies
        dash = c.get("/dashboard", cookies=ck)
        m = re.search(r'name="csrf_token" value="([^"]+)"', dash.text)
        assert m
        r_rot = c.post(
            "/action/rotate-secret",
            data={"csrf_token": m.group(1), "list_filter": "all", "secret_name": "s1"},
            cookies=ck,
            follow_redirects=False,
        )
        assert r_rot.status_code == 303
        assert r_rot.headers["location"].startswith("/secret/s1/edit")
        assert "filter=all" in r_rot.headers["location"]
        mock_make.assert_not_called()


def test_apply_static_calls_sync_with_force_rotation(tmp_path: Path) -> None:
    """Changing a static value must force target writes; lockfile may show targets already synced."""
    auth = NetworkWebSessionStore.from_bootstrap_token("applytok")
    lk_path = tmp_path / "z.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    lk = Lockfile.load(lk_path)
    app = create_network_web_app(
        secretfile=_secretfile_one_static(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=None,
        secretfile_content=None,
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    mock_eng = MagicMock()
    mock_eng.sync.return_value = {"secrets_stored": 0, "errors": [], "details": []}
    with patch("secretzero.network_webui.make_sync_engine", return_value=mock_eng):
        c = TestClient(app)
        r0 = c.post("/auth", data={"access_token": "applytok"}, follow_redirects=False)
        assert r0.status_code == 302
        ck = r0.cookies
        dash = c.get("/dashboard", cookies=ck)
        m = re.search(r'name="csrf_token" value="([^"]+)"', dash.text)
        assert m
        r_apply = c.post(
            "/secret/s1/apply",
            data={"csrf_token": m.group(1), "value": "newval", "list_filter": "all"},
            cookies=ck,
            follow_redirects=False,
        )
        assert r_apply.status_code == 303
        mock_eng.sync.assert_called_once()
        ca = mock_eng.sync.call_args
        assert ca.kwargs.get("force_rotation") is True
        assert ca.kwargs.get("secret_names") == ["s1"]


def test_secret_edit_hides_target_provenance_actor(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("acttok")
    lk_path = tmp_path / "a.lock"
    lk_path.write_text(
        '{"version":"1.0","secrets":{"s1":{"hash":"h","created_at":"t","updated_at":"t",'
        '"target_provenance":{"local/file/.env":[{"updated_at":"t","actor":{"provider":"local","os_user":"alice"}}]}}}}\n'
    )
    lk = Lockfile.load(lk_path)
    app = create_network_web_app(
        secretfile=_secretfile_one_static(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=None,
        secretfile_content=None,
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    c = TestClient(app)
    r0 = c.post("/auth", data={"access_token": "acttok"}, follow_redirects=False)
    assert r0.status_code == 302
    edit = c.get("/secret/s1/edit", cookies=r0.cookies)
    assert edit.status_code == 200
    assert "Recent target actor metadata" not in edit.text
    assert "alice" not in edit.text


def test_dashboard_includes_debug_panel_when_enabled(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("dbg")
    lk_path = tmp_path / "d.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    lk = Lockfile.load(lk_path)
    app = create_network_web_app(
        secretfile=_minimal_secretfile(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=tmp_path / "Secretfile.yml",
        secretfile_content="version: '1.0'\nsecrets: []\n",
        var_file_paths=None,
        runtime_var_file_paths=None,
        runtime_lockfile=None,
        environment=None,
        dry_run=True,
        debug=True,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    c = TestClient(app)
    r0 = c.post("/auth", data={"access_token": "dbg"}, follow_redirects=False)
    assert r0.status_code == 302
    dash = c.get("/dashboard", cookies=r0.cookies)
    assert dash.status_code == 200
    assert "Debug log" in dash.text


def test_dashboard_renders_environment_selector(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("envtok")
    lk_path = tmp_path / "env.lock"
    lk_path.write_text('{"version": "1.0", "secrets": {}}\n')
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("secrets: []\n", encoding="utf-8")
    lk = Lockfile.load(lk_path)
    app = create_network_web_app(
        secretfile=_secretfile_with_environments(),
        lockfile=lk,
        lockfile_path=lk_path,
        secretfile_path=sf_path,
        secretfile_content="secrets: []\n",
        var_file_paths=[],
        runtime_var_file_paths=[],
        runtime_lockfile=None,
        environment="dev",
        dry_run=True,
        debug=False,
        auth=auth,
        use_tls=False,
        on_shutdown=lambda: None,
    )
    client = TestClient(app)
    auth_resp = client.post("/auth", data={"access_token": "envtok"}, follow_redirects=False)
    assert auth_resp.status_code == 302
    dash = client.get("/dashboard", cookies=auth_resp.cookies)
    assert dash.status_code == 200
    assert 'name="environment"' in dash.text
    assert "Environment" in dash.text
