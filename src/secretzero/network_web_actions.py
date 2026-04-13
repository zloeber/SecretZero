"""CLI-equivalent actions for the network web UI (validate, drift, …)."""

from __future__ import annotations

from pathlib import Path

from secretzero.config import ConfigLoader
from secretzero.drift import DriftDetector


def run_validate_manifest(secretfile_path: Path, var_files: list[Path] | None) -> str:
    """Run :meth:`ConfigLoader.validate_file` and return a plain-text report."""
    loader = ConfigLoader()
    ok, msg = loader.validate_file(secretfile_path, var_files=var_files)
    lines = [
        "Validate manifest",
        f"File: {secretfile_path}",
        "",
        ("OK — " if ok else "FAILED — ") + msg,
    ]
    if ok:
        try:
            cfg = loader.load_file(secretfile_path, var_files=var_files)
            lines.extend(
                [
                    "",
                    "Summary:",
                    f"  Version: {cfg.version}",
                    f"  Variables: {len(cfg.variables)}",
                    f"  Providers: {len(cfg.providers)}",
                    f"  Secrets: {len(cfg.secrets)}",
                    f"  Templates: {len(cfg.templates)}",
                ]
            )
        except Exception as exc:
            lines.extend(["", f"(Could not load summary: {exc})"])
    return "\n".join(lines)


def run_check_drift(secretfile_path: Path, lockfile_path: Path) -> str:
    """Run :class:`DriftDetector` and return a plain-text report."""
    if not lockfile_path.exists():
        return (
            f"Drift check\nLockfile not found: {lockfile_path}\n"
            "Generate it with sync first, then try again."
        )
    det = DriftDetector(secretfile_path, lockfile_path)
    results = det.check_drift()
    lines = [
        "Drift check (lockfile vs live targets)",
        f"Secretfile: {secretfile_path}",
        f"Lockfile: {lockfile_path}",
        "",
        f"Drift detected (any): {any(r.has_drift for r in results)}",
        "",
    ]
    for r in results:
        status = "DRIFT" if r.has_drift else "ok"
        lines.append(f"- [{status}] {r.secret_name}")
        lines.append(f"    {r.message}")
        if r.details:
            lines.append(f"    details: {r.details}")
    return "\n".join(lines)
