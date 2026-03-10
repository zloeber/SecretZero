"""Jenkins provider for credentials."""

import os
import secrets
import string
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class JenkinsAuth(ProviderAuth):
    """Jenkins authentication handler.

    Supports authentication via:
    - Explicit credentials in config
    - Environment variables: JENKINS_URL, JENKINS_USERNAME, JENKINS_TOKEN
    """

    # Environment variables to check for credentials
    ENV_URL = "JENKINS_URL"
    ENV_USERNAME = "JENKINS_USERNAME"
    ENV_TOKEN = "JENKINS_TOKEN"

    def __init__(self, config: dict[str, Any]):
        """Initialize Jenkins authentication.

        Args:
            config: Authentication configuration containing:
                - url: Jenkins server URL (or set JENKINS_URL env var)
                - username: Jenkins username (or set JENKINS_USERNAME env var)
                - token: Jenkins API token or password (or set JENKINS_TOKEN env var)
        """
        super().__init__(config)
        self._client: Any | None = None

    def authenticate(self) -> bool:
        """Authenticate with Jenkins.

        Returns:
            True if authentication successful, False otherwise.

        Attempts to authenticate using:
            1. Explicit credentials from config
            2. Environment variables (JENKINS_URL, JENKINS_USERNAME, JENKINS_TOKEN)
        """
        try:
            import jenkins
        except ImportError:
            return False

        url = self.config.get("url") or os.environ.get(self.ENV_URL)
        username = self.config.get("username") or os.environ.get(self.ENV_USERNAME)
        token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)

        if not url or not username or not token:
            return False

        try:
            # Initialize Jenkins client
            self._client = jenkins.Jenkins(url, username=username, password=token)
            # Test authentication by getting version
            self._client.get_version()
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
        """Get the authenticated Jenkins client.

        Returns:
            python-jenkins Jenkins instance.
        """
        if not self.is_authenticated():
            self.authenticate()
        return self._client


