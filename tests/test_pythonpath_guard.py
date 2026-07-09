"""Regression: hostile PYTHONPATH must not shadow secretzero's bundled deps."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_import_survives_hostile_pythonpath() -> None:
    """A decoy pydantic on PYTHONPATH must not win over our site-packages."""
    junk = tempfile.mkdtemp()
    decoy = Path(junk) / "pydantic"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("# hostile decoy\n", encoding="utf-8")

    env = dict(os.environ, PYTHONPATH=junk)
    # Ensure the subprocess uses the same interpreter/venv as the test run.
    result = subprocess.run(
        [sys.executable, "-c", "import secretzero"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
