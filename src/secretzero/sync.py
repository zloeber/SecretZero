"""Secret synchronization engine."""

from pathlib import Path
from typing import Any

from secretzero.bundles import get_bundle_registry
from secretzero.generators.base import BaseGenerator
from secretzero.lockfile import Lockfile
from secretzero.models import AgentInstructions, Secret, Secretfile, Template

# Import providers


class SyncEngine:
    """Engine for synchronizing secrets from configuration to targets."""

    def __init__(
        self,
        secretfile: Secretfile,
        lockfile: Lockfile,
        secretfile_path: Path | None = None,
        secretfile_content: str | None = None,
        hide_input: bool = True,
        prompt_on_empty: bool = True,
    ) -> None:
        """Initialize sync engine.

        Args:
            secretfile: Loaded Secretfile configuration
            lockfile: Lockfile for tracking secrets
            secretfile_path: Path to the Secretfile (for tracking)
            secretfile_content: Raw content of the Secretfile (for change detection)
            hide_input: If True, mask user input when prompting for secrets (default: True)
            prompt_on_empty: If True, prompt for values when empty/unresolved (default: True)
        """
        self.secretfile = secretfile
        self.lockfile = lockfile
        self.secretfile_path = secretfile_path
        self.secretfile_content = secretfile_content
        self.hide_input = hide_input
        self.prompt_on_empty = prompt_on_empty
        self._bundle_registry = get_bundle_registry()
        self._providers: dict[str, Any] = {}
        self._template_targets: dict[str, Any] = {}  # Track template targets and their secrets
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
        """Create a provider instance using the bundle registry.

        Args:
            name: Provider name
            config: Provider configuration

        Returns:
            Provider instance or None
        """
        provider_kind = config.get("kind", name)
        provider_class = self._bundle_registry.get_provider_class(provider_kind)
        if provider_class is not None:
            try:
                return provider_class(name=name, config=config)
            except Exception:
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

    def _validate_target_access(self) -> dict[str, Any]:
        """Validate that at least one target can be accessed.

        Tests connection to all providers used by targets.

        Returns:
            Dictionary with validation results:
                - accessible_count: Number of accessible providers
                - total_count: Total number of unique providers
                - results: List of tuples (provider_name, success, error_msg)
        """
        # Collect unique providers from all targets
        provider_names = set()
        for secret in self.secretfile.secrets:
            for target in secret.targets:
                provider_names.add(target.provider)

        # Test connection to each provider
        results = []
        accessible_count = 0

        for provider_name in provider_names:
            # Local file targets don't require authentication
            if provider_name == "local":
                results.append((provider_name, True, None))
                accessible_count += 1
                continue

            provider = self._get_provider(provider_name)
            if provider is None:
                results.append((provider_name, False, "Provider not initialized"))
                continue

            # Test connection
            try:
                success, error_msg = provider.test_connection()
                results.append((provider_name, success, error_msg))
                if success:
                    accessible_count += 1
            except Exception as e:
                results.append((provider_name, False, str(e)))

        return {
            "accessible_count": accessible_count,
            "total_count": len(provider_names),
            "results": results,
        }

    def sync(
        self,
        dry_run: bool = False,
        force_rotation: bool = False,
        secret_names: list[str] | None = None,
        ignore_foreign_context_targets: bool = False,
    ) -> dict[str, Any]:
        """Synchronize all secrets to their targets.

        Args:
            dry_run: If True, only simulate without making changes
            force_rotation: If True, regenerate secrets even if they exist
            secret_names: If provided, only sync secrets with these names

        Returns:
            Dictionary with sync results and statistics

        Raises:
            RuntimeError: If no targets can be accessed
        """
        # Validate target access before generating secrets
        # Only validate if there are actual targets configured
        validation = self._validate_target_access()
        if validation["total_count"] > 0 and validation["accessible_count"] == 0:
            error_details = []
            for provider_name, success, error_msg in validation["results"]:
                if error_msg:
                    error_details.append(f"  • {provider_name}: {error_msg}")
                else:
                    error_details.append(f"  • {provider_name}: Connection failed")

            error_message = (
                f"Cannot sync secrets: No accessible targets found.\n"
                f"Tested {validation['total_count']} provider(s):\n" + "\n".join(error_details)
            )
            raise RuntimeError(error_message)

        results = {
            "secrets_processed": 0,
            "secrets_generated": 0,
            "secrets_skipped": 0,
            "secrets_stored": 0,
            "errors": [],
            "details": [],
            "secretfile_changed": False,
        }

        # Track secretfile for change detection (if tracking info provided)
        if self.secretfile_path and self.secretfile_content:
            secretfile_changed = self.lockfile.secretfile_changed(
                self.secretfile_path, self.secretfile_content
            )
            results["secretfile_changed"] = secretfile_changed

            # Track the secretfile in the lockfile
            if not dry_run:
                self.lockfile.track_secretfile(self.secretfile_path, self.secretfile_content)

        # Filter secrets by name if specified
        secrets_to_sync = self.secretfile.secrets
        if secret_names:
            secrets_to_sync = [s for s in self.secretfile.secrets if s.name in secret_names]
            # Warn about secrets that don't exist
            found_names = {s.name for s in secrets_to_sync}
            missing_names = set(secret_names) - found_names
            if missing_names:
                results["errors"].append(
                    f"Warning: Secrets not found in Secretfile: {', '.join(sorted(missing_names))}"
                )

        for secret in secrets_to_sync:
            try:
                result = self._sync_secret(
                    secret,
                    dry_run,
                    force_rotation,
                    ignore_foreign_context_targets=ignore_foreign_context_targets,
                )
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

        # Render template targets after all secrets are synced
        if not dry_run:
            template_render_errors = self._render_template_targets()
            if template_render_errors:
                results["errors"].extend(template_render_errors)

        return results

    def _sync_secret(
        self,
        secret: Secret,
        dry_run: bool,
        force_rotation: bool = False,
        ignore_foreign_context_targets: bool = False,
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
                return self._sync_template_secret(
                    secret,
                    template,
                    dry_run,
                    force_rotation,
                    ignore_foreign_context_targets=ignore_foreign_context_targets,
                )

        # Check if secret needs generation (one_time check)
        if secret.one_time and self.lockfile.has_secret(secret.name) and not force_rotation:
            result["skipped"] = True
            result["reason"] = "One-time secret already exists"
            return result

        # Check if secret exists in lockfile and has all targets tracked
        secret_exists = self.lockfile.has_secret(secret.name)
        lockfile_entry = self.lockfile.get_secret_info(secret.name) if secret_exists else None

        # Determine which targets need syncing
        if lockfile_entry and lockfile_entry.targets and not ignore_foreign_context_targets:
            tracked_targets = set(lockfile_entry.targets.keys())
        else:
            # When ignoring foreign contexts, treat as if no targets have been synced yet
            tracked_targets = set()
        targets_to_sync = []

        for target_config in secret.targets:
            target_id = self._build_target_id(target_config)
            needs_sync = force_rotation or target_id not in tracked_targets

            # For file targets, also check if the file actually exists
            if (
                not needs_sync
                and target_config.provider == "local"
                and target_config.kind == "file"
            ):
                file_path = Path(target_config.config.get("path", ""))
                if not file_path.exists():
                    needs_sync = True  # File missing, needs to be recreated

            if needs_sync:
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
            secret_value = self._generate_secret_value(
                secret.kind,
                secret.config,
                env_var_name,
                field_description=f"Secret: {secret.name}",
                agent_instructions=secret.agent_instructions,
            )
            result["generated"] = True

        # Store in targets (only targets that need syncing)
        if not dry_run:
            # all_targets_ok = True
            any_target_stored = False
            for target_config in targets_to_sync:
                target_result = self._store_in_target(secret.name, secret_value, target_config)
                result["targets"].append(target_result)

                if target_result.get("status") in {"failed", "error", "unsupported"}:
                    # all_targets_ok = False
                    message = target_result.get("message", "Target store failed")
                    result["errors"].append(
                        f"{secret.name} -> {target_result['provider']}/{target_result['kind']}: {message}"
                    )
                else:
                    # Track successful target stores
                    any_target_stored = True
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
            elif any_target_stored:
                # Mark as stored if at least one target succeeded
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
        self,
        secret: Secret,
        template: Template,
        dry_run: bool,
        force_rotation: bool = False,
        ignore_foreign_context_targets: bool = False,
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
            if lockfile_entry and lockfile_entry.targets and not ignore_foreign_context_targets:
                tracked_targets = set(lockfile_entry.targets.keys())
            else:
                tracked_targets = set()
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

    def _resolve_provider_in_config(
        self, generator_class: type, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Inject a live provider instance into *config* if the generator needs one.

        Generator classes that require a provider instance declare two class
        attributes:

        * ``PROVIDER_CONFIG_KEY`` – the ``config`` key that holds the provider
          *name* string (defaults to ``"provider"``).
        * ``PROVIDER_INJECTION_KEY`` – the ``config`` key under which the
          resolved provider *instance* should be injected.

        When the resolved provider is not found the config is returned
        unchanged; the generator's own ``generate()`` method will raise an
        appropriate error at generation time.

        Args:
            generator_class: The generator class about to be instantiated.
            config: Current generator config dict.

        Returns:
            Possibly-augmented config dict.
        """
        provider_config_key: str | None = getattr(generator_class, "PROVIDER_CONFIG_KEY", None)
        provider_injection_key: str | None = getattr(
            generator_class, "PROVIDER_INJECTION_KEY", None
        )

        if not provider_config_key or not provider_injection_key:
            return config

        provider_name = config.get(provider_config_key)
        if not provider_name or not isinstance(provider_name, str):
            return config

        provider = self._get_provider(provider_name)
        if provider is None:
            return config

        return {**config, provider_injection_key: provider}

    def _generate_secret_value(
        self,
        kind: str,
        config: dict[str, Any],
        env_var_name: str,
        field_description: str | None = None,
        agent_instructions: AgentInstructions | None = None,
    ) -> str:
        """Generate a secret value using the bundle registry.

        Looks up the generator class for *kind* in the bundle registry,
        optionally injects a live provider instance (for generators that
        declare ``PROVIDER_CONFIG_KEY`` / ``PROVIDER_INJECTION_KEY``), and
        delegates to :meth:`~secretzero.generators.base.BaseGenerator.generate_with_fallback`.

        When *agent_instructions* are provided (from the Secretfile
        ``agent_instructions`` block) they are attached to the generator so
        they take precedence over any built-in instructions.  If generation
        fails, the effective instructions (user-defined or built-in) are
        printed to the console before the exception is re-raised.

        Args:
            kind: Generator kind string (e.g. ``"random_password"``).
            config: Generator configuration dict from the Secretfile.
            env_var_name: Environment variable name checked before generation.
            field_description: Optional human-readable label for user prompts.
            agent_instructions: Optional Secretfile-defined retrieval instructions
                that override the generator's built-in manual instructions.

        Returns:
            Generated secret value string.

        Raises:
            ValueError: If *kind* is not registered in the bundle registry.
        """
        generator_class = self._bundle_registry.get_generator_class(kind)
        if generator_class is None:
            raise ValueError(
                f"Unknown generator kind: '{kind}'. "
                f"Available kinds: {', '.join(self._bundle_registry.list_generator_kinds())}"
            )

        # Inject provider instance for generators that require one
        resolved_config = self._resolve_provider_in_config(generator_class, config)

        # Validate that provider-backed generators received their provider.
        # When the provider is missing, try to show manual instructions before
        # raising so the user knows how to obtain the secret value by hand.
        injection_key: str | None = getattr(generator_class, "PROVIDER_INJECTION_KEY", None)
        if injection_key and resolved_config.get(injection_key) is None:
            config_key: str = getattr(generator_class, "PROVIDER_CONFIG_KEY", "provider")
            provider_name = config.get(config_key, kind)
            if self._get_provider(provider_name) is None:
                # Attempt to instantiate the generator without its provider so we
                # can call get_manual_instructions().  Some generators (e.g.
                # github_pat) can be created without a resolved provider instance;
                # others (e.g. provider_backed) cannot, in which case we simply
                # skip the instructions display.
                effective_instructions: AgentInstructions | None = agent_instructions
                if effective_instructions is None:
                    try:
                        _tmp_gen = generator_class(resolved_config)
                        effective_instructions = _tmp_gen.get_manual_instructions()
                    except Exception:
                        pass  # Generator cannot be instantiated without its provider
                if effective_instructions is not None:
                    BaseGenerator._display_manual_instructions(effective_instructions)
                raise ValueError(
                    f"'{kind}' generator requires provider '{provider_name}' "
                    f"to be configured in the Secretfile providers section."
                )

        generator = generator_class(resolved_config)
        if self.hide_input:
            generator.hide_input = True

        # Allow generators to opt in to prompt_on_empty control
        if hasattr(generator, "prompt_on_empty"):
            generator.prompt_on_empty = self.prompt_on_empty

        # Attach Secretfile-defined instructions so they take precedence over
        # the generator's built-in defaults when prompting or on failure.
        if agent_instructions is not None:
            generator.manual_instructions = agent_instructions

        try:
            return generator.generate_with_fallback(
                env_var_name, field_description=field_description
            )
        except Exception:
            # Display manual retrieval instructions before propagating the error
            # so the user understands how to obtain the value by hand.
            instructions = generator.get_manual_instructions()
            if instructions is not None:
                BaseGenerator._display_manual_instructions(instructions)
            raise

    def _retrieve_from_target(self, secret_name: str, target_config: Any) -> str | None:
        """Retrieve a secret value from a target using the bundle registry.

        Args:
            secret_name: Name of the secret
            target_config: Target configuration

        Returns:
            Secret value if found, None otherwise
        """
        try:
            kind_str = str(target_config.kind)

            # Resolve provider for non-local targets
            provider = None
            if target_config.provider != "local":
                provider = self._get_provider(target_config.provider)
                if provider is None:
                    return None
                if not provider.is_authenticated():
                    if not provider.authenticate():
                        return None

            # Look up target class in bundle registry
            target_class = self._bundle_registry.get_target_class(kind_str)
            if target_class is None:
                return None

            # Local targets receive only config; provider-based targets receive (provider, config)
            if target_config.provider == "local":
                target = target_class(target_config.config)
            else:
                target = target_class(provider, target_config.config)

            return target.retrieve(secret_name)

        except Exception:
            return None

    def _get_local_actor_info(self) -> dict[str, Any]:
        """Return actor information for local (non-provider) operations."""
        import getpass
        import os

        username = None
        full_name = None
        uid: int | None = None

        try:
            username = getpass.getuser()
        except Exception:
            try:
                username = os.getenv("USER") or os.getenv("USERNAME")
            except Exception:
                username = None

        try:
            uid = os.getuid()
            try:
                import pwd  # type: ignore[import]

                pw = pwd.getpwuid(uid)
                gecos = pw.pw_gecos or ""
                full_name = (gecos.split(",")[0] or None) if gecos else None
            except Exception:
                full_name = None
        except Exception:
            uid = None

        return {
            "provider": "local",
            "username": username,
            "uid": uid,
            "full_name": full_name,
        }

    def _store_in_target(
        self, secret_name: str, secret_value: str, target_config: Any
    ) -> dict[str, Any]:
        """Store a secret in a target using the bundle registry.

        Args:
            secret_name: Name of the secret
            secret_value: Value to store
            target_config: Target configuration

        Returns:
            Dictionary with storage result
        """
        result: dict[str, Any] = {
            "provider": target_config.provider,
            "kind": target_config.kind,
            "status": "unknown",
        }

        try:
            kind_str = str(target_config.kind)

            # Look up the target class from the bundle registry
            target_class = self._bundle_registry.get_target_class(kind_str)
            if target_class is None:
                result["status"] = "unsupported"
                result["message"] = (
                    f"Target kind '{kind_str}' is not registered. "
                    f"Available kinds: {', '.join(self._bundle_registry.list_target_kinds())}"
                )
                return result

            # Resolve provider for non-local targets
            provider = None
            actor_info: dict[str, Any] | None = None
            if target_config.provider != "local":
                provider = self._get_provider(target_config.provider)
                if provider is None:
                    result["status"] = "error"
                    result["message"] = f"{target_config.provider} provider not initialized"
                    return result

                # Authenticate if not already authenticated
                if not provider.is_authenticated():
                    if not provider.authenticate():
                        result["status"] = "error"
                        result["message"] = f"{target_config.provider} authentication failed"
                        return result

                try:
                    actor_info = provider.get_actor_info()
                except Exception:
                    actor_info = None
            else:
                # Local targets: use OS user information
                actor_info = self._get_local_actor_info()

            # Instantiate the target
            if target_config.provider == "local":
                target = target_class(target_config.config)
            else:
                target = target_class(provider, target_config.config)

            # File targets: validate before storing
            if kind_str == "file":
                is_valid, error_msg = target.validate()
                if not is_valid:
                    result["status"] = "error"
                    result["message"] = f"File target validation failed: {error_msg}"
                    return result

            # Template targets: collect secrets for deferred rendering
            if kind_str == "template":
                success = target.store(secret_name, secret_value)
                template_id = target_config.config.get("output_path", "unknown")
                if template_id not in self._template_targets:
                    self._template_targets[template_id] = {
                        "target": target,
                        "secrets": {},
                    }
                self._template_targets[template_id]["secrets"][secret_name] = secret_value
                result["status"] = "stored" if success else "failed"
                return result

            # Generic store
            success = target.store(secret_name, secret_value)
            result["status"] = "stored" if success else "failed"

            if actor_info is not None:
                result["actor"] = actor_info

        except ImportError as exc:
            result["status"] = "error"
            result["message"] = f"Missing dependency: {exc}"
        except Exception as exc:
            result["status"] = "error"
            result["message"] = str(exc)

        return result

    def _render_template_targets(self) -> list[str]:
        """Render all collected template targets with their secrets.

        Returns:
            List of error messages from failed renderings
        """
        errors = []

        for template_id, template_info in self._template_targets.items():
            try:
                target = template_info["target"]
                secrets = template_info["secrets"]

                # Render the template with collected secrets
                success = target.render(secrets)

                if not success:
                    errors.append(
                        f"Failed to render template to {target.output_path}: Unknown error"
                    )
            except Exception as e:
                errors.append(f"Failed to render template to {template_id}: {e}")

        # Clear the template targets after rendering
        self._template_targets.clear()

        return errors

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