class JenkinsProvider(BaseProvider):
    """Jenkins provider for credentials."""

    display_name = "Jenkins"
    description = "Jenkins credentials and secrets"
    required_package = ("jenkins", "secretzero[jenkins]")
    auth_class = JenkinsAuth
    auth_methods = {
        "token": "Use Jenkins API token",
    }
    config_options = {
        "url": "Jenkins server URL",
        "username": "Jenkins username",
    }
    config_example = """providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: admin
        token: ${JENKINS_TOKEN}"""
    target_details = {
        "jenkins_credential": {
            "description": "Jenkins Secret Credential",
            "config": {
                "credential_id": "Credential ID in Jenkins",
                "credential_type": "Type: secret_text, username_password, or ssh_key (default: secret_text)",
                "folder": "Jenkins folder path (optional)",
            },
            "example": """targets:
  - provider: jenkins
    kind: jenkins_credential
    config:
      credential_id: database_password
      credential_type: secret_text""",
        },
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: JenkinsAuth | None = None,
    ):
        """Initialize Jenkins provider.

        Args:
            name: Provider name.
            config: Provider configuration.
            auth: Optional pre-configured auth handler.
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            # Merge top-level config into auth config
            for key in ["url", "username", "token"]:
                if key in config:
                    auth_config[key] = config[key]
            auth = JenkinsAuth(auth_config)
        super().__init__(name, config, auth)

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "jenkins"

    def get_actor_info(self) -> dict[str, Any]:
        """Return information about the current Jenkins user/context."""
        info = super().get_actor_info()

        # Jenkins typically authenticates as a user; config may carry username.
        username = (self.config or {}).get("username") or (
            self.auth.config.get("username") if self.auth else None
        )
        url = (self.config or {}).get("url") or (self.auth.config.get("url") if self.auth else None)

        if username:
            info.setdefault("user", username)
        if url:
            info.setdefault("url", url)

        return info

    def test_connection(self) -> tuple[bool, str | None]:
        """Test Jenkins API connectivity.

        Returns:
            Tuple of (success, details).
        """
        # If python-jenkins is missing, treat this as an authentication-
        # style failure so callers can handle it consistently.
        try:
            import jenkins  # noqa: F401
        except ImportError:
            return (
                False,
                "Authentication failed - python-jenkins not installed (pip install python-jenkins)",
            )

        # Check if all required credentials are available in config, auth config, or environment
        url = (
            self.config.get("url")
            or (self.auth.config.get("url") if self.auth else None)
            or os.environ.get(JenkinsAuth.ENV_URL)
        )
        username = (
            self.config.get("username")
            or (self.auth.config.get("username") if self.auth else None)
            or os.environ.get(JenkinsAuth.ENV_USERNAME)
        )
        token = (
            self.config.get("token")
            or (self.auth.config.get("token") if self.auth else None)
            or os.environ.get(JenkinsAuth.ENV_TOKEN)
        )

        if not url or not username or not token:
            missing = []
            if not url:
                missing.append(f"url (or {JenkinsAuth.ENV_URL})")
            if not username:
                missing.append(f"username (or {JenkinsAuth.ENV_USERNAME})")
            if not token:
                missing.append(f"token (or {JenkinsAuth.ENV_TOKEN})")
            return False, f"Missing required credentials: {', '.join(missing)}"

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed - invalid credentials"

        try:
            client = self.auth.get_client()
            version = client.get_version()
            return True, f"Connected to Jenkins v{version}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types.

        Returns:
            List of target type identifiers.
        """
        return ["jenkins_credential"]

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
            char_pool += string.ascii_uppercase
        if lowercase:
            char_pool += string.ascii_lowercase
        if numbers:
            char_pool += string.digits
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
        credential_type: str = "UsernamePasswordCredentialsImpl",
    ) -> str:
        """Retrieve a credential from Jenkins.

        Args:
            secret_name: Credential ID to retrieve.
            credential_type: Type of credential. Defaults to UsernamePasswordCredentialsImpl.

        Returns:
            str: Placeholder message indicating credential exists.

        Raises:
            ValueError: If the credential cannot be retrieved.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("Jenkins authentication failed")

            # Use Jenkins Credentials API through HTTP
            url = self.config.get("url") or self.auth.config.get("url")
            if not url:
                raise ValueError("Jenkins URL must be configured")

            # Jenkins API endpoint for credentials
            cred_url = f"{url}/credentials/store/system/domain/_/credential/{secret_name}/api/json"

            response = client.jenkins_open(cred_url)
            if response:
                return "[CREDENTIAL EXISTS]"
            raise ValueError(f"Credential {secret_name} not found")

        except Exception as e:
            raise ValueError(f"Failed to retrieve credential from Jenkins: {e}")

    # ===== STORE CAPABILITY =====

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        credential_type: str = "UsernamePasswordCredentialsImpl",
        username: str | None = None,
    ) -> bool:
        """Store a credential in Jenkins.

        Args:
            secret_name: Credential ID for the credential.
            secret_value: The secret password/token value.
            credential_type: Type of credential to create. Defaults to UsernamePasswordCredentialsImpl.
            username: Username for UsernamePasswordCredentialsImpl. Defaults to None.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the credential cannot be stored.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("Jenkins authentication failed")

            url = self.config.get("url") or self.auth.config.get("url")
            if not url:
                raise ValueError("Jenkins URL must be configured")

            # Create credential XML based on type
            if credential_type == "UsernamePasswordCredentialsImpl":
                credential_xml = f"""
                <com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
                    <id>{secret_name}</id>
                    <description>Managed by SecretZero</description>
                    <username>{username or secret_name}</username>
                    <password>{secret_value}</password>
                </com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
                """
            elif credential_type == "SecretStringCredentials":
                credential_xml = f"""
                <org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>
                    <id>{secret_name}</id>
                    <description>Managed by SecretZero</description>
                    <secret>{secret_value}</secret>
                </org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>
                """
            else:
                raise ValueError(f"Unsupported credential type: {credential_type}")

            # API endpoint to create credential
            cred_url = f"{url}/credentials/store/system/domain/_/createCredentials"
            client.jenkins_open(cred_url, data=credential_xml, is_post=True)
            return True

        except Exception as e:
            raise ValueError(f"Failed to store credential in Jenkins: {e}")

    # ===== DELETE CAPABILITY =====

    def delete_secret(self, secret_name: str) -> bool:
        """Delete a credential from Jenkins.

        Args:
            secret_name: Credential ID to delete.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the credential cannot be deleted.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("Jenkins authentication failed")

            url = self.config.get("url") or self.auth.config.get("url")
            if not url:
                raise ValueError("Jenkins URL must be configured")

            # API endpoint to delete credential
            cred_url = f"{url}/credentials/store/system/domain/_/credential/{secret_name}/doDelete"
            client.jenkins_open(cred_url, is_post=True)
            return True

        except Exception as e:
            raise ValueError(f"Failed to delete credential from Jenkins: {e}")


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   jenkins = "secretzero_jenkins:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    """Lazily construct the Jenkins bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="jenkins",
        version="1.0.0",
        provider_class="secretzero.providers.jenkins:JenkinsProvider",
        generators={},
        targets={
            "jenkins_credential": "secretzero.targets.jenkins:JenkinsCredentialTarget",
        },
        generator_kinds=[],
        target_kinds=["jenkins_credential"],
        terraform_provider=None,
    )
