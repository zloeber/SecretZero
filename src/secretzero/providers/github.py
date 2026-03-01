"""GitHub provider for GitHub Actions secrets and PAT generation."""

import json
import os
import secrets
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth

# ===== GitHub PAT Permission Models =====

# Valid permission names for fine-grained GitHub PATs / App installation tokens.
# Maps permission name -> allowed access levels.
GITHUB_PAT_PERMISSIONS: dict[str, list[str]] = {
    # Repository permissions
    "actions": ["read", "write"],
    "administration": ["read", "write"],
    "checks": ["read", "write"],
    "codespaces": ["read", "write"],
    "contents": ["read", "write"],
    "dependabot_secrets": ["read", "write"],
    "deployments": ["read", "write"],
    "environments": ["read", "write"],
    "issues": ["read", "write"],
    "metadata": ["read", "write"],
    "packages": ["read", "write"],
    "pages": ["read", "write"],
    "pull_requests": ["read", "write"],
    "repository_hooks": ["read", "write"],
    "repository_projects": ["read", "write", "admin"],
    "secret_scanning_alerts": ["read", "write"],
    "secrets": ["read", "write"],
    "security_events": ["read", "write"],
    "single_file": ["read", "write"],
    "statuses": ["read", "write"],
    "vulnerability_alerts": ["read", "write"],
    "workflows": ["write"],
    # Organization permissions
    "members": ["read", "write"],
    "organization_administration": ["read", "write"],
    "organization_hooks": ["read", "write"],
    "organization_plan": ["read"],
    "organization_projects": ["read", "write", "admin"],
    "organization_secrets": ["read", "write"],
    "organization_self_hosted_runners": ["read", "write"],
    "team_discussions": ["read", "write"],
}


