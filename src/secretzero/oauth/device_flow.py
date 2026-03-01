"""Generic OAuth 2.0 Device Authorization Grant (RFC 8628).

This module implements the device flow used by CLI tools to authenticate
users via a browser.  The flow works as follows:

1. **Device code request** – the CLI asks the authorization server for a
   one-time user code and a device code.
2. **User interaction** – the CLI displays the user code and a URL.  The
   user visits the URL in any browser and enters the code.
3. **Token polling** – the CLI polls the token endpoint until the user
   completes authorization (or the code expires).

The implementation is provider-agnostic: callers supply endpoint URLs and
a ``client_id`` via :class:`DeviceFlowConfig`.

Example (GitHub)::

    from secretzero.oauth.device_flow import (
        DeviceFlowConfig,
        request_device_code,
        poll_for_token,
    )

    cfg = DeviceFlowConfig(
        client_id="Iv1.abc123",
        device_code_url="https://github.com/login/device/code",
        token_url="https://github.com/login/oauth/access_token",
        scopes=["repo", "workflow"],
    )
    device = request_device_code(cfg)
    print(f"Enter code {device.user_code} at {device.verification_uri}")
    result = poll_for_token(cfg, device)
    print(f"Token: {result.access_token}")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Configuration & result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceFlowConfig:
    """Configuration for initiating a device-flow authorization.

    Attributes:
        client_id: OAuth application client ID.
        device_code_url: Authorization-server endpoint that issues device codes.
        token_url: Token endpoint polled after the user authorizes.
        scopes: OAuth scopes to request.
        extra_params: Additional key-value pairs sent with every request
            (e.g. ``{"audience": "..."}``) for providers that need them.
    """

    client_id: str
    device_code_url: str
    token_url: str
    scopes: list[str] = field(default_factory=list)
    extra_params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceCodeResponse:
    """Parsed response from the device-code endpoint.

    Attributes:
        device_code: Opaque code used when polling for the token.
        user_code: Short code the user enters in the browser.
        verification_uri: URL the user visits.
        verification_uri_complete: Optional URL with the user code embedded.
        expires_in: Lifetime of the device code in seconds.
        interval: Minimum polling interval in seconds.
    """

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None = None
    expires_in: int = 900
    interval: int = 5


@dataclass(frozen=True)
class DeviceFlowResult:
    """Successful token response from the device flow.

    Attributes:
        access_token: The OAuth access token.
        token_type: Token type (usually ``bearer``).
        scope: Space-separated scopes granted.
        refresh_token: Optional refresh token.
        expires_in: Token lifetime in seconds (0 = non-expiring).
        raw: Full JSON response from the token endpoint.
    """

    access_token: str
    token_type: str = "bearer"
    scope: str = ""
    refresh_token: str | None = None
    expires_in: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DeviceFlowError(Exception):
    """Base exception for device-flow errors."""


class DeviceFlowExpiredError(DeviceFlowError):
    """The device code expired before the user authorized."""


class DeviceFlowAccessDeniedError(DeviceFlowError):
    """The user explicitly denied authorization."""


class DeviceFlowTimeoutError(DeviceFlowError):
    """Polling exceeded the maximum allowed duration."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def request_device_code(config: DeviceFlowConfig) -> DeviceCodeResponse:
    """Request a device code from the authorization server.

    Args:
        config: Device-flow configuration.

    Returns:
        Parsed device-code response.

    Raises:
        DeviceFlowError: If the server returns an error or the request fails.
    """
    try:
        import requests as _requests
    except ImportError as exc:
        raise DeviceFlowError(
            "The 'requests' package is required for OAuth device flow. "
            "Install it with: pip install requests"
        ) from exc

    payload: dict[str, str] = {
        "client_id": config.client_id,
        **config.extra_params,
    }
    if config.scopes:
        payload["scope"] = " ".join(config.scopes)

    headers = {"Accept": "application/json"}

    try:
        resp = _requests.post(
            config.device_code_url,
            data=payload,
            headers=headers,
            timeout=30,
        )
    except _requests.RequestException as exc:
        raise DeviceFlowError(f"HTTP request to device-code endpoint failed: {exc}") from exc

    if resp.status_code != 200:
        raise DeviceFlowError(
            f"Device-code request failed (HTTP {resp.status_code}): {resp.text[:500]}"
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise DeviceFlowError(f"Invalid JSON in device-code response: {exc}") from exc

    if "error" in data:
        raise DeviceFlowError(
            f"Device-code server error: {data.get('error_description', data['error'])}"
        )

    return DeviceCodeResponse(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_uri=data["verification_uri"],
        verification_uri_complete=data.get("verification_uri_complete"),
        expires_in=int(data.get("expires_in", 900)),
        interval=int(data.get("interval", 5)),
    )


def poll_for_token(
    config: DeviceFlowConfig,
    device: DeviceCodeResponse,
    *,
    max_wait: int = 0,
    _sleep: Any = None,
) -> DeviceFlowResult:
    """Poll the token endpoint until the user authorizes or the code expires.

    This function blocks until one of:
    - The user authorizes the device (returns :class:`DeviceFlowResult`).
    - The device code expires (:class:`DeviceFlowExpiredError`).
    - The user denies access (:class:`DeviceFlowAccessDeniedError`).
    - *max_wait* seconds elapse (:class:`DeviceFlowTimeoutError`).

    Args:
        config: Device-flow configuration (same instance used with
            :func:`request_device_code`).
        device: The device-code response to poll for.
        max_wait: Maximum seconds to poll.  ``0`` means use the device
            code's ``expires_in`` value.
        _sleep: Override for ``time.sleep`` (used in tests).

    Returns:
        Parsed token response.

    Raises:
        DeviceFlowExpiredError: Code expired.
        DeviceFlowAccessDeniedError: User denied.
        DeviceFlowTimeoutError: Polling exceeded *max_wait*.
        DeviceFlowError: Unexpected error from the token endpoint.
    """
    try:
        import requests as _requests
    except ImportError as exc:
        raise DeviceFlowError(
            "The 'requests' package is required for OAuth device flow. "
            "Install it with: pip install requests"
        ) from exc

    sleep_fn = _sleep or time.sleep
    deadline = time.monotonic() + (max_wait or device.expires_in)
    interval = device.interval

    headers = {"Accept": "application/json"}
    payload: dict[str, str] = {
        "client_id": config.client_id,
        "device_code": device.device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        **config.extra_params,
    }

    while True:
        sleep_fn(interval)

        if time.monotonic() > deadline:
            raise DeviceFlowTimeoutError(
                "OAuth device flow timed out waiting for user authorization"
            )

        try:
            resp = _requests.post(
                config.token_url,
                data=payload,
                headers=headers,
                timeout=30,
            )
        except _requests.RequestException as exc:
            raise DeviceFlowError(f"HTTP request to token endpoint failed: {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise DeviceFlowError(f"Invalid JSON in token response: {exc}") from exc

        error = data.get("error")
        if error is None and "access_token" in data:
            # Success!
            return DeviceFlowResult(
                access_token=data["access_token"],
                token_type=data.get("token_type", "bearer"),
                scope=data.get("scope", ""),
                refresh_token=data.get("refresh_token"),
                expires_in=int(data.get("expires_in", 0)),
                raw=data,
            )

        if error == "authorization_pending":
            # User hasn't entered the code yet — keep polling.
            continue

        if error == "slow_down":
            # Server wants us to back off.
            interval += 5
            continue

        if error == "expired_token":
            raise DeviceFlowExpiredError("The device code expired. Please restart the login flow.")

        if error == "access_denied":
            raise DeviceFlowAccessDeniedError(
                "Authorization was denied. The user cancelled the login."
            )

        # Unknown/unhandled error
        desc = data.get("error_description", error)
        raise DeviceFlowError(f"Token endpoint returned error: {desc}")
