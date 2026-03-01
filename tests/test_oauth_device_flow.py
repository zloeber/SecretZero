"""Tests for the generic OAuth device-flow implementation."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from secretzero.oauth.device_flow import (
    DeviceCodeResponse,
    DeviceFlowAccessDeniedError,
    DeviceFlowConfig,
    DeviceFlowError,
    DeviceFlowExpiredError,
    DeviceFlowResult,
    DeviceFlowTimeoutError,
    poll_for_token,
    request_device_code,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def github_config() -> DeviceFlowConfig:
    """A DeviceFlowConfig pointing at GitHub (default scopes)."""
    return DeviceFlowConfig(
        client_id="Iv1.test_client_id",
        device_code_url="https://github.com/login/device/code",
        token_url="https://github.com/login/oauth/access_token",
        scopes=["repo", "workflow"],
    )


@pytest.fixture()
def device_code() -> DeviceCodeResponse:
    """A sample DeviceCodeResponse as returned by the server."""
    return DeviceCodeResponse(
        device_code="dc_test123",
        user_code="ABCD-1234",
        verification_uri="https://github.com/login/device",
        verification_uri_complete="https://github.com/login/device?user_code=ABCD-1234",
        expires_in=900,
        interval=1,  # Keep tests fast
    )


# ---------------------------------------------------------------------------
# DeviceFlowConfig
# ---------------------------------------------------------------------------


class TestDeviceFlowConfig:
    """Tests for configuration dataclass."""

    def test_defaults(self) -> None:
        """Scopes and extra_params default to empty."""
        cfg = DeviceFlowConfig(
            client_id="id",
            device_code_url="https://example.com/device",
            token_url="https://example.com/token",
        )
        assert cfg.scopes == []
        assert cfg.extra_params == {}

    def test_frozen(self) -> None:
        """Config is immutable."""
        cfg = DeviceFlowConfig(
            client_id="id",
            device_code_url="https://example.com/device",
            token_url="https://example.com/token",
        )
        with pytest.raises(AttributeError):
            cfg.client_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# request_device_code
# ---------------------------------------------------------------------------


class TestRequestDeviceCode:
    """Tests for the device-code request step."""

    @patch("secretzero.oauth.device_flow._requests", create=True)
    def test_success(self, _mock: MagicMock, github_config: DeviceFlowConfig) -> None:
        """Happy path: server returns a valid device code."""
        with patch("secretzero.oauth.device_flow.request_device_code") as real:
            # Use the real function but mock requests at a lower level
            pass

        # Actually mock at the import level
        response_data = {
            "device_code": "dc_abc",
            "user_code": "XY12-3456",
            "verification_uri": "https://github.com/login/device",
            "verification_uri_complete": "https://github.com/login/device?user_code=XY12-3456",
            "expires_in": 899,
            "interval": 5,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response_data

        with patch("requests.post", return_value=mock_resp):
            result = request_device_code(github_config)

        assert result.device_code == "dc_abc"
        assert result.user_code == "XY12-3456"
        assert result.verification_uri == "https://github.com/login/device"
        assert result.expires_in == 899
        assert result.interval == 5

    def test_http_error(self, github_config: DeviceFlowConfig) -> None:
        """Non-200 status raises DeviceFlowError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(DeviceFlowError, match="HTTP 401"):
                request_device_code(github_config)

    def test_server_error_field(self, github_config: DeviceFlowConfig) -> None:
        """Status 200 but response JSON contains an 'error' key."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "error": "unauthorized_client",
            "error_description": "The client is not authorized",
        }

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(DeviceFlowError, match="not authorized"):
                request_device_code(github_config)

    def test_invalid_json(self, github_config: DeviceFlowConfig) -> None:
        """Non-JSON response raises DeviceFlowError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("bad json")

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(DeviceFlowError, match="Invalid JSON"):
                request_device_code(github_config)

    def test_network_error(self, github_config: DeviceFlowConfig) -> None:
        """Network failure raises DeviceFlowError."""
        import requests as _req

        with patch("requests.post", side_effect=_req.ConnectionError("offline")):
            with pytest.raises(DeviceFlowError, match="HTTP request.*failed"):
                request_device_code(github_config)

    def test_requests_not_installed(self, github_config: DeviceFlowConfig) -> None:
        """Missing requests package raises DeviceFlowError."""
        import sys

        # Temporarily hide the requests module so the lazy import fails
        real_requests = sys.modules.get("requests")
        sys.modules["requests"] = None  # type: ignore[assignment]
        try:
            # The function does `import requests as _requests` at call time;
            # with sys.modules["requests"] = None the import will raise.
            with pytest.raises((DeviceFlowError, ImportError)):
                request_device_code(github_config)
        finally:
            if real_requests is not None:
                sys.modules["requests"] = real_requests
            else:
                sys.modules.pop("requests", None)


