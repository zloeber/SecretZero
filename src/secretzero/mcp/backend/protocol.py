"""Backend protocol for SecretZero MCP tools."""

from __future__ import annotations

from typing import Any, Protocol


class SecretZeroBackend(Protocol):
    """Abstract interface implemented by local and HTTP MCP backends."""

    def catalog_list(
        self,
        *,
        provider: str | None = None,
        bundle: str | None = None,
        kind: str | None = None,
    ) -> dict[str, Any]: ...

    def schema_get(self) -> dict[str, Any]: ...

    def secretfile_validate(self) -> dict[str, Any]: ...

    def secrets_list(self, *, name_filter: str | None = None) -> dict[str, Any]: ...

    def secrets_status(self) -> dict[str, Any]: ...

    def providers_list(self) -> dict[str, Any]: ...

    def targets_list(self) -> dict[str, Any]: ...

    def variables_list(self, *, name_filter: str | None = None) -> dict[str, Any]: ...

    def version_info(self, *, detailed: bool = False) -> dict[str, Any]: ...

    def detect_secrets(
        self,
        *,
        directory: str | None = None,
        all_keys: bool = False,
    ) -> dict[str, Any]: ...

    def discover_bindings(
        self,
        *,
        directory: str | None = None,
        local_only: bool = True,
    ) -> dict[str, Any]: ...

    def agent_sync(
        self,
        *,
        dry_run: bool = False,
        refresh: bool = True,
        web: bool = False,
        sz_agent: bool | None = None,
    ) -> dict[str, Any]: ...

    def agent_sync_web_start(
        self,
        *,
        dry_run: bool = False,
        refresh: bool = True,
    ) -> dict[str, Any]: ...

    def agent_sync_web_poll(self, session_id: str) -> dict[str, Any]: ...

    def agent_instructions(
        self,
        *,
        show_all: bool = False,
        detailed: bool = False,
        secret_names: list[str] | None = None,
    ) -> dict[str, Any]: ...

    def drift_check(self, *, secret_name: str | None = None) -> dict[str, Any]: ...

    def sync_dry_run(
        self,
        *,
        secret_name: str | None = None,
        refresh: bool = True,
        force: bool = False,
    ) -> dict[str, Any]: ...

    def sync_execute(
        self,
        *,
        secret_name: str | None = None,
        refresh: bool = True,
        force: bool = False,
    ) -> dict[str, Any]: ...

    def rotate_check(self, *, secret_name: str | None = None) -> dict[str, Any]: ...

    def rotate_execute(
        self, *, secret_name: str | None = None, force: bool = False
    ) -> dict[str, Any]: ...

    def agent_adopt(
        self,
        *,
        target: str | None = None,
        source_dir: str | None = None,
        output_dir: str | None = None,
        template: bool = False,
        preseed_lockfile: bool = False,
        dry_run: bool = True,
        force: bool = False,
    ) -> dict[str, Any]: ...

    def clean_lockfile(self, *, dry_run: bool = True) -> dict[str, Any]: ...

    def ingest_preseed(self, *, source: str, dry_run: bool = True) -> dict[str, Any]: ...
