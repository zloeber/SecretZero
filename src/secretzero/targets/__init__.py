"""Secret storage targets for SecretZero."""

from secretzero.targets.base import BaseTarget
from secretzero.targets.file import FileTarget

# Optional cloud provider targets
try:
    from secretzero.targets.aws import SecretsManagerTarget, SSMParameterTarget

    _has_aws = True
except ImportError:
    _has_aws = False

try:
    from secretzero.targets.azure import KeyVaultTarget

    _has_azure = True
except ImportError:
    _has_azure = False

try:
    from secretzero.targets.vault import VaultKVTarget

    _has_vault = True
except ImportError:
    _has_vault = False

__all__ = [
    "BaseTarget",
    "FileTarget",
]

if _has_aws:
    __all__.extend(["SSMParameterTarget", "SecretsManagerTarget"])
if _has_azure:
    __all__.append("KeyVaultTarget")
if _has_vault:
    __all__.append("VaultKVTarget")
