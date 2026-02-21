"""Provider capabilities interface for SecretZero.

This module defines the interface for providers to declare their capabilities,
enabling auto-discovery, schema validation, and programmatic access to provider
operations like generation, retrieval, storage, rotation, and deletion.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CapabilityType(str, Enum):
    """Types of provider capabilities."""

    GENERATE = "generate"
    RETRIEVE = "retrieve"
    STORE = "store"
    ROTATE = "rotate"
    DELETE = "delete"


class ParameterSchema(BaseModel):
    """Schema for a method parameter."""

    type: str = Field(description="Parameter type (e.g., 'str', 'int', 'dict')")
    required: bool = Field(default=False, description="Whether parameter is required")
    default: Any = Field(default=None, description="Default value if not required")
    description: str = Field(default="", description="Parameter description")


class MethodSignature(BaseModel):
    """Schema for a provider method signature."""

    name: str = Field(description="Method name (e.g., 'generate_password')")
    description: str = Field(description="Human-readable method description")
    return_type: str = Field(description="Return type (e.g., 'str', 'dict')")
    parameters: dict[str, ParameterSchema] = Field(
        default_factory=dict, description="Parameter schemas by name"
    )


class Capability(BaseModel):
    """Definition of a provider capability."""

    capability_type: CapabilityType = Field(description="Type of capability")
    method: MethodSignature = Field(description="Method implementation details")
    requires_auth: bool = Field(
        default=True, description="Whether this capability requires authentication"
    )
    supported_targets: list[str] = Field(
        default_factory=list,
        description="Target types that can use this capability (empty = all)",
    )


class ProviderCapabilities(BaseModel):
    """Collection of capabilities a provider offers."""

    provider_kind: str = Field(description="Provider type identifier")
    version: str = Field(default="1.0", description="Provider version")
    capabilities: list[Capability] = Field(
        default_factory=list, description="Available capabilities"
    )

    def get_capability(self, method_name: str) -> Capability | None:
        """Get capability by method name.

        Args:
            method_name: Name of the method to find

        Returns:
            Capability if found, None otherwise
        """
        for capability in self.capabilities:
            if capability.method.name == method_name:
                return capability
        return None

    def has_capability(self, capability_type: CapabilityType) -> bool:
        """Check if provider has any capability of given type.

        Args:
            capability_type: Type of capability to check

        Returns:
            True if provider has at least one capability of this type
        """
        return any(c.capability_type == capability_type for c in self.capabilities)

    def list_methods_by_type(self, capability_type: CapabilityType) -> list[str]:
        """List all method names for a capability type.

        Args:
            capability_type: Type of capability to filter by

        Returns:
            List of method names
        """
        return [c.method.name for c in self.capabilities if c.capability_type == capability_type]


class IProviderWithCapabilities(ABC):
    """Interface for providers that declare their capabilities.

    Providers should inherit from this interface and implement get_capabilities()
    to declare all operations they support. The base implementation uses
    introspection to auto-discover methods.
    """

    @classmethod
    @abstractmethod
    def get_capabilities(cls) -> ProviderCapabilities:
        """Declare all capabilities this provider offers.

        This method should return a ProviderCapabilities object describing
        all methods and their signatures. The default implementation in
        BaseProvider uses introspection to find methods starting with
        'generate_', 'retrieve_', 'store_', 'rotate_', or 'delete_'.

        Returns:
            ProviderCapabilities describing all methods and their signatures
        """
        pass

    @abstractmethod
    def list_available_methods(self) -> list[str]:
        """List all callable capability methods on this provider instance.

        Returns:
            List of method names available after authentication
        """
        pass

    @abstractmethod
    def get_method_schema(self, method_name: str) -> MethodSignature:
        """Get schema for a specific method.

        Args:
            method_name: Name of method to inspect

        Returns:
            MethodSignature with parameter and return types

        Raises:
            ValueError: If method not found
        """
        pass
