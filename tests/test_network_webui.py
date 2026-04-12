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
    generate_self_signed_tls_files,
    pick_port_in_range,
)


def _minimal_secretfile() -> Secretfile:
    return Secretfile(version="1.0", secrets=[])


def _secretfile_one_static() -> Secretfile:
    return Secretfile(
        version="1.0",
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
        dry_run=True,
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
        dry_run=True,
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
