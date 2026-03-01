"""OAuth utilities for SecretZero.

Provides generic OAuth device-flow authentication (RFC 8628) that can
be used by any provider that supports the Device Authorization Grant.
"""

from secretzero.oauth.device_flow import (
    DeviceFlowConfig,
    DeviceFlowError,
    DeviceFlowResult,
    poll_for_token,
    request_device_code,
)

__all__ = [
    "DeviceFlowConfig",
    "DeviceFlowError",
    "DeviceFlowResult",
    "request_device_code",
    "poll_for_token",
]
