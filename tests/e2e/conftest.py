"""Session-scoped localhost API for Tavern black-box tests."""

from __future__ import annotations

import asyncio
import os
import shutil
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from secretzero.api.app import create_app

E2E_PORT = 37654
_FIXTURE = Path(__file__).parent / "fixtures" / "Secretfile.agent_e2e.yml"


@pytest.fixture(scope="session", autouse=True)
def _secretzero_e2e_api_server(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Bind ``create_app`` on a fixed port and expose ``SECRETZERO_E2E_BASE`` for Tavern."""
    if not _FIXTURE.exists():
        pytest.skip("E2E Secretfile fixture missing")

    wd = tmp_path_factory.mktemp("e2e_agent_cwd")
    secretfile = wd / "Secretfile.yml"
    shutil.copy(_FIXTURE, secretfile)
    (wd / ".gitsecrets.lock").write_text('{"version": "1.0", "secrets": {}}', encoding="utf-8")

    os.environ["SECRETZERO_E2E_BASE"] = f"http://127.0.0.1:{E2E_PORT}"

    app = create_app(secretfile_path=str(secretfile.resolve()))

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=E2E_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    def _run() -> None:
        asyncio.run(server.serve())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.8)
    yield
    server.should_exit = True
    thread.join(timeout=5.0)
