"""Agent target registry and autodetection."""

from __future__ import annotations

from pathlib import Path

from secretzero.integrations.base import AgentInstallDetection, AgentTargetAdapter
from secretzero.integrations.hermes.adapter import HermesAgentAdapter
from secretzero.integrations.openclaw.adapter import OpenClawAgentAdapter

_ADAPTERS: dict[str, AgentTargetAdapter] = {
    HermesAgentAdapter.target_id: HermesAgentAdapter(),
    OpenClawAgentAdapter.target_id: OpenClawAgentAdapter(),
}


def get_adapter(target_id: str) -> AgentTargetAdapter | None:
    return _ADAPTERS.get(target_id.lower())


def list_adapters() -> list[AgentTargetAdapter]:
    return sorted(_ADAPTERS.values(), key=lambda a: a.autodetect_order)


def list_agent_targets() -> list[str]:
    return [adapter.target_id for adapter in list_adapters()]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        try:
            key = str(path.expanduser().resolve())
        except OSError:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path.expanduser())
    return out


def detect_all_installs() -> list[AgentInstallDetection]:
    """Scan default paths for every registered adapter."""
    found: list[AgentInstallDetection] = []
    seen_dirs: set[str] = set()
    for adapter in list_adapters():
        for candidate in _dedupe_paths(adapter.default_install_paths()):
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            key = str(resolved)
            if key in seen_dirs:
                continue
            detection = adapter.detect_install(resolved)
            if detection is None:
                continue
            seen_dirs.add(key)
            found.append(detection)
    return found


def autodetect_target() -> tuple[str, Path] | None:
    """Return first detected adapter in autodetect order (Hermes, then OpenClaw)."""
    for adapter in list_adapters():
        for candidate in _dedupe_paths(adapter.default_install_paths()):
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            detection = adapter.detect_install(resolved)
            if detection is not None:
                return adapter.target_id, detection.source_dir
    return None


def resolve_agent_install(
    *,
    target: str | None,
    source_dir: Path | None,
) -> tuple[AgentTargetAdapter, Path] | None:
    """Resolve adapter + install root, applying autodetection when omitted."""
    adapter: AgentTargetAdapter | None = None
    root: Path | None = None

    if target:
        adapter = get_adapter(target)
        if adapter is None:
            return None

    if source_dir is not None:
        root = source_dir.expanduser().resolve()
        if adapter is None:
            for candidate in list_adapters():
                if candidate.detect_install(root) is not None:
                    adapter = candidate
                    break
            if adapter is None:
                return None
        elif adapter.detect_install(root) is None:
            return None
    elif adapter is not None:
        for candidate in _dedupe_paths(adapter.default_install_paths()):
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if adapter.detect_install(resolved) is not None:
                root = resolved
                break
        if root is None:
            return None
    else:
        auto = autodetect_target()
        if auto is None:
            return None
        target_id, root = auto
        adapter = get_adapter(target_id)
        if adapter is None:
            return None

    assert adapter is not None and root is not None
    return adapter, root