def validate_pat_permissions(permissions: dict[str, str]) -> tuple[bool, list[str]]:
    """Validate a set of PAT permissions against the known permission schema.

    Args:
        permissions: Mapping of permission name to access level (e.g. {"contents": "read"}).

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    errors: list[str] = []
    for perm_name, access_level in permissions.items():
        if perm_name not in GITHUB_PAT_PERMISSIONS:
            errors.append(
                f"Unknown permission '{perm_name}'. "
                f"Valid: {', '.join(sorted(GITHUB_PAT_PERMISSIONS.keys()))}"
            )
            continue
        allowed = GITHUB_PAT_PERMISSIONS[perm_name]
        if access_level not in allowed:
            errors.append(
                f"Invalid access level '{access_level}' for permission '{perm_name}'. "
                f"Allowed: {', '.join(allowed)}"
            )
    return (len(errors) == 0, errors)


# ===== GitHub OAuth Device Flow Defaults =====

#: Default GitHub device-code endpoint (used by :meth:`GitHubAuth.authenticate_device_flow`).
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"

#: Default GitHub token endpoint.
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

#: Default OAuth scopes requested when none are specified.
GITHUB_DEFAULT_OAUTH_SCOPES: list[str] = ["repo", "read:org", "workflow"]


class GitHubAuth(ProviderAuth):
    """GitHub authentication handler.

    Supports authentication via:

    - Explicit token in config
    - Environment variable: ``GITHUB_TOKEN`` (checked automatically if not in config)
    - Interactive OAuth device flow (see :meth:`authenticate_device_flow`)
    """

    # Environment variable to check for token
    ENV_TOKEN = "GITHUB_TOKEN"

    # Human-readable descriptions for GitHub OAuth / fine-grained token scopes.
    SCOPE_DESCRIPTIONS: dict[str, str] = {
        "repo": "Full control of private repositories",
        "repo:status": "Access commit status",
        "repo_deployment": "Access deployment status",
        "public_repo": "Access public repositories",
        "repo:invite": "Access repository invitations",
        "security_events": "Read and write security events",
        "admin:repo_hook": "Full control of repository hooks",
        "write:repo_hook": "Write repository hooks",
        "read:repo_hook": "Read repository hooks",
        "admin:org": "Full control of orgs and teams",
        "write:org": "Read and write org and team membership",
        "read:org": "Read org and team membership",
        "admin:public_key": "Full control of user public keys",
        "write:public_key": "Write user public keys",
        "read:public_key": "Read user public keys",
        "admin:org_hook": "Full control of organization hooks",
        "gist": "Create gists",
        "notifications": "Access notifications",
        "user": "Update all user data",
        "read:user": "Read all user profile data",
        "user:email": "Access user email addresses",
        "user:follow": "Follow and unfollow users",
        "delete_repo": "Delete repositories",
        "write:discussion": "Read and write team discussions",
        "read:discussion": "Read team discussions",
        "write:packages": "Upload packages",
        "read:packages": "Download packages",
        "delete:packages": "Delete packages",
        "admin:gpg_key": "Full control of user GPG keys",
        "write:gpg_key": "Write user GPG keys",
        "read:gpg_key": "Read user GPG keys",
        "workflow": "Update GitHub Action workflows",
        "admin:enterprise": "Full control of enterprises",
        "manage_runners:enterprise": "Manage enterprise runners and runner groups",
        "manage_billing:enterprise": "Read and write enterprise billing data",
        "read:enterprise": "Read enterprise profile data",
        "codespace": "Full control of codespaces",
        "copilot": "Full control of GitHub Copilot settings",
    }

    @classmethod
    def get_scope_descriptions(cls) -> dict[str, str]:
        """Return GitHub OAuth scope descriptions.

        Returns:
            Mapping of scope name to human-readable description.
        """
        return dict(cls.SCOPE_DESCRIPTIONS)

    def __init__(self, config: dict[str, Any]):
        """Initialize GitHub authentication.

        Args:
            config: Authentication configuration containing:
                - token: GitHub personal access token (or set GITHUB_TOKEN env var)
                - api_url: Optional GitHub API URL (default: https://api.github.com)

        Notes:
            If 'token' is not provided in config, will check GITHUB_TOKEN environment variable.
        """
        super().__init__(config)
        self._client: Any | None = None

    def authenticate(self) -> bool:
        """Authenticate with GitHub.

        Returns:
            True if authentication successful, False otherwise.

        Attempts to authenticate using:
            1. Explicit token from config
            2. GITHUB_TOKEN environment variable
        """
        try:
            from github import Github
        except ImportError:
            return False

        # Try to get token from config or environment
        token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
        if not token:
            return False

        api_url = self.config.get("api_url", "https://api.github.com")

        try:
            # Initialize GitHub client
            self._client = Github(token, base_url=api_url)
            # Test authentication by fetching user info
            self._client.get_user().login
            return True
        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """Check if currently authenticated.

        Returns:
            True if authenticated, False otherwise.
        """
        return self._client is not None

    def get_client(self) -> Any:
        """Get the authenticated GitHub client.

        Returns:
            PyGithub Github instance.
        """
        if not self.is_authenticated():
            self.authenticate()
        return self._client

    # ------------------------------------------------------------------
    # Interactive OAuth device flow
    # ------------------------------------------------------------------

    def authenticate_device_flow(
        self,
        client_id: str,
        scopes: list[str] | None = None,
        *,
        open_browser: bool = True,
        on_user_code: Any = None,
        max_wait: int = 0,
        _sleep: Any = None,
    ) -> dict[str, Any]:
        """Run the OAuth 2.0 Device Authorization Grant interactively.

        This method requests a one-time user code from GitHub, optionally
        opens the verification URL in the user's browser, and then polls
        until the user has authorized the application.

        On success the resulting access token is stored internally so that
        subsequent calls to :meth:`authenticate` and :meth:`get_client`
        work transparently.

        Args:
            client_id: OAuth App or GitHub App client ID.
            scopes: OAuth scopes to request.  Defaults to
                :data:`GITHUB_DEFAULT_OAUTH_SCOPES`.
            open_browser: If *True*, attempt to open the verification URL
                in the user's default browser.
            on_user_code: Optional callback ``(user_code, verification_uri,
                verification_uri_complete) -> None`` invoked as soon as the
                user code is available.  Useful for CLI output.
            max_wait: Maximum seconds to wait for authorization.  ``0``
                means use the server-provided expiry.
            _sleep: Override for ``time.sleep`` (used in tests).

        Returns:
            Dictionary with ``access_token``, ``token_type``, ``scope``,
            and the full ``raw`` server response.

        Raises:
            RuntimeError: If the device flow fails.
        """
        from secretzero.oauth.device_flow import (
            DeviceFlowConfig,
            DeviceFlowError,
            poll_for_token,
            request_device_code,
        )

        base_url = self.config.get("github_url", "https://github.com")
        device_code_url = f"{base_url}/login/device/code"
        token_url = f"{base_url}/login/oauth/access_token"

        cfg = DeviceFlowConfig(
            client_id=client_id,
            device_code_url=device_code_url,
            token_url=token_url,
            scopes=scopes or GITHUB_DEFAULT_OAUTH_SCOPES,
        )

        try:
            device = request_device_code(cfg)
        except DeviceFlowError as exc:
            raise RuntimeError(f"Failed to start GitHub device flow: {exc}") from exc

        # Notify the caller so the CLI can display the code
        if on_user_code:
            on_user_code(
                device.user_code,
                device.verification_uri,
                device.verification_uri_complete,
            )

        # Optionally open the browser
        if open_browser:
            try:
                import webbrowser

                target = device.verification_uri_complete or device.verification_uri
                webbrowser.open(target)
            except Exception:  # noqa: BLE001
                pass  # Non-fatal; user can navigate manually.

        try:
            result = poll_for_token(
                cfg,
                device,
                max_wait=max_wait,
                _sleep=_sleep,
            )
        except DeviceFlowError as exc:
            raise RuntimeError(f"GitHub device flow failed: {exc}") from exc

        # Store the token so authenticate() / get_client() pick it up.
        self.config["token"] = result.access_token
        self._client = None  # Reset so next get_client() re-authenticates.

        return {
            "access_token": result.access_token,
            "token_type": result.token_type,
            "scope": result.scope,
            "raw": result.raw,
        }

    def get_token_info(self) -> dict[str, Any]:
        """Get information about the authenticated token.

        Uses GitHub REST API directly (doesn't require PyGithub client).

        Returns:
            Dictionary containing:
                - user: GitHub username
                - scopes: List of OAuth scopes granted to the token
                - token_type: Type of token (e.g., 'OAuth', 'PAT')

        Raises:
            RuntimeError: If token is not available or API request fails
        """
        try:
            import requests

            # Get token for API request
            token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
            if not token:
                raise RuntimeError(
                    "No GitHub token found in config or GITHUB_TOKEN environment variable"
                )

            api_url = self.config.get("api_url", "https://api.github.com")

            # Make authenticated request to /user endpoint
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(f"{api_url}/user", headers=headers, timeout=10)
            response.raise_for_status()

            user_data = response.json()

            # Get scopes from header
            scopes_header = response.headers.get("X-OAuth-Scopes", "")
            scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]

            return {
                "user": user_data.get("login", "unknown"),
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "scopes": scopes,
                "token_type": response.headers.get("X-GitHub-SSO", "PAT"),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get token info: {e}")


class GitHubProvider(BaseProvider):
    """GitHub provider for Actions secrets."""

    display_name = "GitHub"
    description = "GitHub repository secrets and Actions"
    required_package = ("github", "secretzero[github]")
    auth_class = GitHubAuth
    auth_methods = {
        "token": "Use GitHub personal access token",
        "oauth_device": "Interactive OAuth device flow (browser-based login)",
    }
    config_options = {
        "owner": "GitHub organization or username",
        "repo": "Repository name",
    }
    config_example = """providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}"""
    target_details = {
        "github_secret": {
            "description": "GitHub Actions Secret",
            "config": {
                "repository": "GitHub repository (owner/repo format)",
                "secret_name": "Secret name (optional, uses secret.name if not provided)",
            },
            "example": """targets:
  - provider: github
    kind: github_secret
    config:
      repository: myorg/myrepo
      secret_name: DATABASE_PASSWORD""",
        },
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: GitHubAuth | None = None,
    ):
        """Initialize GitHub provider.

        Args:
            name: Provider name.
            config: Provider configuration.
            auth: Optional pre-configured auth handler.
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            # Merge top-level config into auth config for token
            if "token" in config:
                auth_config = {**auth_config, "token": config["token"]}
            auth = GitHubAuth(auth_config)
        super().__init__(name, config, auth)

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "github"

    def test_connection(self) -> tuple[bool, str | None]:
        """Test GitHub API connectivity.

        Returns:
            Tuple of (success, details).
        """
        try:
            from github import Github
        except ImportError:
            return False, "PyGithub not installed (pip install PyGithub)"

        # Check if token is available in config, auth config, or environment
        token = (
            self.config.get("token")
            or (self.auth.config.get("token") if self.auth else None)
            or os.environ.get(GitHubAuth.ENV_TOKEN)
        )
        if not token:
            return (
                False,
                f"No authentication token found. Set config 'token' or {GitHubAuth.ENV_TOKEN} env var",
            )

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed - invalid token or API URL"

        try:
            client = self.auth.get_client()
            user = client.get_user()
            return True, f"Connected as {user.login}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types.

        Returns:
            List of target type identifiers.
        """
        return ["github_secret", "github_environment_secret"]

    def get_token_permissions(self) -> dict[str, Any]:
        """Get information about the current GitHub token.

        .. deprecated::
            Use :meth:`get_token_info` (inherited from :class:`BaseProvider`)
            instead. This method is kept for backward compatibility.

        Returns:
            Dictionary with token information including scopes/permissions.

        Raises:
            RuntimeError: If not authenticated or token info cannot be retrieved.
        """
        return self.get_token_info()

    @classmethod
    def get_scope_descriptions(cls) -> dict[str, str]:
        """Return GitHub OAuth scope descriptions.

        Returns:
            Mapping of scope name to human-readable description.
        """
        return GitHubAuth.get_scope_descriptions()

    # ===== GENERATE CAPABILITY =====

    def generate_password(
        self,
        length: int = 32,
        special_chars: bool = True,
        uppercase: bool = True,
        lowercase: bool = True,
        numbers: bool = True,
    ) -> str:
        """Generate a cryptographically secure password.

        Args:
            length: Length of password (8-256 characters). Defaults to 32.
            special_chars: Include special characters. Defaults to True.
            uppercase: Include uppercase letters. Defaults to True.
            lowercase: Include lowercase letters. Defaults to True.
            numbers: Include numbers. Defaults to True.

        Returns:
            str: Generated password.

        Raises:
            ValueError: If parameters are invalid.
        """
        if length < 8 or length > 256:
            raise ValueError("Password length must be between 8 and 256")

        char_pool = ""
        if uppercase:
            char_pool += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if lowercase:
            char_pool += "abcdefghijklmnopqrstuvwxyz"
        if numbers:
            char_pool += "0123456789"
        if special_chars:
            char_pool += "!@#$%^&*-_+=()[]{}|:;<>,.?/"

        if not char_pool:
            raise ValueError("At least one character type must be enabled")

        password = "".join(secrets.choice(char_pool) for _ in range(length))
        return password

    # ===== RETRIEVE CAPABILITY =====

    def retrieve_secret(
        self,
        secret_name: str,
        repository: str | None = None,
        environment: str | None = None,
    ) -> str:
        """Retrieve a secret from GitHub.

        Note: GitHub API does not return secret values for security reasons.
        This method returns a placeholder.

        Args:
            secret_name: Name of the secret to retrieve.
            repository: GitHub repository (owner/repo format).
            environment: Optional environment name for environment secrets.

        Returns:
            str: Placeholder message indicating secret exists.

        Raises:
            ValueError: If the secret cannot be retrieved or does not exist.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitHub authentication failed")

            if not repository:
                repository = self.config.get("repository")
            if not repository:
                raise ValueError("Repository (owner/repo) must be specified")

            repo = client.get_repo(repository)

            if environment:
                # Check environment secret
                try:
                    _ = repo.get_environment(environment)
                    # GitHub API doesn't provide secret values
                    return f"[SECRET EXISTS in {environment}]"
                except Exception as e:
                    raise ValueError(f"Secret not found in environment {environment}: {e}")
            else:
                # Check repository secret
                try:
                    # List secrets to verify it exists
                    secrets_list = repo.get_secrets()
                    for s in secrets_list:
                        if s.name == secret_name:
                            return "[SECRET EXISTS]"
                    raise ValueError(f"Secret {secret_name} not found")
                except Exception as e:
                    raise ValueError(f"Failed to retrieve secret: {e}")

        except Exception as e:
            raise ValueError(f"Failed to retrieve secret from GitHub: {e}")

    # ===== STORE CAPABILITY =====

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        repository: str | None = None,
        environment: str | None = None,
    ) -> bool:
        """Store a secret in GitHub.

        Args:
            secret_name: Name of the secret.
            secret_value: The secret value.
            repository: GitHub repository (owner/repo format).
            environment: Optional environment name for environment secrets.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be stored.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitHub authentication failed")

            if not repository:
                repository = self.config.get("repository")
            if not repository:
                raise ValueError("Repository (owner/repo) must be specified")

            repo = client.get_repo(repository)

            if environment:
                # Store as environment secret
                _ = repo.get_environment(environment)
                from github import Repository

                repo.create_environment_secret(environment, secret_name, secret_value)
            else:
                # Store as repository secret
                repo.create_secret(secret_name, secret_value)

            return True
        except Exception as e:
            raise ValueError(f"Failed to store secret in GitHub: {e}")

    # ===== DELETE CAPABILITY =====

    def delete_secret(
        self,
        secret_name: str,
        repository: str | None = None,
        environment: str | None = None,
    ) -> bool:
        """Delete a secret from GitHub.

        Args:
            secret_name: Name of the secret to delete.
            repository: GitHub repository (owner/repo format).
            environment: Optional environment name for environment secrets.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be deleted.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitHub authentication failed")

            if not repository:
                repository = self.config.get("repository")
            if not repository:
                raise ValueError("Repository (owner/repo) must be specified")

            repo = client.get_repo(repository)

            if environment:
                # Delete environment secret
                env = repo.get_environment(environment)
                env.delete_secret(secret_name)
            else:
                # Delete repository secret
                repo.delete_secret(secret_name)

            return True
        except Exception as e:
            raise ValueError(f"Failed to delete secret from GitHub: {e}")

    # ===== GENERATE PAT CAPABILITY =====

    def generate_pat(
        self,
        permissions: dict[str, str] | None = None,
        repositories: list[str] | None = None,
        repository: str | None = None,
        token_name: str | None = None,
        expires_in_hours: int = 1,
    ) -> str:
        """Generate a scoped GitHub App installation access token.

        Creates a short-lived installation token via a GitHub App with only
        the requested permissions.  This is the API-automatable equivalent
        of a fine-grained PAT.

        The calling token **must** be a GitHub App JWT or an installation
        token that itself has permission to create installation tokens.
        Alternatively, if ``app_id`` and ``private_key`` (or
        ``private_key_path``) are provided in the provider config, those
        are used to mint a JWT automatically.

        Args:
            permissions: Mapping of permission scope to access level,
                e.g. ``{"contents": "read", "pull_requests": "write"}``.
                Must conform to :data:`GITHUB_PAT_PERMISSIONS`.
                If *None*, the installation's full default permissions are used.
            repositories: Optional list of repository names (not full
                ``owner/repo``) to scope the token to.
            repository: Convenience alias – single ``owner/repo`` string.
                When supplied and *repositories* is empty, the repo name
                part is extracted automatically.
            token_name: Human-readable label stored in metadata (not sent
                to the API, but useful for lockfile tracking).
            expires_in_hours: Lifetime of the token in hours (1-24,
                default 1).  GitHub enforces a hard maximum of 1 hour for
                installation tokens, so values > 1 are clamped.

        Returns:
            The installation access token string.

        Raises:
            ValueError: If permissions are invalid or required config is
                missing.
            RuntimeError: If the GitHub API call fails.
        """
        # ---- validate permissions ------------------------------------------
        if permissions:
            valid, errors = validate_pat_permissions(permissions)
            if not valid:
                raise ValueError("Invalid PAT permissions:\n  " + "\n  ".join(errors))

        # ---- resolve repository list ---------------------------------------
        repo_names: list[str] | None = None
        if repositories:
            repo_names = repositories
        elif repository:
            # Accept "owner/repo" or bare "repo"
            repo_names = [repository.split("/")[-1]]
        elif self.config.get("repository"):
            repo_names = [self.config["repository"].split("/")[-1]]

        # ---- build JWT from App credentials if available -------------------
        app_id = self.config.get("app_id")
        private_key = self.config.get("private_key")
        private_key_path = self.config.get("private_key_path")
        installation_id = self.config.get("installation_id")

        if not app_id:
            app_id = os.environ.get("GITHUB_APP_ID")
        if not private_key and not private_key_path:
            private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
            private_key_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH")
        if not installation_id:
            installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")

        if not app_id or not installation_id:
            raise ValueError(
                "generate_pat requires GitHub App credentials. "
                "Set 'app_id' and 'installation_id' in provider config, "
                "or GITHUB_APP_ID / GITHUB_APP_INSTALLATION_ID env vars."
            )

        if private_key_path and not private_key:
            try:
                with open(private_key_path) as fh:
                    private_key = fh.read()
            except OSError as exc:
                raise ValueError(
                    f"Cannot read GitHub App private key from {private_key_path}: {exc}"
                )

        if not private_key:
            raise ValueError(
                "generate_pat requires a GitHub App private key. "
                "Set 'private_key' in config or GITHUB_APP_PRIVATE_KEY env var."
            )

        # ---- mint JWT and request installation token -----------------------
        try:
            import time

            import jwt as pyjwt
            import requests
        except ImportError as exc:
            raise RuntimeError(f"generate_pat requires 'PyJWT' and 'requests' packages: {exc}")

        now = int(time.time())
        payload = {
            "iat": now - 60,  # issued-at (1 min in the past for clock skew)
            "exp": now + (10 * 60),  # 10-minute JWT lifetime (max allowed)
            "iss": str(app_id),
        }
        encoded_jwt = pyjwt.encode(payload, private_key, algorithm="RS256")

        api_url = (
            self.config.get("api_url")
            or (self.auth.config.get("api_url") if self.auth else None)
            or "https://api.github.com"
        )

        # Build the access token request body
        body: dict[str, Any] = {}
        if permissions:
            body["permissions"] = permissions
        if repo_names:
            body["repositories"] = repo_names

        headers = {
            "Authorization": f"Bearer {encoded_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        url = f"{api_url}/app/installations/{installation_id}/access_tokens"
        response = requests.post(url, headers=headers, json=body, timeout=30)

        if response.status_code != 201:
            detail = response.text[:500]
            raise RuntimeError(
                f"GitHub API returned {response.status_code} creating installation token: {detail}"
            )

        data = response.json()
        token = data.get("token")
        if not token:
            raise RuntimeError("GitHub API response missing 'token' field")

        return token

    def generate_pat_with_manifest(
        self,
        manifest: dict[str, Any],
    ) -> str:
        """Generate a PAT from a full manifest block (convenience wrapper).

        This is the method invoked by the ``github_pat`` generator kind.
        It unpacks a manifest dict and delegates to :meth:`generate_pat`.

        Args:
            manifest: Dictionary with keys matching :meth:`generate_pat`
                parameters: ``permissions``, ``repositories``, ``repository``,
                ``token_name``, ``expires_in_hours``.

        Returns:
            The installation access token string.
        """
        return self.generate_pat(
            permissions=manifest.get("permissions"),
            repositories=manifest.get("repositories"),
            repository=manifest.get("repository"),
            token_name=manifest.get("token_name"),
            expires_in_hours=manifest.get("expires_in_hours", 1),
        )


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   github = "secretzero_github:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    """Lazily construct the GitHub bundle manifest.

    The import is deferred so that importing this module does not force
    the bundles package to load.
    """
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="github",
        version="1.0.0",
        provider_class="secretzero.providers.github:GitHubProvider",
        generators={
            "github_pat": "secretzero.generators.github_pat:GitHubPATGenerator",
        },
        targets={
            "github_secret": "secretzero.targets.github:GitHubSecretTarget",
        },
        generator_kinds=["github_pat"],
        target_kinds=["github_secret"],
    )
