"""Secret synchronization engine."""

from pathlib import Path
from typing import Any

from secretzero.config import ConfigLoader
from secretzero.generators import (
    RandomPasswordGenerator,
    RandomStringGenerator,
    ScriptGenerator,
    StaticGenerator,
)
from secretzero.lockfile import Lockfile
from secretzero.models import GeneratorKind, Secret, Secretfile, Template
from secretzero.targets import FileTarget


class SyncEngine:
    """Engine for synchronizing secrets from configuration to targets."""

    def __init__(self, secretfile: Secretfile, lockfile: Lockfile) -> None:
        """Initialize sync engine.

        Args:
            secretfile: Loaded Secretfile configuration
            lockfile: Lockfile for tracking secrets
        """
        self.secretfile = secretfile
        self.lockfile = lockfile
        self.generator_map = {
            GeneratorKind.RANDOM_PASSWORD: RandomPasswordGenerator,
            GeneratorKind.RANDOM_STRING: RandomStringGenerator,
            GeneratorKind.STATIC: StaticGenerator,
            GeneratorKind.SCRIPT: ScriptGenerator,
        }

    def sync(self, dry_run: bool = False) -> dict[str, Any]:
        """Synchronize all secrets to their targets.

        Args:
            dry_run: If True, only simulate without making changes

        Returns:
            Dictionary with sync results and statistics
        """
        results = {
            "secrets_processed": 0,
            "secrets_generated": 0,
            "secrets_skipped": 0,
            "secrets_stored": 0,
            "errors": [],
            "details": [],
        }

        for secret in self.secretfile.secrets:
            try:
                result = self._sync_secret(secret, dry_run)
                results["secrets_processed"] += 1
                results["details"].append(result)

                if result["generated"]:
                    results["secrets_generated"] += 1
                if result["skipped"]:
                    results["secrets_skipped"] += 1
                if result["stored"]:
                    results["secrets_stored"] += 1

            except Exception as e:
                error_msg = f"Error syncing secret '{secret.name}': {e}"
                results["errors"].append(error_msg)

        return results

    def _sync_secret(self, secret: Secret, dry_run: bool) -> dict[str, Any]:
        """Sync a single secret.

        Args:
            secret: Secret definition
            dry_run: If True, only simulate

        Returns:
            Dictionary with sync details for this secret
        """
        result = {
            "name": secret.name,
            "kind": secret.kind,
            "generated": False,
            "skipped": False,
            "stored": False,
            "targets": [],
        }

        # Check if this is a template-based secret
        if secret.kind.startswith("templates."):
            template_name = secret.kind.replace("templates.", "")
            template = self.secretfile.templates.get(template_name)
            if template:
                return self._sync_template_secret(secret, template, dry_run)

        # Check if secret needs generation (one_time check)
        if secret.one_time and self.lockfile.has_secret(secret.name):
            result["skipped"] = True
            result["reason"] = "One-time secret already exists"
            return result

        # Generate secret value
        env_var_name = secret.name.upper()
        secret_value = self._generate_secret_value(
            secret.kind, secret.config, env_var_name
        )
        result["generated"] = True

        # Check if value has changed
        if not self.lockfile.should_update(secret.name, secret_value):
            result["skipped"] = True
            result["reason"] = "Secret value unchanged"
            return result

        # Store in targets
        if not dry_run:
            for target_config in secret.targets:
                target_result = self._store_in_target(
                    secret.name, secret_value, target_config
                )
                result["targets"].append(target_result)

            # Update lockfile
            self.lockfile.add_secret(secret.name, secret_value)
            result["stored"] = True
        else:
            result["dry_run"] = True
            for target_config in secret.targets:
                result["targets"].append(
                    {
                        "provider": target_config.provider,
                        "kind": target_config.kind,
                        "status": "would_store",
                    }
                )

        return result

    def _sync_template_secret(
        self, secret: Secret, template: Template, dry_run: bool
    ) -> dict[str, Any]:
        """Sync a template-based secret with multiple fields.

        Args:
            secret: Secret definition
            template: Template definition
            dry_run: If True, only simulate

        Returns:
            Dictionary with sync details
        """
        result = {
            "name": secret.name,
            "kind": secret.kind,
            "template": True,
            "fields": [],
            "generated": False,
            "stored": False,
            "skipped": False,
        }

        # Process each field in the template
        for field_name, field_def in template.fields.items():
            field_result = {
                "name": field_name,
                "generated": False,
                "stored": False,
                "targets": [],
            }

            # Build environment variable name
            env_var_name = f"{secret.name.upper()}_{field_name.upper()}"

            # Generate field value
            field_value = self._generate_secret_value(
                field_def.generator.kind.value,
                field_def.generator.config,
                env_var_name,
            )
            field_result["generated"] = True
            result["generated"] = True

            # Combine secret and field targets
            all_targets = field_def.targets + template.targets
            field_secret_name = f"{secret.name}.{field_name}"

            # Store in targets
            if not dry_run:
                for target_config in all_targets:
                    target_result = self._store_in_target(
                        field_name, field_value, target_config
                    )
                    field_result["targets"].append(target_result)

                # Update lockfile
                self.lockfile.add_secret(field_secret_name, field_value)
                field_result["stored"] = True
                result["stored"] = True
            else:
                field_result["dry_run"] = True
                for target_config in all_targets:
                    field_result["targets"].append(
                        {
                            "provider": target_config.provider,
                            "kind": target_config.kind,
                            "status": "would_store",
                        }
                    )

            result["fields"].append(field_result)

        return result

    def _generate_secret_value(
        self, kind: str, config: dict[str, Any], env_var_name: str
    ) -> str:
        """Generate a secret value using the appropriate generator.

        Args:
            kind: Generator kind
            config: Generator configuration
            env_var_name: Environment variable name for fallback

        Returns:
            Generated secret value

        Raises:
            ValueError: If generator kind is unknown
        """
        # Map string kinds to enum values
        if kind == "random_password":
            generator_class = RandomPasswordGenerator
        elif kind == "random_string":
            generator_class = RandomStringGenerator
        elif kind == "static":
            generator_class = StaticGenerator
        elif kind == "script":
            generator_class = ScriptGenerator
        else:
            raise ValueError(f"Unknown generator kind: {kind}")

        generator = generator_class(config)
        return generator.generate_with_fallback(env_var_name)

    def _store_in_target(
        self, secret_name: str, secret_value: str, target_config: Any
    ) -> dict[str, Any]:
        """Store a secret in a target.

        Args:
            secret_name: Name of the secret
            secret_value: Value to store
            target_config: Target configuration

        Returns:
            Dictionary with storage result
        """
        result = {
            "provider": target_config.provider,
            "kind": target_config.kind,
            "status": "unknown",
        }

        try:
            # Currently only support local file targets
            if target_config.provider == "local" and target_config.kind == "file":
                target = FileTarget(target_config.config)
                success = target.store(secret_name, secret_value)
                result["status"] = "stored" if success else "failed"
            else:
                result["status"] = "unsupported"
                result["message"] = f"Provider '{target_config.provider}' not yet implemented"

        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)

        return result

    def get_secret_info(self, secret_name: str) -> dict[str, Any] | None:
        """Get information about a specific secret.

        Args:
            secret_name: Name of the secret

        Returns:
            Dictionary with secret information or None if not found
        """
        # Find secret in configuration
        secret = None
        for s in self.secretfile.secrets:
            if s.name == secret_name:
                secret = s
                break

        if not secret:
            return None

        # Get lockfile entry
        lock_entry = self.lockfile.secrets.get(secret_name)

        info = {
            "name": secret.name,
            "kind": secret.kind,
            "one_time": secret.one_time,
            "rotation_period": secret.rotation_period,
            "targets": [
                {"provider": t.provider, "kind": t.kind} for t in secret.targets
            ],
            "exists_in_lockfile": lock_entry is not None,
        }

        if lock_entry:
            info["created_at"] = lock_entry.created_at
            info["updated_at"] = lock_entry.updated_at
            info["hash"] = lock_entry.hash

        return info
