"""Provider-backed secret generator for SecretZero.

This generator delegates secret generation to a provider that has native
generation capabilities (e.g., Vault's password generation, AWS IAM
credential generation, etc.).
"""

from typing import Any

from secretzero.generators.base import BaseGenerator
from secretzero.models import AgentInstructions, AgentInstructionStep
from secretzero.providers.base import BaseProvider
from secretzero.providers.capabilities import CapabilityType, IProviderWithCapabilities


class ProviderBackedGeneratorConfig:
    """Configuration for provider-backed generator."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize configuration.

        Args:
            config: Configuration dictionary with:
                - provider: Provider instance or registry key
                - method: Method name to call on provider
                - method_args: Arguments to pass to method (default: {})
        """
        self.provider = config.get("provider")
        self.method = config.get("method")
        self.method_args = config.get("method_args", {})

        if not self.provider:
            raise ValueError("provider_backed generator requires 'provider' configuration")
        if not self.method:
            raise ValueError("provider_backed generator requires 'method' configuration")


class ProviderBackedGenerator(BaseGenerator):
    """Generator that delegates to a provider's capability method.

    .. rubric:: Bundle provider injection protocol

    The sync engine inspects ``PROVIDER_CONFIG_KEY`` and ``PROVIDER_INJECTION_KEY``
    class attributes to inject the resolved provider instance into the config
    before instantiation.  For this generator both keys are ``"provider"``,
    meaning the string provider name in ``config["provider"]`` is *replaced*
    in-place with the actual provider instance.

    This allows using provider-native operations for secret generation:
    - Vault's password/certificate generation
    - AWS IAM credential generation
    - Azure service principal creation
    - etc.

    Example configuration:
        generator: provider_backed
        generator_config:
          provider: vault_instance
          method: generate_password
          method_args:
            length: 32
            special_chars: true
    """

    #: Key in the generator config dict that holds the provider *name* string.
    #: Used by the sync engine to resolve the provider instance.
    PROVIDER_CONFIG_KEY: str = "provider"

    #: Key under which the sync engine injects the resolved provider *instance*.
    #: For this generator the string name is replaced in-place.
    PROVIDER_INJECTION_KEY: str = "provider"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize provider-backed generator.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If provider or method not configured
            TypeError: If provider doesn't support the method
        """
        super().__init__(config)
        self.gen_config = ProviderBackedGeneratorConfig(config)

        # Validate provider implements capabilities
        provider = self.gen_config.provider
        if not isinstance(provider, (BaseProvider, IProviderWithCapabilities)):
            raise TypeError(
                f"Provider must implement IProviderWithCapabilities, got {type(provider)}"
            )

        # Validate method exists
        if not hasattr(provider, self.gen_config.method):
            raise AttributeError(
                f"Provider {provider.__class__.__name__} has no method '{self.gen_config.method}'"
            )

        # Validate method is a capability method
        available_methods = provider.list_available_methods()
        if self.gen_config.method not in available_methods:
            raise ValueError(
                f"Method '{self.gen_config.method}' is not a capability method on {provider.__class__.__name__}. "
                f"Available: {', '.join(available_methods)}"
            )

    def generate(self) -> str:
        """Generate a secret using the provider method.

        Returns:
            Generated secret value from the provider

        Raises:
            RuntimeError: If provider method fails
            TypeError: If method return value is not a string
        """
        provider = self.gen_config.provider
        method = getattr(provider, self.gen_config.method)
        args = self.gen_config.method_args or {}

        try:
            result = method(**args)
        except Exception as e:
            raise RuntimeError(
                f"Failed to generate secret using {self.gen_config.method}: {e}"
            ) from e

        # Convert result to string if needed
        if isinstance(result, str):
            return result
        if isinstance(result, (int, float, bool)):
            return str(result)
        if isinstance(result, dict):
            # For dict results, return JSON string or specific field
            import json

            return json.dumps(result)

        raise TypeError(
            f"Provider method {self.gen_config.method} returned {type(result)}, "
            f"expected str, int, float, bool, or dict"
        )

    def validate_configuration(self) -> tuple[bool, str | None]:
        """Validate generator configuration.

        Returns:
            Tuple of (valid: bool, error_message: Optional[str])
        """
        try:
            provider = self.gen_config.provider
            if not provider:
                return False, "Provider is not configured"

            if not isinstance(provider, (BaseProvider, IProviderWithCapabilities)):
                return False, "Provider must implement IProviderWithCapabilities"

            method = self.gen_config.method
            if not hasattr(provider, method):
                return False, f"Provider has no method '{method}'"

            available = provider.list_available_methods()
            if method not in available:
                return False, f"Method '{method}' is not a capability method"

            # Try to get method schema to validate it exists and is callable
            schema = provider.get_method_schema(method)
            if not schema:
                return False, f"Could not get schema for method '{method}'"

            return True, None
        except Exception as e:
            return False, str(e)

    def get_manual_instructions(self) -> AgentInstructions:
        """Return step-by-step instructions for manually obtaining the provider-backed secret.

        These instructions are displayed when the provider method call fails or
        when the provider is unavailable and manual input is required.

        The guidance is tailored to the configured provider kind where possible.

        Returns:
            AgentInstructions with provider-specific manual retrieval steps.
        """
        if self.manual_instructions is not None:
            return self.manual_instructions

        provider = self.gen_config.provider
        method = self.gen_config.method

        # Determine provider kind for tailored instructions
        provider_kind: str = "unknown"
        provider_name: str = ""
        if isinstance(provider, BaseProvider):
            provider_kind = provider.provider_kind
            provider_name = getattr(provider, "name", "") or provider_kind

        # Build provider-specific steps
        steps = _build_provider_manual_steps(provider_kind, method, provider_name)

        return AgentInstructions(
            summary=(
                f"Automatic secret generation via '{provider_kind}' provider failed "
                f"(method: {method}). Follow these steps to obtain the secret manually."
            ),
            steps=steps,
            prerequisites=[
                f"Access credentials for the '{provider_kind}' provider",
                "Sufficient permissions to read or generate the required secret",
            ],
            automation_hint=(
                f"This secret can be generated automatically when the '{provider_kind}' "
                "provider is properly authenticated and accessible."
            ),
            fallback=(
                "Contact your infrastructure or security team to obtain the required secret value."
            ),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PROVIDER_MANUAL_STEPS: dict[str, list[AgentInstructionStep]] = {
    "aws": [
        AgentInstructionStep(
            action="https://console.aws.amazon.com",
            description="Log in to the AWS Management Console",
        ),
        AgentInstructionStep(
            action="Navigate to the relevant service (Secrets Manager, SSM Parameter Store, IAM, etc.)",
            description="Open the service that holds or can generate the required secret",
        ),
        AgentInstructionStep(
            action="Locate or create the secret / credential",
            description="Find the existing secret or use the service's generate feature",
        ),
        AgentInstructionStep(
            action="Copy the secret value",
            description="Retrieve and copy the plaintext secret value",
        ),
    ],
    "azure": [
        AgentInstructionStep(
            action="https://portal.azure.com",
            description="Log in to the Azure Portal",
        ),
        AgentInstructionStep(
            action="Navigate to Key Vault → Secrets",
            description="Open the Azure Key Vault that holds the required secret",
        ),
        AgentInstructionStep(
            action="Select the secret and click 'Show Secret Value'",
            description="Retrieve the current version of the secret",
        ),
        AgentInstructionStep(
            action="Copy the secret value",
            description="Copy the plaintext secret value",
        ),
    ],
    "vault": [
        AgentInstructionStep(
            action="Export VAULT_ADDR and VAULT_TOKEN environment variables, then run: vault kv get <path>",
            description="Authenticate with HashiCorp Vault and retrieve the secret",
        ),
        AgentInstructionStep(
            action="vault kv get -field=<field> <secret-path>",
            description="Read the specific field value from the Vault KV secret",
        ),
        AgentInstructionStep(
            action="Copy the output value",
            description="Copy the plaintext secret value",
        ),
    ],
    "github": [
        AgentInstructionStep(
            action="https://github.com/settings/tokens",
            description="Navigate to GitHub Settings → Developer settings → Personal access tokens",
        ),
        AgentInstructionStep(
            action="Generate a new token with the required permissions",
            description="Create or retrieve the GitHub token",
        ),
        AgentInstructionStep(
            action="Copy the token value immediately after generation",
            description="Copy the plaintext token value — it is only shown once",
        ),
    ],
    "gitlab": [
        AgentInstructionStep(
            action="https://gitlab.com/-/profile/personal_access_tokens",
            description="Navigate to GitLab → User Settings → Access Tokens",
        ),
        AgentInstructionStep(
            action="Create a token with the required scopes",
            description="Generate a new personal access token",
        ),
        AgentInstructionStep(
            action="Copy the token value immediately after creation",
            description="Copy the plaintext token — it is only displayed once",
        ),
    ],
    "jenkins": [
        AgentInstructionStep(
            action="Open Jenkins → Manage Jenkins → Manage Credentials",
            description="Navigate to the Jenkins credential store",
        ),
        AgentInstructionStep(
            action="Locate or create the required credential",
            description="Find the existing credential or add a new one",
        ),
        AgentInstructionStep(
            action="Copy the credential value from the credential configuration page",
            description="Retrieve the plaintext credential value",
        ),
    ],
    "kubernetes": [
        AgentInstructionStep(
            action="kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data.<key>}' | base64 -d",
            description="Retrieve the secret value from Kubernetes using kubectl",
            required_tools=["kubectl"],
        ),
        AgentInstructionStep(
            action="Copy the decoded secret value",
            description="Copy the plaintext secret value",
        ),
    ],
    "entra-agent-id": [
        AgentInstructionStep(
            action="https://entra.microsoft.com",
            description="Open Microsoft Entra admin center",
        ),
        AgentInstructionStep(
            action="Review pending sponsor or owner approvals for the target blueprint",
            description="Grant required human approvals before credential reconciliation",
        ),
        AgentInstructionStep(
            action=(
                "Verify Graph app permissions: AgentIdentityBlueprint.Create, "
                "AgentIdentityBlueprint.AddRemoveCreds.All, "
                "AgentIdentityBlueprint.UpdateAuthProperties.All, "
                "Application.ReadWrite.All, Directory.ReadWrite.All"
            ),
            description="Ensure the automation principal has all required permissions and consent",
        ),
        AgentInstructionStep(
            action="Re-run secretzero agent sync --json",
            description="Confirm blueprint and agent identity operations now complete",
        ),
    ],
}


def _build_provider_manual_steps(
    provider_kind: str, method: str, provider_name: str
) -> list[AgentInstructionStep]:
    """Build manual retrieval steps tailored to the given provider kind.

    Args:
        provider_kind: Provider kind string (e.g. 'aws', 'vault').
        method: The capability method that was called (e.g. 'generate_password').
        provider_name: Configured provider name for display purposes.

    Returns:
        List of AgentInstructionStep objects describing the manual process.
    """
    provider_steps = _PROVIDER_MANUAL_STEPS.get(provider_kind)
    if provider_steps:
        return list(provider_steps)

    # Generic fallback steps
    return [
        AgentInstructionStep(
            action=f"Log in to the '{provider_name or provider_kind}' provider",
            description="Authenticate with the provider using your credentials",
        ),
        AgentInstructionStep(
            action=f"Locate the secret generated by '{method}'",
            description="Navigate to the section of the provider that holds the required secret",
        ),
        AgentInstructionStep(
            action="Copy the secret value",
            description="Retrieve and copy the plaintext secret value",
        ),
    ]
