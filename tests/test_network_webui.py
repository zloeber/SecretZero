"""Tests for ``secretzero web`` network UI (auth, CSRF, sync hook)."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from secretzero.agent import AgentSyncResult
from secretzero.lockfile import Lockfile
from secretzero.models import Secretfile
from secretzero.network_webui import (
    NetworkWebSessionStore,
    create_network_web_app,
    generate_self_signed_tls_files,
    pick_port_in_range,
)


def _minimal_secretfile() -> Secretfile:
    return Secretfile(version="1.0", secrets=[])


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


def test_network_web_flow_auth_csrf_submit(tmp_path: Path) -> None:
    auth = NetworkWebSessionStore.from_bootstrap_token("tok")
    done = []

    def on_ok() -> None:
        done.append(True)

    sf = _minimal_secretfile()
    lk = _minimal_lockfile(tmp_path)

    app = create_network_web_app(
        pending_secret_names=["s1"],
        secretfile=sf,
        lockfile=lk,
        secretfile_path=None,
        secretfile_content=None,
        dry_run=True,
        auth=auth,
        use_tls=False,
        on_success_shutdown=on_ok,
    )

    fake = AgentSyncResult(
        status="complete",
        synced_secrets=["s1"],
        failed_secrets={},
        pending_secrets={},
    )

    with patch(
        "secretzero.network_webui.sync_pending_secrets_from_web_form",
        return_value=(fake, None),
    ):
        client = TestClient(app)
        r0 = client.get("/")
        assert r0.status_code == 200
        r1 = client.post("/auth", data={"access_token": "wrong"})
        assert r1.status_code == 200
        assert "Invalid access token" in r1.text

        r2 = client.post("/auth", data={"access_token": "tok"}, follow_redirects=False)
        assert r2.status_code == 302
        assert r2.headers["location"] == "/form"
        sid_cookie = r2.cookies.get("sz_web_session")
        assert sid_cookie

        r3 = client.get("/form", cookies=r2.cookies)
        assert r3.status_code == 200
        assert "csrf_token" in r3.text

        # extract csrf from HTML roughly
        import re

        m = re.search(r'name="csrf_token" value="([^"]+)"', r3.text)
        assert m
        csrf = m.group(1)

        r4 = client.post(
            "/submit",
            data={"csrf_token": csrf, "s1": "x"},
            cookies=r2.cookies,
        )
        assert r4.status_code == 200
        assert "done" in r4.text.lower() or "dry run" in r4.text.lower()
        assert done == [True]
