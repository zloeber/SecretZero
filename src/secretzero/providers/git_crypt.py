"""git-crypt provider for repository-committed encrypted secret files."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from secretzero.providers.base import BaseProvider, ProviderAuth

if TYPE_CHECKING:
    from secretzero.bundles.registry import BundleManifest


class GitCryptAuth(ProviderAuth):
    """git-crypt auth model (ambient repo unlock state)."""

    def authenticate(self) -> bool:
        return shutil.which("git-crypt") is not None

    def is_authenticated(self) -> bool:
        return self.authenticate()

    def get_token_info(self) -> dict[str, Any]:
        return {
            "user": os.environ.get("USER") or os.environ.get("USERNAME") or "local-user",
            "scopes": ["repo:read", "repo:write"],
            "token_type": "git_crypt_ambient",
        }


class GitCryptProvider(BaseProvider):
    """Provider for workflows where encrypted files are managed by git-crypt filters."""

    display_name = "git-crypt"
    description = "git-crypt managed encrypted file storage"
    required_package = None
    auth_class = GitCryptAuth
    auth_methods = {"ambient": "Use current repository unlock state"}
    config_options = {
        "secret_file": "Path to file tracked by git-crypt filters",
        "format": "Data format: yaml, json, or dotenv (default: yaml)",
    }
    config_example = """providers:
  repo_secrets:
    kind: git_crypt
    auth:
      kind: ambient
    config:
      secret_file: secrets/app.secrets.yaml
      format: yaml"""
    target_details = {
        "git_crypt_file": {
            "description": (
                "Store key/value secrets in a file expected to be encrypted by git-crypt "
                "when committed."
            ),
            "config": {"key": "Optional on-disk key name override (defaults to Secret.name)"},
            "example": """targets:
  - provider: repo_secrets
    kind: git_crypt_file
    config:
      key: APP_DB_PASSWORD""",
        }
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: GitCryptAuth | None = None,
    ):
        if auth is None:
            auth = GitCryptAuth((config or {}).get("auth", {}))
        super().__init__(name, config, auth)

    @property
    def provider_kind(self) -> str:
        return "git_crypt"

    def get_supported_targets(self) -> list[str]:
        return ["git_crypt_file"]

    def test_connection(self) -> tuple[bool, str | None]:
        if shutil.which("git-crypt") is None:
            return False, "git-crypt CLI not found in PATH"
        secret_file = self._get_secret_file()
        if secret_file is None:
            return False, "secret_file not configured"
        if not self._repo_looks_unlocked():
            return False, "git-crypt repository appears locked (run 'git-crypt unlock')"
        return True, f"git-crypt provider ready (file: {secret_file})"

    def retrieve_secret(self, secret_name: str) -> str:
        secret_file = self._require_secret_file()
        if not secret_file.exists():
            raise ValueError(f"Secret file not found: {secret_file}")
        data = self._read_plain(secret_file)
        if secret_name not in data:
            raise ValueError(f"Secret '{secret_name}' not found in file '{secret_file}'")
        return str(data[secret_name])

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        secret_file = self._require_secret_file()
        data: dict[str, str] = {}
        if secret_file.exists():
            data = self._read_plain(secret_file)
        data[secret_name] = secret_value
        self._write_plain(secret_file, data)
        return True

    def delete_secret(self, secret_name: str) -> bool:
        secret_file = self._require_secret_file()
        if not secret_file.exists():
            raise ValueError(f"Secret file not found: {secret_file}")
        data = self._read_plain(secret_file)
        if secret_name not in data:
            return False
        del data[secret_name]
        self._write_plain(secret_file, data)
        return True

    def _get_secret_file(self) -> Path | None:
        secret_file = self.config.get("secret_file")
        return Path(secret_file) if secret_file else None

    def _require_secret_file(self) -> Path:
        secret_file = self._get_secret_file()
        if secret_file is None:
            raise ValueError("secret_file not configured")
        return secret_file

    def _format_type(self) -> str:
        fmt = str(self.config.get("format", "yaml")).strip().lower()
        if fmt not in {"yaml", "json", "dotenv"}:
            raise ValueError(f"Unsupported format: {fmt}")
        return fmt

    def _repo_looks_unlocked(self) -> bool:
        proc = subprocess.run(  # noqa: S603
            ["git-crypt", "status"],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return False
        out = (proc.stdout or "").lower()
        return "not encrypted" in out or "encrypted files" in out

    def _read_plain(self, path: Path) -> dict[str, str]:
        content = path.read_text()
        fmt = self._format_type()
        if fmt == "yaml":
            data = yaml.safe_load(content) or {}
        elif fmt == "json":
            data = json.loads(content) if content.strip() else {}
        else:
            data = self._parse_dotenv(content)
        if not isinstance(data, dict):
            raise ValueError(f"secret_file must contain a {fmt} mapping at the top level")
        return {str(k): str(v) for k, v in data.items()}

    def _write_plain(self, path: Path, data: dict[str, str]) -> None:
        fmt = self._format_type()
        if fmt == "yaml":
            content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
        elif fmt == "json":
            content = json.dumps(data, indent=2)
        else:
            content = self._format_dotenv(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    @staticmethod
    def _parse_dotenv(content: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            result[key.strip()] = value
        return result

    @staticmethod
    def _format_dotenv(data: dict[str, str]) -> str:
        lines: list[str] = []
        for key, value in data.items():
            if " " in value or any(ch in value for ch in ['"', "'", "$", "\\", "\n"]):
                value = f'"{value}"'
            lines.append(f"{key}={value}")
        return "\n".join(lines) + "\n"


def _get_bundle_manifest() -> BundleManifest:
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="git_crypt",
        version="1.0.0",
        provider_class="secretzero.providers.git_crypt:GitCryptProvider",
        generators={},
        targets={"git_crypt_file": "secretzero.targets.git_crypt_file:GitCryptFileTarget"},
        generator_kinds=[],
        target_kinds=["git_crypt_file"],
        terraform_provider=None,
    )
