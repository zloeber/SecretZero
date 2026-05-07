"""GitNexus / MetaGit integration helpers for relational secret intelligence.

Produces `.gitnexus/secrets_overlay.json` for knowledge-graph ingestion and
optional `~/.metagit.yml` fragments for workspace situational awareness.

No network I/O — local files and optional subprocess calls when GitNexus CLI
is installed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from secretzero.models import Secretfile

OVERLAY_SCHEMA_VERSION = "1"
# Documented node kind for LadybugDB / GitNexus consumers (contract string).
LADYBUG_SECRET_BINDING_KIND = "secretzero.secret_binding"


def gitnexus_overlay_disabled() -> bool:
    return os.environ.get("SZ_NO_GITNEXUS_OVERLAY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def metagit_registry_enabled() -> bool:
    return os.environ.get("SZ_METAGIT_REGISTRY", "").strip().lower() in ("1", "true", "yes")


def _repo_slug(repo_root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()).name
    except OSError:
        pass
    return repo_root.name or "repo"


def _count_source_files(repo_root: Path, *, limit: int = 8000) -> int:
    """Rough file count for density scoring (extension-heuristic, capped)."""
    exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt"}
    n = 0
    for p in repo_root.rglob("*"):
        if n >= limit:
            break
        if p.is_file() and p.suffix.lower() in exts:
            if "node_modules" in p.parts or ".venv" in p.parts:
                continue
            n += 1
    return max(n, 1)


def secret_density_score(secret_count: int, repo_root: Path) -> float:
    """Heuristic secrets-per-source-file ratio for MetaGit dashboards."""
    denom = _count_source_files(repo_root)
    return round(float(secret_count) / float(denom), 6)


def load_discovery_bindings(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ".gitnexus" / "discovery_bindings.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    bindings = raw.get("bindings")
    return bindings if isinstance(bindings, dict) else {}


def build_secrets_overlay(
    secretfile: Secretfile,
    *,
    secretfile_path: Path,
    repo_root: Path,
    discovery_bindings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build secrets_overlay.json payload (LadybugDB-oriented graph hints)."""
    root = repo_root.resolve()
    bindings_map = (
        discovery_bindings if discovery_bindings is not None else load_discovery_bindings(root)
    )
    slug = _repo_slug(root)
    secrets_out: dict[str, Any] = {}
    for s in secretfile.secrets:
        b_raw = bindings_map.get(s.name)
        b = b_raw if isinstance(b_raw, dict) else {}
        symbol_ids: list[str] = []
        sid = b.get("symbol_id")
        if isinstance(sid, str) and sid.strip():
            symbol_ids.append(sid.strip())
        extra = b.get("symbol_ids")
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, str) and item.strip() and item not in symbol_ids:
                    symbol_ids.append(item.strip())
        fqns: list[str] = []
        sfqn = b.get("symbol_fqn")
        if isinstance(sfqn, str) and sfqn.strip():
            fqns.append(sfqn.strip())
        for f in b.get("fqns") or []:
            if isinstance(f, str) and f.strip() and f not in fqns:
                fqns.append(f.strip())
        containing = b.get("containing_symbol")
        source_file = b.get("source_file")
        line_no = b.get("line_number")
        uri_name = quote(s.name, safe="")
        entry: dict[str, Any] = {
            "kind": LADYBUG_SECRET_BINDING_KIND,
            "process_tags": list(s.process_tags),
            "symbol_ids": symbol_ids,
            "fqns": fqns,
            "containing_symbol": containing if isinstance(containing, str) else None,
            "mcp_resource_uri": f"secretzero://repo/{slug}/secret/{uri_name}/usage",
        }
        refs: list[dict[str, Any]] = []
        if isinstance(source_file, str) and source_file:
            ref: dict[str, Any] = {"file": source_file}
            if isinstance(line_no, int) and line_no > 0:
                ref["line"] = line_no
            refs.append(ref)
        entry["source_refs"] = refs
        secrets_out[s.name] = entry

    return {
        "schema_version": OVERLAY_SCHEMA_VERSION,
        "ladybug_schema_profile": "gitnexus.secret_overlay.v1",
        "repo_slug": slug,
        "repo_root": str(root),
        "secretfile": str(secretfile_path.resolve()),
        "generated_at": datetime.now(UTC).isoformat(),
        "secrets": secrets_out,
    }


