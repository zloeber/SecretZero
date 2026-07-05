"""Drift detection for secrets."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from secretzero.config import ConfigLoader
from secretzero.environment_resolution import apply_target_profile, resolve_environment_context
from secretzero.local_secrets import (
    local_lockfile_path,
    resolve_lockfile_for_secret,
)
from secretzero.lockfile import Lockfile
from secretzero.models import Secret, TargetConfig
from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY


class DriftStatus(BaseModel):
    """Drift detection status."""

    secret_name: str
    has_drift: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class DriftDetector:
    """Detect drift between lockfile and actual targets."""

    def __init__(
        self,
        secretfile_path: Path,
        lockfile_path: Path,
        *,
        environment: str | None = None,
        runtime_var_files: list[Path] | None = None,
    ):
        """Initialize drift detector.

        Args:
            secretfile_path: Path to Secretfile
            lockfile_path: Path to lockfile
            environment: Optional named environment profile
            runtime_var_files: Optional runtime var-file overrides
        """
        self.secretfile_path = secretfile_path
        self.lockfile_path = lockfile_path
        self.local_lockfile_path = local_lockfile_path(lockfile_path)

        loader = ConfigLoader()
        base_secretfile = loader.load_file(secretfile_path)
        env_ctx = resolve_environment_context(
            secretfile=base_secretfile,
            secretfile_path=secretfile_path,
            environment=environment,
            runtime_var_files=runtime_var_files,
            runtime_lockfile=str(lockfile_path),
        )
        self.config = loader.load_file(
            secretfile_path, var_files=env_ctx.resolved_var_files or None
        )
        self.config = apply_target_profile(self.config, env_ctx.resolved_target_profile)
        self.environment_context = env_ctx
        self.lockfile = Lockfile.load(lockfile_path)
        self.local_lockfile = Lockfile.load(self.local_lockfile_path)

    def _lockfile_for(self, secret: Secret) -> Lockfile:
        return resolve_lockfile_for_secret(self.lockfile, self.local_lockfile, secret)

    def check_drift(self, secret_name: str | None = None) -> list[DriftStatus]:
        """Check for drift in secrets.

        Args:
            secret_name: Optional specific secret to check

        Returns:
            List of drift status results
        """
        results = []

        # Filter secrets to check
        secrets_to_check = self.config.secrets
        if secret_name:
            secrets_to_check = [s for s in self.config.secrets if s.name == secret_name]

        for secret in secrets_to_check:
            result = self._check_secret_drift(secret)
            results.append(result)

        return results

    def _check_secret_drift(self, secret: Secret) -> DriftStatus:
        """Check drift for a single secret.

        Args:
            secret: Secret to check

        Returns:
            Drift status
        """
        if secret.kind.startswith("templates."):
            return self._check_template_secret_drift(secret)

        targets = self._format_targets(secret.targets)
        secret_lockfile = self._lockfile_for(secret)

        # Check if secret exists in lockfile
        if not secret_lockfile.has_secret(secret.name):
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Secret not found in lockfile",
                details={
                    "reason": "never_generated",
                    "targets": targets,
                },
            )

        lockfile_entry = secret_lockfile.get_secret_info(secret.name)
        if not lockfile_entry:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Secret entry corrupted in lockfile",
                details={"reason": "corrupted"},
            )

        if secret.kind == "entra-agent-blueprint":
            result = self._check_entra_blueprint_drift(secret)
            if result is not None:
                return result

        secretfile_content = (
            self.secretfile_path.read_text() if self.secretfile_path.exists() else None
        )
        from secretzero.lockfile_state import definition_drift_for_secret
        from secretzero.secret_definition_hash import (
            hash_secret_definition,
            stored_definition_hash,
        )

        if definition_drift_for_secret(
            secret_lockfile,
            secret,
            secretfile=self.config,
            secretfile_path=self.secretfile_path,
            secretfile_content=secretfile_content,
        ):
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Secretfile definition changed since last sync",
                details={
                    "reason": "definition_changed",
                    "stored_definition_hash": stored_definition_hash(secret_lockfile, secret),
                    "current_definition_hash": hash_secret_definition(
                        secret, secretfile=self.config
                    ),
                    "targets": targets,
                },
            )

        # Check if we can verify drift against targets
        # For now, we'll focus on file targets which we can read
        file_targets = self._get_file_targets(secret)

        if not file_targets:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=False,
                message="No verifiable targets (file targets only)",
                details={
                    "reason": "no_file_targets",
                    "lockfile_hash": lockfile_entry.hash,
                    "targets": targets,
                },
            )

        # Check file targets for drift
        drift_detected = False
        drift_details = {}

        for target in file_targets:
            target_path = Path(target.config.get("path", ""))
            if not target_path.exists():
                drift_detected = True
                drift_details[str(target_path)] = "file_missing"
                continue

            # For now, we mark as "needs_verification" since we can't read
            # the actual secret value from the file without knowing the format
            # and key name
            drift_details[str(target_path)] = "exists"

        if drift_detected:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Target files missing",
                details=drift_details,
            )

        return DriftStatus(
            secret_name=secret.name,
            has_drift=False,
            message="No drift detected in file targets",
            details=drift_details,
        )

    def _check_entra_blueprint_drift(self, secret: Secret) -> DriftStatus | None:
        """Provider-aware drift check for Entra agent blueprints."""
        provider_alias = str(secret.config.get("provider", "")).strip()
        if not provider_alias:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Entra blueprint config missing provider alias",
                details={"reason": "missing_provider"},
            )
        provider_cfg = self.config.providers.get(provider_alias)
        if provider_cfg is None:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message=f"Provider '{provider_alias}' not found in Secretfile",
                details={"reason": "unknown_provider"},
            )

        provider_kind = provider_cfg.kind or provider_alias
        provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_kind)
        if provider_class is None:
            return None

        try:
            provider = provider_class(name=provider_alias, config=provider_cfg.model_dump())
            display_name = str(
                secret.config.get("spec", {}).get("blueprint", {}).get("display_name", "")
            )
            if not display_name:
                return DriftStatus(
                    secret_name=secret.name,
                    has_drift=True,
                    message="Entra blueprint spec missing blueprint.display_name",
                    details={"reason": "missing_display_name"},
                )
            state = provider.retrieve_blueprint_state(display_name)
            return DriftStatus(
                secret_name=secret.name,
                has_drift=False,
                message="Entra blueprint reachable via provider state lookup",
                details={"provider_state": state},
            )
        except Exception as e:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message=f"Entra blueprint provider-state drift check failed: {e}",
                details={"reason": "provider_state_lookup_failed"},
            )

    def _check_template_secret_drift(self, secret: Secret) -> DriftStatus:
        """Check drift for a template-based secret.

        Args:
            secret: Template-based secret

        Returns:
            Drift status
        """
        template_name = secret.kind.split(".", 1)[1]
        template = self.config.templates.get(template_name)

        if not template:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Template not found",
                details={"template": template_name},
            )

        field_details: dict[str, Any] = {}
        any_missing = False
        any_present = False

        for field_name, field_def in template.fields.items():
            field_secret_name = f"{secret.name}.{field_name}"
            exists_in_lockfile = self.lockfile.has_secret(field_secret_name)
            any_present = any_present or exists_in_lockfile
            any_missing = any_missing or not exists_in_lockfile

            targets = self._format_targets(field_def.targets + template.targets)
            field_details[field_name] = {
                "exists_in_lockfile": exists_in_lockfile,
                "targets": targets,
            }

        if not any_present:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Template fields not found in lockfile",
                details={
                    "reason": "never_generated",
                    "fields": field_details,
                },
            )

        if any_missing:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Some template fields missing in lockfile",
                details={
                    "reason": "partial_generation",
                    "fields": field_details,
                },
            )

        return DriftStatus(
            secret_name=secret.name,
            has_drift=False,
            message="Template fields found in lockfile",
            details={
                "reason": "tracked",
                "fields": field_details,
            },
        )

    def _get_file_targets(self, secret: Secret) -> list[TargetConfig]:
        """Get file targets for a secret.

        Args:
            secret: Secret to get targets for

        Returns:
            List of file target configs
        """
        return [t for t in secret.targets if t.kind == "file"]

    @staticmethod
    def _format_targets(targets: list[TargetConfig]) -> list[str]:
        """Format targets for display.

        Args:
            targets: List of target configs

        Returns:
            List of formatted target strings
        """
        return [f"{t.provider}/{t.kind}" for t in targets]

    def auto_remediate(self, secret_name: str | None = None) -> dict[str, Any]:
        """Auto-remediate drift by regenerating secrets.

        Args:
            secret_name: Optional specific secret to remediate

        Returns:
            Remediation results
        """
        # Check for drift first
        drift_results = self.check_drift(secret_name)

        secrets_with_drift = [r for r in drift_results if r.has_drift]

        if not secrets_with_drift:
            return {
                "remediated": 0,
                "message": "No drift detected",
            }

        # For auto-remediation, we'd need to call the sync engine
        # This is a placeholder for the actual implementation
        return {
            "remediated": 0,
            "message": "Auto-remediation requires running 'secretzero sync --force'",
            "secrets_with_drift": [r.secret_name for r in secrets_with_drift],
        }
