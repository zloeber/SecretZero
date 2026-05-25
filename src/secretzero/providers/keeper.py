"""Keeper Password Manager provider for vault record retrieval and storage."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any

from secretzero.providers.base import BaseProvider, ProviderAuth

if TYPE_CHECKING:
    from secretzero.bundles.registry import BundleManifest

logger = logging.getLogger(__name__)

DEFAULT_STRUCTURED_FIELDS = ("login", "password", "url", "notes")
JSON_FIELD_PREFIX = "$JSON:"


class KeeperAuth(ProviderAuth):
    """Keeper Commander session authentication."""

    ENV_CONFIG_FILE = "KEEPER_CONFIG_FILE"
    ENV_USER = "KEEPER_USER"
    ENV_PASSWORD = "KEEPER_PASSWORD"
    ENV_SERVER = "KEEPER_SERVER"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._params: Any | None = None
        self._logged_in = False

    def _build_params(self) -> Any:
        from keepercommander.__main__ import get_params_from_config

        config_file = (
            self.config.get("config_file")
            or os.environ.get(self.ENV_CONFIG_FILE)
            or self.config.get("config_path")
        )
        if config_file:
            params = get_params_from_config(os.path.expanduser(str(config_file)))
        else:
            from keepercommander.params import KeeperParams

            params = KeeperParams()
            params.config = {}

        user = self.config.get("user") or os.environ.get(self.ENV_USER)
        if user:
            params.user = str(user)
            params.config["user"] = params.user

        password = self.config.get("password") or os.environ.get(self.ENV_PASSWORD)
        if password:
            params.password = str(password)
            params.config["password"] = params.password

        server = self.config.get("server") or os.environ.get(self.ENV_SERVER)
        if server:
            params.config["server"] = str(server)

        return params

    def authenticate(self) -> bool:
        try:
            from keepercommander import api

            self._params = self._build_params()
            if not self._params.user:
                logger.error("Keeper authentication requires a user (KEEPER_USER or config file)")
                return False

            api.login(self._params)
            if not getattr(self._params, "session_token", None):
                logger.error("Keeper login did not establish a session token")
                return False

            self._logged_in = True
            return True
        except ImportError:
            logger.error(
                "keepercommander is required for Keeper provider. "
                "Install with: pip install secretzero[keeper]"
            )
            return False
        except Exception as exc:
            logger.error("Keeper authentication failed: %s", exc)
            return False

    def is_authenticated(self) -> bool:
        return self._logged_in and self._params is not None

    def get_client(self) -> Any | None:
        return self._params

    def get_token_info(self) -> dict[str, Any]:
        if not self._params:
            raise RuntimeError("Not authenticated")
        server = self._params.config.get("server") if self._params.config else None
        return {
            "user": self._params.user,
            "scopes": [],
            "token_type": "keeper_session",
            "server": server,
            "config_file": getattr(self._params, "config_filename", None),
        }


class KeeperProvider(BaseProvider):
    """Provider for Keeper Password Manager vault records."""

    display_name = "Keeper Password Manager"
    description = "Keeper vault record read/write via Commander SDK"
    required_package = ("keepercommander", "secretzero[keeper]")
    auth_class = KeeperAuth
    auth_methods = {
        "token": "Use KEEPER_CONFIG_FILE or auth.config.config_file",
        "default": "Use KEEPER_USER and KEEPER_PASSWORD (discouraged for production)",
    }
    config_options = {
        "config_file": "Path to Commander config.json (or KEEPER_CONFIG_FILE)",
        "server": "Keeper server hostname (default: keepersecurity.com)",
        "sync_ttl_seconds": "Seconds to cache sync_down results (default: 300)",
        "default_folder": "Default folder path for newly created records",
    }
    config_example = """providers:
  keeper:
    kind: keeper
    auth:
      kind: token
      config:
        config_file: ${KEEPER_CONFIG_FILE}
    config:
      sync_ttl_seconds: 300
      default_folder: "Shared Folders/SecretZero\""""
    target_details = {
        "keeper_record": {
            "description": "Keeper Password Manager vault record field(s)",
            "config": {
                "record_uid": "Stable record UID (preferred after first sync)",
                "path": "Vault path such as Shared Folders/App/DB Password",
                "title": "Record title for lookup or create_if_missing",
                "field": "Scalar field to sync (default: password)",
                "structured": "When true, read/write login/password/url/notes as JSON",
                "fields": "Optional explicit field list for structured mode",
                "create_if_missing": "Create a typed record when locator is missing",
                "record_type": "Typed record kind for create (default: login)",
                "folder": "Folder path override for record creation",
            },
            "example": """targets:
  - provider: keeper
    kind: keeper_record
    config:
      title: "Service Account"
      create_if_missing: true
      record_type: login
      folder: "Shared Folders/SecretZero"
      structured: true""",
        },
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: KeeperAuth | None = None,
    ):
        if auth is None and config:
            auth_cfg = config.get("auth", {}).get("config", {})
            merged = {**auth_cfg}
            for key in ("config_file", "user", "password", "server"):
                if key in config:
                    merged[key] = config[key]
            auth = KeeperAuth(merged)
        super().__init__(name, config, auth)
        self._last_sync_at: float | None = None
        self._last_record_uid: str | None = None

    @property
    def provider_kind(self) -> str:
        return "keeper"

    @property
    def last_record_uid(self) -> str | None:
        """Record UID from the most recent resolve/create/store operation."""
        return self._last_record_uid

    def get_supported_targets(self) -> list[str]:
        return ["keeper_record"]

    def _params(self) -> Any:
        if not self.auth or not self.auth.is_authenticated():
            if not self.auth or not self.auth.authenticate():
                raise RuntimeError(
                    "Keeper authentication failed. Configure KEEPER_CONFIG_FILE or "
                    "KEEPER_USER/KEEPER_PASSWORD."
                )
        params = self.auth.get_client()
        if params is None:
            raise RuntimeError("Keeper session unavailable after authentication")
        return params

    def _sync_ttl_seconds(self) -> int:
        raw = self.config.get("sync_ttl_seconds", 300)
        try:
            ttl = int(raw)
        except (TypeError, ValueError):
            ttl = 300
        return max(0, ttl)

    def _ensure_synced(self, force: bool = False) -> None:
        from keepercommander import api

        params = self._params()
        ttl = self._sync_ttl_seconds()
        now = time.monotonic()
        if (
            not force
            and self._last_sync_at is not None
            and ttl > 0
            and (now - self._last_sync_at) < ttl
            and params.record_cache
        ):
            return

        api.sync_down(params)
        self._last_sync_at = now

    @staticmethod
    def _coerce_field_map(secret_value: Any) -> dict[str, str]:
        if isinstance(secret_value, dict):
            return {
                str(key): "" if value is None else str(value) for key, value in secret_value.items()
            }
        if not isinstance(secret_value, str):
            return {"password": str(secret_value)}

        text = secret_value.strip()
        if not text:
            return {"password": ""}
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {"password": secret_value}
            if isinstance(parsed, dict):
                return {
                    str(key): "" if value is None else str(value) for key, value in parsed.items()
                }
        return {"password": secret_value}

    @staticmethod
    def _structured_field_names(fields: list[str] | None) -> tuple[str, ...]:
        if not fields:
            return DEFAULT_STRUCTURED_FIELDS
        return tuple(str(field) for field in fields)

    @staticmethod
    def _resolve_record(params: Any, *, record_uid: str | None, locator: str | None) -> Any:
        from keepercommander import vault
        from keepercommander.commands.base import RecordMixin

        if record_uid:
            if record_uid not in params.record_cache:
                raise ValueError(f"Keeper record UID '{record_uid}' not found in vault cache")
            record = vault.KeeperRecord.load(params, record_uid)
            if record is None:
                raise ValueError(f"Keeper record UID '{record_uid}' could not be loaded")
            return record

        if not locator:
            raise ValueError(
                "Keeper record locator required: provide record_uid, path, title, or name"
            )

        record = RecordMixin.resolve_single_record(params, locator)
        if record is not None:
            return record

        matches: list[Any] = []
        target = locator.casefold()
        for uid in params.record_cache:
            candidate = vault.KeeperRecord.load(params, uid)
            if candidate and candidate.title.casefold() == target:
                matches.append(candidate)

        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            details = ", ".join(sorted(f"{match.title} ({match.record_uid})" for match in matches))
            raise ValueError(
                f"Ambiguous Keeper record title '{locator}': {len(matches)} matches ({details})"
            )

        raise ValueError(f"Keeper record not found: {locator}")

    @staticmethod
    def _extract_field(record: Any, field_name: str) -> str:
        from keepercommander.commands.base import RecordMixin

        value = RecordMixin.get_record_field(record, field_name)
        if value is None:
            raise ValueError(f"Field '{field_name}' not found or empty on Keeper record")
        return str(value)

    @staticmethod
    def _extract_record_payload(record: Any, field_names: tuple[str, ...]) -> dict[str, str]:
        from keepercommander.commands.base import RecordMixin

        payload: dict[str, str] = {}
        for field_name in field_names:
            value = RecordMixin.get_record_field(record, field_name)
            if value is not None and str(value) != "":
                payload[field_name] = str(value)
        if not payload:
            raise ValueError("No structured fields found on Keeper record")
        return payload

    @staticmethod
    def _apply_field(record: Any, field_name: str, value: str) -> None:
        from keepercommander import vault

        if isinstance(record, vault.PasswordRecord):
            if field_name == "login":
                record.login = value
                return
            if field_name == "password":
                record.password = value
                return
            if field_name in {"url", "link"}:
                record.link = value
                return
            if field_name == "notes":
                record.notes = value
                return
            record.set_custom_value(field_name, value)
            return

        if isinstance(record, vault.TypedRecord):
            typed_field = record.get_typed_field(field_name)
            if typed_field is None:
                record.fields.append(vault.TypedField.new_field(field_name, value))
            else:
                typed_field.value = [value]
            return

        if field_name == "login" and hasattr(record, "login"):
            record.login = value
            return
        if field_name == "password" and hasattr(record, "password"):
            record.password = value
            return
        if field_name in {"url", "link"} and hasattr(record, "link"):
            record.link = value
            return
        if field_name == "notes" and hasattr(record, "notes"):
            record.notes = value
            return
        set_custom = getattr(record, "set_custom_value", None)
        if callable(set_custom):
            set_custom(field_name, value)
            return

        raise ValueError(
            f"Unsupported Keeper record type for field update: {type(record).__name__}"
        )

    def _apply_field_map(self, record: Any, field_map: dict[str, str]) -> None:
        for field_name, value in field_map.items():
            self._apply_field(record, field_name, value)

    def _resolve_locator(
        self,
        *,
        secret_name: str,
        record_uid: str | None = None,
        path: str | None = None,
        title: str | None = None,
        name: str | None = None,
        create_if_missing: bool = False,
        record_type: str | None = None,
        folder: str | None = None,
        field_map: dict[str, str] | None = None,
    ) -> tuple[Any, str]:
        self._ensure_synced()
        params = self._params()
        uid = record_uid or None
        locator = path or title or name or (secret_name if not uid else None)
        try:
            record = self._resolve_record(params, record_uid=uid, locator=locator)
        except ValueError as exc:
            if not create_if_missing or uid:
                raise
            if "not found" not in str(exc).lower():
                raise
            record_title = title or name or secret_name
            record, uid = self._create_record(
                title=record_title,
                record_type=record_type or "login",
                folder=folder,
                field_map=field_map or {"password": ""},
            )
        self._last_record_uid = record.record_uid
        return record, record.record_uid

    def _create_record(
        self,
        *,
        title: str,
        record_type: str,
        folder: str | None,
        field_map: dict[str, str],
    ) -> tuple[Any, str]:
        from keepercommander import api, vault
        from keepercommander.commands import record_edit
        from keepercommander.params import LAST_RECORD_UID

        params = self._params()
        folder_path = folder or self.config.get("default_folder")
        field_specs = [f"{field_name}={value}" for field_name, value in field_map.items() if value]
        if not field_specs and "password" in field_map:
            field_specs = [f"password={field_map['password']}"]

        cmd = record_edit.RecordAddCommand()
        cmd.execute(
            params,
            title=title,
            record_type=record_type,
            folder=folder_path,
            fields=field_specs,
            force=True,
        )
        api.sync_down(params)
        uid = params.environment_variables.get(LAST_RECORD_UID)
        if not uid:
            raise ValueError("Keeper record creation did not return a record UID")
        record = vault.KeeperRecord.load(params, uid)
        if record is None:
            raise ValueError(f"Created Keeper record '{uid}' could not be loaded")
        self._last_record_uid = uid
        logger.info("Created Keeper record title=%s record_uid=%s", title, uid)
        return record, uid

    def _push_record_update(self, record: Any) -> None:
        from keepercommander import record_management, vault

        if not isinstance(record, vault.KeeperRecord):
            raise ValueError("Invalid Keeper record object for update")
        record_management.update_record(self._params(), record)

    def test_connection(self) -> tuple[bool, str | None]:
        try:
            self._ensure_synced(force=True)
            params = self._params()
            count = len(params.record_cache)
            return True, f"Connected to Keeper vault ({count} records cached)"
        except ImportError:
            return False, "keepercommander not installed (pip install secretzero[keeper])"
        except Exception as exc:
            return False, str(exc)

    def generate_password(self, length: int = 32) -> str:
        """Generate a password using Keeper Commander's generator."""
        from keepercommander.commands.record_edit import RecordEditMixin

        safe_length = max(4, min(int(length), 200))
        return RecordEditMixin.generate_password([str(safe_length)])

    def retrieve_secret(
        self,
        secret_name: str,
        *,
        record_uid: str | None = None,
        path: str | None = None,
        title: str | None = None,
        name: str | None = None,
        field: str | None = None,
        structured: bool | None = None,
        fields: list[str] | None = None,
        **_: Any,
    ) -> str:
        """Retrieve a scalar or structured payload from a Keeper vault record."""
        record, _uid = self._resolve_locator(
            secret_name=secret_name,
            record_uid=record_uid,
            path=path,
            title=title,
            name=name,
        )
        if structured:
            payload = self._extract_record_payload(record, self._structured_field_names(fields))
            return json.dumps(payload, sort_keys=True, separators=(",", ":"))
        field_name = (field or "password").strip()
        return self._extract_field(record, field_name)

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        *,
        record_uid: str | None = None,
        path: str | None = None,
        title: str | None = None,
        name: str | None = None,
        field: str | None = None,
        structured: bool | None = None,
        fields: list[str] | None = None,
        create_if_missing: bool = False,
        record_type: str | None = None,
        folder: str | None = None,
        **_: Any,
    ) -> bool:
        """Create or update a Keeper vault record."""
        field_map = self._coerce_field_map(secret_value)
        if structured:
            allowed = set(self._structured_field_names(fields))
            field_map = {key: value for key, value in field_map.items() if key in allowed}
            if not field_map:
                raise ValueError("Structured Keeper store requires at least one allowed field")
        else:
            field_name = (field or "password").strip()
            scalar_value = field_map.get(field_name)
            if scalar_value is None:
                scalar_value = field_map.get("password", secret_value)
            field_map = {field_name: scalar_value}

        record, uid = self._resolve_locator(
            secret_name=secret_name,
            record_uid=record_uid,
            path=path,
            title=title,
            name=name,
            create_if_missing=create_if_missing,
            record_type=record_type,
            folder=folder,
            field_map=field_map,
        )
        self._apply_field_map(record, field_map)
        self._push_record_update(record)
        self._ensure_synced(force=True)
        logger.info("Updated Keeper record record_uid=%s fields=%s", uid, sorted(field_map))
        return True

    def rotate_secret(
        self,
        secret_name: str,
        new_value: str,
        *,
        record_uid: str | None = None,
        path: str | None = None,
        title: str | None = None,
        name: str | None = None,
        field: str | None = None,
        structured: bool | None = None,
        fields: list[str] | None = None,
        create_if_missing: bool = False,
        record_type: str | None = None,
        folder: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """Rotate a Keeper record by writing a newly generated value."""
        return self.store_secret(
            secret_name=secret_name,
            secret_value=new_value,
            record_uid=record_uid,
            path=path,
            title=title,
            name=name,
            field=field,
            structured=structured,
            fields=fields,
            create_if_missing=create_if_missing,
            record_type=record_type,
            folder=folder,
            **kwargs,
        )


def _get_bundle_manifest() -> BundleManifest:
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="keeper",
        version="1.1.0",
        provider_class="secretzero.providers.keeper:KeeperProvider",
        targets={"keeper_record": "secretzero.targets.keeper:KeeperRecordTarget"},
        target_kinds=["keeper_record"],
    )