def write_secrets_overlay(secretfile_path: Path, overlay: dict[str, Any]) -> Path:
    out_dir = secretfile_path.parent / ".gitnexus"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "secrets_overlay.json"
    path.write_text(json.dumps(overlay, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


def merge_metagit_registry(secretfile_path: Path, secretfile: Secretfile) -> Path | None:
    """Merge SecretZero inventory metadata into ~/.metagit.yml when enabled."""
    if not metagit_registry_enabled():
        return None
    root = secretfile_path.parent.resolve()
    score = secret_density_score(len(secretfile.secrets), root)
    entry = {
        "secretfile": str(secretfile_path.resolve()),
        "repo_root": str(root),
        "secret_count": len(secretfile.secrets),
        "secret_density_score": score,
        "updated_at": datetime.now(UTC).isoformat(),
        "process_tags_present": sorted(
            {tag for s in secretfile.secrets for tag in (s.process_tags or [])}
        ),
    }
    home = Path.home()
    mg_path = home / ".metagit.yml"
    data: dict[str, Any] = {}
    if mg_path.is_file():
        try:
            loaded = yaml.safe_load(mg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, yaml.YAMLError):
            data = {}
    sz = data.get("secretzero")
    if not isinstance(sz, dict):
        sz = {}
    repos = sz.get("repos")
    if not isinstance(repos, dict):
        repos = {}
    repos[str(root)] = entry
    sz["repos"] = repos
    data["secretzero"] = sz
    mg_path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return mg_path


def emit_gitnexus_sidecars(
    *,
    secretfile_path: Path,
    secretfile: Secretfile,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Write overlay (and optionally MetaGit registry). Returns summary dict."""
    if gitnexus_overlay_disabled():
        return {"skipped": True, "reason": "SZ_NO_GITNEXUS_OVERLAY"}
    root = repo_root if repo_root is not None else secretfile_path.parent.resolve()
    overlay = build_secrets_overlay(secretfile, secretfile_path=secretfile_path, repo_root=root)
    overlay_path = write_secrets_overlay(secretfile_path, overlay)
    out: dict[str, Any] = {
        "secrets_overlay": str(overlay_path),
        "skipped": False,
    }
    mg = merge_metagit_registry(secretfile_path, secretfile)
    if mg is not None:
        out["metagit_registry"] = str(mg)
    return out


def run_gitnexus_analyze_skills(cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run `gitnexus analyze --skills` when CLI is available."""
    try:
        return subprocess.run(
            ["gitnexus", "analyze", "--skills"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["gitnexus", "analyze", "--skills"],
            returncode=127,
            stdout="",
            stderr="gitnexus executable not found on PATH",
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=["gitnexus", "analyze", "--skills"],
            returncode=1,
            stdout="",
            stderr=str(exc),
        )


def run_gitnexus_blast_radius(
    symbol_fqn: str,
    cwd: Path | None = None,
    *,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke GitNexus impact-style analysis for a symbol FQN.

    Uses `gitnexus impact` when present; falls back to `npx gitnexus impact`.
    """
    cwd = cwd or Path.cwd()
    args_base = ["impact", "--target", symbol_fqn]
    if extra_args:
        args_base.extend(extra_args)

    for cmd in (["gitnexus"], ["npx", "gitnexus"]):
        full = cmd + args_base
        try:
            return subprocess.run(
                full,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return subprocess.CompletedProcess(
        args=["gitnexus", "impact"],
        returncode=127,
        stdout="",
        stderr="Neither gitnexus nor npx on PATH",
    )


def format_blast_radius_cli(symbol_fqn: str, cwd: Path | None = None) -> str:
    """Shell one-liner hint for agents (gitnexus vs npx)."""
    cwd = cwd or Path.cwd()
    safe = re.sub(r"['\"\\]", "", symbol_fqn)
    return (
        f"cd {sh_quote(str(cwd.resolve()))} && "
        f"(gitnexus impact --target {sh_quote(safe)} || npx gitnexus impact --target {sh_quote(safe)})"
    )


def sh_quote(s: str) -> str:
    """POSIX-ish single-quote wrapping."""
    return "'" + s.replace("'", "'\"'\"'") + "'"


def print_impact_suggestion(symbol_fqn: str, *, stream: Any = None) -> None:
    stream = stream or sys.stderr
    stream.write(
        "GitNexus CLI not found. Install GitNexus or run:\n  "
        + format_blast_radius_cli(symbol_fqn)
        + "\n"
    )
