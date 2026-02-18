"""Secret synchronization engine."""

from typing import Any

from secretzero.generators import (
    RandomPasswordGenerator,
    RandomStringGenerator,
    ScriptGenerator,
    StaticGenerator,
)
from secretzero.lockfile import Lockfile
from secretzero.models import GeneratorKind, Secret, Secretfile, Template
from secretzero.targets import FileTarget

# Import providers


class SyncEngine:
    """Engine for synchronizing secrets from configuration to targets."""

    def __init__(
        self, secretfile: Secretfile, lockfile: Lockfile, hide_input: bool = False
    ) -> None:
        """Initialize sync engine.

        Args:
            secretfile: Loaded Secretfile configuration
            lockfile: Lockfile for tracking secrets
            hide_input: If True, mask user input when prompting for secrets
        """
        self.secretfile = secretfile
        self.lockfile = lockfile
        self.hide_input = hide_input
        self.generator_map = {
            GeneratorKind.RANDOM_PASSWORD: RandomPasswordGenerator,
            GeneratorKind.RANDOM_STRING: RandomStringGenerator,
            GeneratorKind.STATIC: StaticGenerator,
            GeneratorKind.SCRIPT: ScriptGenerator,
        }
        self._providers = {}
        self._initialize_providers()

    @staticmethod
    def _build_target_id(target_config) -> str:
        """Build a consistent target identifier.

        Args:
            target_config: Target configuration

        Returns:
            Target identifier string
        """
        provider = target_config.provider
        kind = target_config.kind

        # For file targets, use path as the identifier
        if kind == "file":
            identifier = target_config.config.get("path", "")
        # For most other targets, use name
        else:
            identifier = target_config.config.get("name", "")

        return f"{provider}/{kind}/{identifier}"

    def _initialize_providers(self) -> None:
        """Initialize providers from secretfile configuration."""
        if not self.secretfile.providers:
            return

        for provider_name, provider_config in self.secretfile.providers.items():
            try:
                # Convert Pydantic model to dict
                config_dict = provider_config.model_dump()
                provider = self._create_provider(provider_name, config_dict)
                if provider:
                    self._providers[provider_name] = provider
            except Exception:
                # Skip providers that can't be initialized
                pass

    def _create_provider(self, name: str, config: dict) -> Any | None:
        """Create a provider instance.

        Args:
            name: Provider name
            config: Provider configuration

        Returns:
            Provider instance or None
        """
        # Determine provider type from config or name
        provider_kind = config.get("kind", name)

        if provider_kind == "aws":
            try:
                from secretzero.providers.aws import AWSProvider

                return AWSProvider(name=name, config=config)
            except ImportError:
                return None
        elif provider_kind == "azure":
            try:
                from secretzero.providers.azure import AzureProvider

                return AzureProvider(name=name, config=config)
            except ImportError:
                return None
        elif provider_kind == "vault":
            try:
                from secretzero.providers.vault import VaultProvider

                return VaultProvider(name=name, config=config)
            except ImportError:
                return None
        elif provider_kind == "github":
            try:
                from secretzero.providers.github import GitHubProvider

                return GitHubProvider(name=name, config=config)
            except ImportError:
                return None
        elif provider_kind == "gitlab":
            try:
                from secretzero.providers.gitlab import GitLabProvider

                return GitLabProvider(name=name, config=config)
            except ImportError:
                return None
        elif provider_kind == "jenkins":
            try:
                from secretzero.providers.jenkins import JenkinsProvider

                return JenkinsProvider(name=name, config=config)
            except ImportError:
                return None
        elif provider_kind == "kubernetes":
            try:
                from secretzero.providers.kubernetes import KubernetesProvider

                return KubernetesProvider(name=name, config=config)
            except ImportError:
                return None

        return None

    def _get_provider(self, provider_name: str) -> Any | None:
        """Get a provider by name.

        Args:
            provider_name: Name of the provider

        Returns:
            Provider instance or None
        """
        return self._providers.get(provider_name)

    def sync(self, dry_run: bool = False, force_rotation: bool = False) -> dict[str, Any]:
        """Synchronize all secrets to their targets.

        Args:
            dry_run: If True, only simulate without making changes
            force_rotation: If True, regenerate secrets even if they exist

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
                result = self._sync_secret(secret, dry_run, force_rotation)
                results["secrets_processed"] += 1
                results["details"].append(result)

                if result["generated"]:
                    results["secrets_generated"] += 1
                if result["skipped"]:
                    results["secrets_skipped"] += 1
                if result["stored"]:
                    results["secrets_stored"] += 1
                if result.get("errors"):
                    results["errors"].extend(result["errors"])

            except Exception as e:
                error_msg = f"Error syncing secret '{secret.name}': {e}"
                results["errors"].append(error_msg)

        return results

    def _sync_secret(
        self, secret: Secret, dry_run: bool, force_rotation: bool = False
    ) -> dict[str, Any]:
        """Sync a single secret.

        Args:
            secret: Secret definition
            dry_run: If True, only simulate
            force_rotation: If True, regenerate even if exists

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
            "errors": [],
        }

        # Check if this is a template-based secret
        if secret.kind.startswith("templates."):
            template_name = secret.kind.replace("templates.", "")
            template = self.secretfile.templates.get(template_name)
            if template:
                return self._sync_template_secret(secret, template, dry_run, force_rotation)

        # Check if secret needs generation (one_time check)
        if secret.one_time and self.lockfile.has_secret(secret.name) and not force_rotation:
            result["skipped"] = True
            result["reason"] = "One-time secret already exists"
            return result

        # Check if secret exists in lockfile and has all targets tracked
        secret_exists = self.lockfile.has_secret(secret.name)
        lockfile_entry = self.lockfile.get_secret_info(secret.name) if secret_exists else None

        # Determine which targets need syncing
        tracked_targets = (
            set(lockfile_entry.targets.keys())
            if lockfile_entry and lockfile_entry.targets
            else set()
        )
        targets_to_sync = []

        for target_config in secret.targets:
            target_id = self._build_target_id(target_config)
            if force_rotation or target_id not in tracked_targets:
                targets_to_sync.append(target_config)

        # If no targets need syncing and secret exists, skip
        # Special case: if secret has no targets at all and doesn't exist, generate it
        if not targets_to_sync and (secret_exists or len(secret.targets) > 0):
            result["skipped"] = True
            result["reason"] = "All targets already synced"
            return result

        # Get or generate secret value
        secret_value = None

        # For partial sync (secret exists, not forcing), try to retrieve from existing target
        if secret_exists and not force_rotation and tracked_targets:
            for target_config in secret.targets:
                target_id = self._build_target_id(target_config)
                
                # Check if target is tracked (support old lockfile format for file targets)
                is_tracked = target_id in tracked_targets
                if not is_tracked and target_config.kind == "file":
                    # Check old format (with empty name instead of path)
                    old_target_id = f"{target_config.provider}/{target_config.kind}/"
                    is_tracked = old_target_id in tracked_targets
                
                if is_tracked:
                    # Try to retrieve from this target
                    secret_value = self._retrieve_from_target(secret.name, target_config)
                    if secret_value:
                        result["retrieved_from_existing"] = True
                        break

            if not secret_value:
                result["skipped"] = True
                result["reason"] = (
                    "Cannot retrieve existing value for partial sync. Use --force-rotation to regenerate."
                )
                result["errors"].append(
                    f"{secret.name}: Unable to retrieve from existing targets for partial sync"
                )
                return result

        # Generate new value if needed (full sync or force rotation)
        if not secret_value:
            env_var_name = secret.name.upper()
            secret_value = self._generate_secret_value(secret.kind, secret.config, env_var_name)
            result["generated"] = True

        # Store in targets (only targets that need syncing)
        if not dry_run:
            all_targets_ok = True
            for target_config in targets_to_sync:
                target_result = self._store_in_target(secret.name, secret_value, target_config)
                result["targets"].append(target_result)

                if target_result.get("status") in {"failed", "error", "unsupported"}:
                    all_targets_ok = False
                    message = target_result.get("message", "Target store failed")
                    result["errors"].append(
                        f"{secret.name} -> {target_result['provider']}/{target_result['kind']}: {message}"
                    )
                else:
                    # Track successful target stores
                    target_id = self._build_target_id(target_config)
                    self.lockfile.add_secret(
                        secret.name, secret_value, target_id=target_id, is_rotation=force_rotation
                    )

            # If secret was generated but has no targets, still add to lockfile
            if len(targets_to_sync) == 0 and result.get("generated"):
                self.lockfile.add_secret(
                    secret.name, secret_value, target_id=None, is_rotation=force_rotation
                )
                result["stored"] = True
            elif all_targets_ok:
                result["stored"] = True
        else:
            result["dry_run"] = True
            for target_config in targets_to_sync:
                result["targets"].append(
                    {
                        "provider": target_config.provider,
                        "kind": target_config.kind,
                        "status": "would_store",
                    }
                )

        return result

    def _sync_template_secret(
        self, secret: Secret, template: Template, dry_run: bool, force_rotation: bool = False
    ) -> dict[str, Any]:
        """Sync a template-based secret with multiple fields.

        Args:
            secret: Secret definition
            template: Template definition
            dry_run: If True, only simulate
            force_rotation: If True, regenerate even if exists

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
            "errors": [],
        }

        # Process each field in the template
        for field_name, field_def in template.fields.items():
            field_result = {
                "name": field_name,
                "generated": False,
                "stored": False,
                "targets": [],
                "errors": [],
            }

            # Combine secret and field targets
            all_targets = field_def.targets + template.targets
            field_secret_name = f"{secret.name}.{field_name}"

            # Check if field exists in lockfile
            field_exists = self.lockfile.has_secret(field_secret_name)
            lockfile_entry = (
                self.lockfile.get_secret_info(field_secret_name) if field_exists else None
            )

            # Determine which targets need syncing
            tracked_targets = (
                set(lockfile_entry.targets.keys())
                if lockfile_entry and lockfile_entry.targets
                else set()
            )
            targets_to_sync = []

            for target_config in all_targets:
                target_id = self._build_target_id(target_config)
                if force_rotation or target_id not in tracked_targets:
                    targets_to_sync.append(target_config)

            # If no targets need syncing, skip
            if not targets_to_sync:
                field_result["skipped"] = True
                result["fields"].append(field_result)
                continue

            # Get or generate field value
            field_value = None

            # For partial sync, try to retrieve from existing target
            if field_exists and not force_rotation and tracked_targets:
                for target_config in all_targets:
                    target_id = self._build_target_id(target_config)
                    
                    # Check if target is tracked (support old lockfile format for file targets)
                    is_tracked = target_id in tracked_targets
                    if not is_tracked and target_config.kind == "file":
                        # Check old format (with empty name instead of path)
                        old_target_id = f"{target_config.provider}/{target_config.kind}/"
                        is_tracked = old_target_id in tracked_targets
                    
                    if is_tracked:
                        field_value = self._retrieve_from_target(field_name, target_config)
                        if field_value:
                            field_result["retrieved_from_existing"] = True
                            break

                if not field_value:
                    field_result["skipped"] = True
                    field_result["errors"].append(
                        f"{field_secret_name}: Unable to retrieve from existing targets for partial sync"
                    )
                    result["fields"].append(field_result)
                    continue

            # Generate new value if needed
            if not field_value:
                env_var_name = f"{secret.name.upper()}_{field_name.upper()}"
                field_value = self._generate_secret_value(
                    field_def.generator.kind.value,
                    field_def.generator.config,
                    env_var_name,
                    field_description=field_def.description,
                )
                field_result["generated"] = True
                result["generated"] = True

            # Store in targets (only targets that need syncing)
            if not dry_run:
                all_targets_ok = True
                for target_config in targets_to_sync:
                    target_result = self._store_in_target(field_name, field_value, target_config)
                    field_result["targets"].append(target_result)

                    if target_result.get("status") in {"failed", "error", "unsupported"}:
                        all_targets_ok = False
                        message = target_result.get("message", "Target store failed")
                        field_result["errors"].append(
                            f"{field_secret_name} -> {target_result['provider']}/{target_result['kind']}: {message}"
                        )
                    else:
                        # Track successful target stores
                        target_id = self._build_target_id(target_config)
                        self.lockfile.add_secret(
                            field_secret_name, field_value, target_id=target_id
                        )

                if all_targets_ok:
                    field_result["stored"] = True
                    result["stored"] = True
                else:
                    result["errors"].extend(field_result["errors"])
            else:
                field_result["dry_run"] = True
                for target_config in targets_to_sync:
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
        self,
        kind: str,
        config: dict[str, Any],
        env_var_name: str,
        field_description: str | None = None,
    ) -> str:
        """Generate a secret value using the appropriate generator.

        Args:
            kind: Generator kind
            config: Generator configuration
            env_var_name: Environment variable name for fallback
            field_description: Optional field description for user prompts

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
        if self.hide_input:
            generator.hide_input = True
        return generator.generate_with_fallback(env_var_name, field_description=field_description)

    def _retrieve_from_target(self, secret_name: str, target_config: Any) -> str | None:
        """Retrieve a secret value from a target.

        Args:
            secret_name: Name of the secret
            target_config: Target configuration

        Returns:
            Secret value if found, None otherwise
        """
        try:
            # Local file targets
            if target_config.provider == "local" and target_config.kind == "file":
                target = FileTarget(target_config.config)
                return target.retrieve(secret_name)

            # AWS targets
            elif target_config.provider == "aws":
                provider = self._get_provider("aws")
                if not provider:
                    return None

                if target_config.kind == "ssm_parameter":
                    try:
                        from secretzero.targets.aws import SSMParameterTarget

                        target = SSMParameterTarget(provider, target_config.config)
                        return target.retrieve(secret_name)
                    except ImportError:
                        return None

                elif target_config.kind == "secrets_manager":
                    try:
                        from secretzero.targets.aws import SecretsManagerTarget

                        target = SecretsManagerTarget(provider, target_config.config)
                        return target.retrieve(secret_name)
                    except ImportError:
                        return None

            # Azure targets
            elif target_config.provider == "azure":
                provider = self._get_provider("azure")
                if not provider:
                    return None

                if target_config.kind == "key_vault":
                    try:
                        from secretzero.targets.azure import KeyVaultTarget

                        target = KeyVaultTarget(provider, target_config.config)
                        return target.retrieve(secret_name)
                    except ImportError:
                        return None

            # GCP targets
            elif target_config.provider == "gcp":
                provider = self._get_provider("gcp")
                if not provider:
                    return None

                if target_config.kind == "secret_manager":
                    try:
                        from secretzero.targets.gcp import SecretManagerTarget

                        target = SecretManagerTarget(provider, target_config.config)
                        return target.retrieve(secret_name)
                    except ImportError:
                        return None

            # Kubernetes targets
            elif target_config.provider == "kubernetes":
                provider = self._get_provider("kubernetes")
                if not provider:
                    return None

                if target_config.kind == "secret":
                    try:
                        from secretzero.targets.kubernetes import SecretTarget

                        target = SecretTarget(provider, target_config.config)
                        return target.retrieve(secret_name)
                    except ImportError:
                        return None

            return None

        except Exception:
            return None

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
            # Local file targets
            if target_config.provider == "local" and target_config.kind == "file":
                target = FileTarget(target_config.config)
                success = target.store(secret_name, secret_value)
                result["status"] = "stored" if success else "failed"

            # AWS targets
            elif target_config.provider == "aws":
                provider = self._get_provider("aws")
                if not provider:
                    result["status"] = "error"
                    result["message"] = "AWS provider not initialized"
                    return result

                if target_config.kind == "ssm_parameter":
                    try:
                        from secretzero.targets.aws import SSMParameterTarget

                        target = SSMParameterTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "boto3 not installed. Install with: pip install secretzero[aws]"
                        )

                elif target_config.kind == "secrets_manager":
                    try:
                        from secretzero.targets.aws import SecretsManagerTarget

                        target = SecretsManagerTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "boto3 not installed. Install with: pip install secretzero[aws]"
                        )
                else:
                    result["status"] = "unsupported"
                    result["message"] = f"AWS target kind '{target_config.kind}' not supported"

            # Azure targets
            elif target_config.provider == "azure":
                provider = self._get_provider("azure")
                if not provider:
                    result["status"] = "error"
                    result["message"] = "Azure provider not initialized"
                    return result

                if target_config.kind == "key_vault":
                    try:
                        from secretzero.targets.azure import KeyVaultTarget

                        target = KeyVaultTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "Azure SDK not installed. Install with: pip install secretzero[azure]"
                        )
                else:
                    result["status"] = "unsupported"
                    result["message"] = f"Azure target kind '{target_config.kind}' not supported"

            # Vault targets
            elif target_config.provider == "vault":
                provider = self._get_provider("vault")
                if not provider:
                    result["status"] = "error"
                    result["message"] = "Vault provider not initialized"
                    return result

                if target_config.kind == "kv":
                    try:
                        from secretzero.targets.vault import VaultKVTarget

                        target = VaultKVTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "hvac not installed. Install with: pip install secretzero[vault]"
                        )
                else:
                    result["status"] = "unsupported"
                    result["message"] = f"Vault target kind '{target_config.kind}' not supported"

            # GitHub targets
            elif target_config.provider == "github":
                provider = self._get_provider("github")
                if not provider:
                    result["status"] = "error"
                    result["message"] = "GitHub provider not initialized"
                    return result

                if target_config.kind == "github_secret":
                    try:
                        from secretzero.targets.github import GitHubSecretTarget

                        target = GitHubSecretTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "PyGithub not installed. Install with: pip install secretzero[github]"
                        )
                else:
                    result["status"] = "unsupported"
                    result["message"] = f"GitHub target kind '{target_config.kind}' not supported"

            # GitLab targets
            elif target_config.provider == "gitlab":
                provider = self._get_provider("gitlab")
                if not provider:
                    result["status"] = "error"
                    result["message"] = "GitLab provider not initialized"
                    return result

                if target_config.kind == "gitlab_variable":
                    try:
                        from secretzero.targets.gitlab import GitLabVariableTarget

                        target = GitLabVariableTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "python-gitlab not installed. Install with: pip install secretzero[gitlab]"
                        )
                else:
                    result["status"] = "unsupported"
                    result["message"] = f"GitLab target kind '{target_config.kind}' not supported"

            # Jenkins targets
            elif target_config.provider == "jenkins":
                provider = self._get_provider("jenkins")
                if not provider:
                    result["status"] = "error"
                    result["message"] = "Jenkins provider not initialized"
                    return result

                if target_config.kind == "jenkins_credential":
                    try:
                        from secretzero.targets.jenkins import JenkinsCredentialTarget

                        target = JenkinsCredentialTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "python-jenkins not installed. Install with: pip install secretzero[jenkins]"
                        )
                else:
                    result["status"] = "unsupported"
                    result["message"] = f"Jenkins target kind '{target_config.kind}' not supported"

            # Kubernetes targets
            elif target_config.provider == "kubernetes":
                provider = self._get_provider("kubernetes")
                if not provider:
                    result["status"] = "error"
                    result["message"] = "Kubernetes provider not initialized"
                    return result

                if target_config.kind == "kubernetes_secret":
                    try:
                        from secretzero.targets.kubernetes import KubernetesSecretTarget

                        target = KubernetesSecretTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "kubernetes not installed. Install with: pip install secretzero[kubernetes]"
                        )
                elif target_config.kind == "external_secret":
                    try:
                        from secretzero.targets.kubernetes import ExternalSecretTarget

                        target = ExternalSecretTarget(provider, target_config.config)
                        success = target.store(secret_name, secret_value)
                        result["status"] = "stored" if success else "failed"
                    except ImportError:
                        result["status"] = "error"
                        result["message"] = (
                            "kubernetes not installed. Install with: pip install secretzero[kubernetes]"
                        )
                else:
                    result["status"] = "unsupported"
                    result["message"] = (
                        f"Kubernetes target kind '{target_config.kind}' not supported"
                    )

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
            "targets": [{"provider": t.provider, "kind": t.kind} for t in secret.targets],
            "exists_in_lockfile": lock_entry is not None,
        }

        if lock_entry:
            info["created_at"] = lock_entry.created_at
            info["updated_at"] = lock_entry.updated_at
            info["hash"] = lock_entry.hash

        return info