# ---------------------------------------------------------------------------
# poll_for_token
# ---------------------------------------------------------------------------


class TestPollForToken:
    """Tests for the polling step."""

    def test_immediate_success(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """Token is granted on the first poll."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "gho_abc123",
            "token_type": "bearer",
            "scope": "repo,workflow",
        }

        noop_sleep = MagicMock()
        with patch("requests.post", return_value=mock_resp):
            result = poll_for_token(
                github_config,
                device_code,
                _sleep=noop_sleep,
            )

        assert result.access_token == "gho_abc123"
        assert result.token_type == "bearer"
        assert result.scope == "repo,workflow"
        noop_sleep.assert_called()

    def test_pending_then_success(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """Two pending responses followed by a success."""
        pending = MagicMock()
        pending.json.return_value = {"error": "authorization_pending"}

        success = MagicMock()
        success.json.return_value = {
            "access_token": "gho_final",
            "token_type": "bearer",
            "scope": "repo",
        }

        noop_sleep = MagicMock()
        with patch("requests.post", side_effect=[pending, pending, success]):
            result = poll_for_token(
                github_config,
                device_code,
                _sleep=noop_sleep,
            )

        assert result.access_token == "gho_final"
        assert noop_sleep.call_count == 3  # 3 polls

    def test_slow_down_increases_interval(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """A 'slow_down' response bumps the interval by 5 seconds."""
        slow = MagicMock()
        slow.json.return_value = {"error": "slow_down"}

        success = MagicMock()
        success.json.return_value = {
            "access_token": "gho_slowed",
            "token_type": "bearer",
            "scope": "",
        }

        intervals: list[float] = []

        def capture_sleep(secs: float) -> None:
            intervals.append(secs)

        with patch("requests.post", side_effect=[slow, success]):
            result = poll_for_token(
                github_config,
                device_code,
                _sleep=capture_sleep,
            )

        assert result.access_token == "gho_slowed"
        # First sleep = device_code.interval (1), second = 1+5 = 6
        assert intervals == [1, 6]

    def test_expired_token_raises(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """An 'expired_token' response raises DeviceFlowExpiredError."""
        expired = MagicMock()
        expired.json.return_value = {"error": "expired_token"}

        noop_sleep = MagicMock()
        with patch("requests.post", return_value=expired):
            with pytest.raises(DeviceFlowExpiredError, match="expired"):
                poll_for_token(
                    github_config,
                    device_code,
                    _sleep=noop_sleep,
                )

    def test_access_denied_raises(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """An 'access_denied' response raises DeviceFlowAccessDeniedError."""
        denied = MagicMock()
        denied.json.return_value = {"error": "access_denied"}

        noop_sleep = MagicMock()
        with patch("requests.post", return_value=denied):
            with pytest.raises(DeviceFlowAccessDeniedError, match="denied"):
                poll_for_token(
                    github_config,
                    device_code,
                    _sleep=noop_sleep,
                )

    def test_unknown_error_raises(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """An unknown error code raises generic DeviceFlowError."""
        unknown = MagicMock()
        unknown.json.return_value = {
            "error": "server_error",
            "error_description": "Something broke",
        }

        noop_sleep = MagicMock()
        with patch("requests.post", return_value=unknown):
            with pytest.raises(DeviceFlowError, match="Something broke"):
                poll_for_token(
                    github_config,
                    device_code,
                    _sleep=noop_sleep,
                )

    def test_timeout(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """Exceeding max_wait raises DeviceFlowTimeoutError."""
        pending = MagicMock()
        pending.json.return_value = {"error": "authorization_pending"}

        # Simulate clock advancing past the deadline
        call_count = 0
        real_monotonic = time.monotonic

        def advancing_sleep(_secs: float) -> None:
            nonlocal call_count
            call_count += 1

        # Use max_wait=1 and device interval=1, so after first sleep + poll
        # we should exceed the deadline
        short_device = DeviceCodeResponse(
            device_code="dc_short",
            user_code="AAAA-0000",
            verification_uri="https://github.com/login/device",
            expires_in=1,  # very short
            interval=2,  # interval > expires_in → immediate timeout
        )

        with patch("requests.post", return_value=pending):
            with pytest.raises(DeviceFlowTimeoutError, match="timed out"):
                poll_for_token(
                    github_config,
                    short_device,
                    max_wait=1,
                    _sleep=advancing_sleep,
                )

    def test_network_error_during_poll(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """Network failure during polling raises DeviceFlowError."""
        import requests as _req

        noop_sleep = MagicMock()
        with patch("requests.post", side_effect=_req.ConnectionError("offline")):
            with pytest.raises(DeviceFlowError, match="HTTP request.*failed"):
                poll_for_token(
                    github_config,
                    device_code,
                    _sleep=noop_sleep,
                )

    def test_result_includes_raw(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """DeviceFlowResult.raw contains the full server response."""
        raw = {
            "access_token": "gho_raw",
            "token_type": "bearer",
            "scope": "repo",
            "extra_field": "bonus",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = raw

        noop_sleep = MagicMock()
        with patch("requests.post", return_value=mock_resp):
            result = poll_for_token(
                github_config,
                device_code,
                _sleep=noop_sleep,
            )

        assert result.raw == raw
        assert result.raw["extra_field"] == "bonus"

    def test_refresh_token_returned(
        self,
        github_config: DeviceFlowConfig,
        device_code: DeviceCodeResponse,
    ) -> None:
        """If the server returns a refresh token it is captured."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "gho_fresh",
            "token_type": "bearer",
            "scope": "",
            "refresh_token": "ghr_refresh123",
            "expires_in": 28800,
        }

        noop_sleep = MagicMock()
        with patch("requests.post", return_value=mock_resp):
            result = poll_for_token(
                github_config,
                device_code,
                _sleep=noop_sleep,
            )

        assert result.refresh_token == "ghr_refresh123"
        assert result.expires_in == 28800


