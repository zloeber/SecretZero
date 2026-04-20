"""SOPS provider for encrypted file-based secrets checked into git."""

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


class SopsAuth(ProviderAuth):
    """SOPS auth model (ambient keys managed by sops backend)."""

    def authenticate(self) -> bool:
        return shutil.which("sops") is not None

    def is_authenticated(self) -> bool:
        return self.authenticate()

    def get_token_info(self) -> dict[str, Any]:
        backend = "unknown"
        for key, val in (
            ("SOPS_AGE_KEY_FILE", os.environ.get("SOPS_AGE_KEY_FILE")),
            ("SOPS_AGE_KEY", os.environ.get("SOPS_AGE_KEY")),
            ("SOPS_PGP_FP", os.environ.get("SOPS_PGP_FP")),
            ("AWS_PROFILE", os.environ.get("AWS_PROFILE")),
            ("AZURE_CLIENT_ID", os.environ.get("AZURE_CLIENT_ID")),
        ):
            if val:
                backend = key
                break
        return {
            "user": os.environ.get("USER") or os.environ.get("USERNAME") or "local-user",
            "scopes": ["file:decrypt", "file:encrypt"],
            "token_type": "sops_ambient",
            "backend_hint": backend,
        }


class SopsProvider(BaseProvider):
    """Local encrypted-file provider backed by the SOPS CLI."""

    display_name = "SOPS"
    description = "SOPS-encrypted file storage"
    required_package = None
    auth_class = SopsAuth
    auth_methods = {"ambient": "Use local SOPS key material (age/pgp/kms/vault backends)"}
    config_options = {
        "sops_file": "Path to encrypted SOPS file",
        "format": "Data format: yaml, json, or dotenv (default: yaml)",
    }
    config_example = """providers:
  repo_secrets:
    kind: sops
    auth:
      kind: ambient
    config:
      sops_file: secrets/application.enc.yaml
      format: yaml"""
    target_details = {
        "sops_file": {
            "description": "Store secret key/value pairs in one SOPS-encrypted file.",
            "config": {"key": "Optional on-disk key name override (defaults to Secret.name)"},
            "example": """targets:
  - provider: repo_secrets
    kind: sops_file
    config:
      key: APP_DB_PASSWORD""",
        }
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: SopsAuth | None = None,
    ):
        if auth is None:
            auth = SopsAuth((config or {}).get("auth", {}))
        super().__init__(name, config, auth)

    @property
    def provider_kind(self) -> str:
        return "sops"

    def get_supported_targets(self) -> list[str]:
        return ["sops_file"]

    def test_connection(self) -> tuple[bool, str | None]:
        if shutil.which("sops") is None:
            return False, "sops CLI not found in PATH"
        sops_file = self._get_sops_file()
        if sops_file is None:
            return False, "sops_file not configured"
        if sops_file.exists():
            try:
                self._read_sops(sops_file)
            except Exception as exc:
                return False, f"Failed to decrypt SOPS file '{sops_file}': {exc}"
        return True, f"SOPS provider ready (file: {sops_file})"

    def retrieve_secret(self, secret_name: str) -> str:
        sops_file = self._require_sops_file()
        if not sops_file.exists():
            raise ValueError(f"SOPS file not found: {sops_file}")
        data = self._read_sops(sops_file)
        if secret_name not in data:
            raise ValueError(f"Secret '{secret_name}' not found in sops file '{sops_file}'")
        return str(data[secret_name])

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        sops_file = self._require_sops_file()
        data: dict[str, str] = {}
        if sops_file.exists():
            data = self._read_sops(sops_file)
        data[secret_name] = secret_value
        self._write_sops(sops_file, data)
        return True

    def delete_secret(self, secret_name: str) -> bool:
        sops_file = self._require_sops_file()
        if not sops_file.exists():
            raise ValueError(f"SOPS file not found: {sops_file}")
        data = self._read_sops(sops_file)
        if secret_name not in data:
            return False
        del data[secret_name]
        self._write_sops(sops_file, data)
        return True

    def _get_sops_file(self) -> Path | None:
        sops_file = self.config.get("sops_file")
        return Path(sops_file) if sops_file else None

    def _require_sops_file(self) -> Path:
        sops_file = self._get_sops_file()
        if sops_file is None:
            raise ValueError("sops_file not configured")
        return sops_file

    def _sops_type(self) -> str:
        fmt = str(self.config.get("format", "yaml")).strip().lower()
        if fmt not in {"yaml", "json", "dotenv"}:
            raise ValueError(f"Unsupported format: {fmt}")
        return fmt

    def _read_sops(self, sops_file: Path) -> dict[str, str]:
        plain_text = self._run_sops(["--decrypt", str(sops_file)])
        fmt = self._sops_type()
        if fmt == "yaml":
            data = yaml.safe_load(plain_text) or {}
        elif fmt == "json":
            data = json.loads(plain_text) if plain_text.strip() else {}
        else:
            data = self._parse_dotenv(plain_text)
        if not isinstance(data, dict):
            raise ValueError(f"SOPS file must contain a {fmt} mapping at the top level")
        return {str(k): str(v) for k, v in data.items()}

    def _write_sops(self, sops_file: Path, data: dict[str, str]) -> None:
        fmt = self._sops_type()
        if fmt == "yaml":
            plain_text = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
            input_type = "yaml"
            output_type = "yaml"
        elif fmt == "json":
            plain_text = json.dumps(data, indent=2)
            input_type = "json"
            output_type = "json"
        else:
            plain_text = self._format_dotenv(data)
            input_type = "dotenv"
            output_type = "dotenv"
        encrypted = self._run_sops(
            ["--encrypt", "--input-type", input_type, "--output-type", output_type, "/dev/stdin"],
            input_text=plain_text,
        )
        sops_file.parent.mkdir(parents=True, exist_ok=True)
        sops_file.write_text(encrypted)

    def _run_sops(self, args: list[str], input_text: str | None = None) -> str:
        if shutil.which("sops") is None:
            raise ValueError("sops CLI not found in PATH")
        cmd = ["sops", *args]
        proc = subprocess.run(  # noqa: S603
            cmd,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip() or "unknown sops error"
            raise ValueError(stderr)
        return proc.stdout

    @staticmethod
    def _parse_dotenv(content: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
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
        name="sops",
        version="1.0.0",
        provider_class="secretzero.providers.sops:SopsProvider",
        generators={},
        targets={"sops_file": "secretzero.targets.sops_file:SopsFileTarget"},
        generator_kinds=[],
        target_kinds=["sops_file"],
        terraform_provider=None,
    )