# ---------------------------------------------------------------------------
# GitHubAuth.authenticate_device_flow
# ---------------------------------------------------------------------------


class TestGitHubAuthDeviceFlow:
    """Tests for the GitHub-specific wrapper around the device flow."""

    def test_happy_path(self) -> None:
        """authenticate_device_flow returns the token dict on success."""
        from secretzero.providers.github import GitHubAuth

        auth = GitHubAuth({})

        mock_device = DeviceCodeResponse(
            device_code="dc_1",
            user_code="AAAA-1111",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=1,
        )

        mock_result = DeviceFlowResult(
            access_token="gho_happy",
            token_type="bearer",
            scope="repo,workflow",
            raw={"access_token": "gho_happy"},
        )

        with (
            patch(
                "secretzero.oauth.device_flow.request_device_code",
                return_value=mock_device,
            ),
            patch(
                "secretzero.oauth.device_flow.poll_for_token",
                return_value=mock_result,
            ),
        ):
            result = auth.authenticate_device_flow(
                client_id="Iv1.test",
                scopes=["repo"],
                open_browser=False,
                _sleep=MagicMock(),
            )

        assert result["access_token"] == "gho_happy"
        assert result["scope"] == "repo,workflow"
        # Token should be stored in config for subsequent authenticate() calls
        assert auth.config["token"] == "gho_happy"

    def test_callback_invoked(self) -> None:
        """The on_user_code callback is called with the user code."""
        from secretzero.providers.github import GitHubAuth

        auth = GitHubAuth({})
        callback = MagicMock()

        mock_device = DeviceCodeResponse(
            device_code="dc_cb",
            user_code="BBBB-2222",
            verification_uri="https://github.com/login/device",
            verification_uri_complete="https://github.com/login/device?user_code=BBBB-2222",
            expires_in=900,
            interval=1,
        )

        mock_result = DeviceFlowResult(
            access_token="gho_cb",
            token_type="bearer",
            scope="repo",
            raw={},
        )

        with (
            patch(
                "secretzero.oauth.device_flow.request_device_code",
                return_value=mock_device,
            ),
            patch(
                "secretzero.oauth.device_flow.poll_for_token",
                return_value=mock_result,
            ),
        ):
            auth.authenticate_device_flow(
                client_id="Iv1.test",
                open_browser=False,
                on_user_code=callback,
                _sleep=MagicMock(),
            )

        callback.assert_called_once_with(
            "BBBB-2222",
            "https://github.com/login/device",
            "https://github.com/login/device?user_code=BBBB-2222",
        )

    def test_default_scopes_used(self) -> None:
        """When no scopes are given, GITHUB_DEFAULT_OAUTH_SCOPES are used."""
        from secretzero.providers.github import (
            GITHUB_DEFAULT_OAUTH_SCOPES,
            GitHubAuth,
        )

        auth = GitHubAuth({})

        captured_config = {}

        def fake_request_device_code(cfg: DeviceFlowConfig) -> DeviceCodeResponse:
            captured_config["scopes"] = cfg.scopes
            return DeviceCodeResponse(
                device_code="dc",
                user_code="CC",
                verification_uri="https://github.com/login/device",
                expires_in=900,
                interval=1,
            )

        mock_result = DeviceFlowResult(
            access_token="gho_def",
            token_type="bearer",
            scope="",
            raw={},
        )

        with (
            patch(
                "secretzero.oauth.device_flow.request_device_code",
                side_effect=fake_request_device_code,
            ),
            patch(
                "secretzero.oauth.device_flow.poll_for_token",
                return_value=mock_result,
            ),
        ):
            auth.authenticate_device_flow(
                client_id="Iv1.test",
                open_browser=False,
                _sleep=MagicMock(),
            )

        assert captured_config["scopes"] == GITHUB_DEFAULT_OAUTH_SCOPES

    def test_ghes_urls(self) -> None:
        """A custom github_url uses the correct endpoints."""
        from secretzero.providers.github import GitHubAuth

        auth = GitHubAuth({"github_url": "https://git.corp.example.com"})

        captured_config: dict[str, str] = {}

        def fake_request_device_code(cfg: DeviceFlowConfig) -> DeviceCodeResponse:
            captured_config["device_code_url"] = cfg.device_code_url
            captured_config["token_url"] = cfg.token_url
            return DeviceCodeResponse(
                device_code="dc",
                user_code="DD",
                verification_uri="https://git.corp.example.com/login/device",
                expires_in=900,
                interval=1,
            )

        mock_result = DeviceFlowResult(
            access_token="gho_ghes",
            token_type="bearer",
            scope="",
            raw={},
        )

        with (
            patch(
                "secretzero.oauth.device_flow.request_device_code",
                side_effect=fake_request_device_code,
            ),
            patch(
                "secretzero.oauth.device_flow.poll_for_token",
                return_value=mock_result,
            ),
        ):
            auth.authenticate_device_flow(
                client_id="Iv1.test",
                open_browser=False,
                _sleep=MagicMock(),
            )

        assert (
            captured_config["device_code_url"] == "https://git.corp.example.com/login/device/code"
        )
        assert (
            captured_config["token_url"] == "https://git.corp.example.com/login/oauth/access_token"
        )

    def test_device_flow_failure_raises_runtime_error(self) -> None:
        """DeviceFlowError from request_device_code is wrapped in RuntimeError."""
        from secretzero.providers.github import GitHubAuth

        auth = GitHubAuth({})

        with patch(
            "secretzero.oauth.device_flow.request_device_code",
            side_effect=DeviceFlowError("boom"),
        ):
            with pytest.raises(RuntimeError, match="Failed to start.*boom"):
                auth.authenticate_device_flow(
                    client_id="Iv1.test",
                    open_browser=False,
                    _sleep=MagicMock(),
                )

    def test_poll_failure_raises_runtime_error(self) -> None:
        """DeviceFlowError from poll_for_token is wrapped in RuntimeError."""
        from secretzero.providers.github import GitHubAuth

        auth = GitHubAuth({})

        mock_device = DeviceCodeResponse(
            device_code="dc",
            user_code="EE",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=1,
        )

        with (
            patch(
                "secretzero.oauth.device_flow.request_device_code",
                return_value=mock_device,
            ),
            patch(
                "secretzero.oauth.device_flow.poll_for_token",
                side_effect=DeviceFlowExpiredError("expired"),
            ),
        ):
            with pytest.raises(RuntimeError, match="device flow failed.*expired"):
                auth.authenticate_device_flow(
                    client_id="Iv1.test",
                    open_browser=False,
                    _sleep=MagicMock(),
                )
