"""Tests for GitHub PAT generation – provider method and generator."""

import json
import time
from unittest.mock import MagicMock, mock_open, patch

import pytest

from secretzero.generators.github_pat import GitHubPATGenerator
from secretzero.providers.github import (
    GITHUB_PAT_PERMISSIONS,
    GitHubProvider,
    validate_pat_permissions,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Permission validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestValidatePATPermissions:
    """Tests for the standalone permission validation function."""

    def test_valid_permissions(self):
        """Test that valid permissions pass validation."""
        perms = {"contents": "read", "pull_requests": "write", "actions": "read"}
        valid, errors = validate_pat_permissions(perms)
        assert valid is True
        assert errors == []

    def test_empty_permissions(self):
        """Empty dict is valid (will use installation defaults)."""
        valid, errors = validate_pat_permissions({})
        assert valid is True
        assert errors == []

    def test_unknown_permission_name(self):
        """Reject permission names not in the known set."""
        valid, errors = validate_pat_permissions({"nonexistent_scope": "read"})
        assert valid is False
        assert len(errors) == 1
        assert "Unknown permission" in errors[0]

    def test_invalid_access_level(self):
        """Reject access levels not allowed for a given permission."""
        # 'workflows' only allows 'write', not 'read' or 'admin'
        valid, errors = validate_pat_permissions({"workflows": "read"})
        assert valid is False
        assert "Invalid access level" in errors[0]

    def test_multiple_errors(self):
        """Multiple bad entries produce multiple errors."""
        valid, errors = validate_pat_permissions({"bad_scope": "read", "workflows": "admin"})
        assert valid is False
        assert len(errors) == 2

    def test_admin_access_where_allowed(self):
        """Some permissions support 'admin' level."""
        valid, errors = validate_pat_permissions({"repository_projects": "admin"})
        assert valid is True

    def test_admin_access_where_not_allowed(self):
        """Most permissions don't support 'admin'."""
        valid, errors = validate_pat_permissions({"contents": "admin"})
        assert valid is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GitHubProvider.generate_pat
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGitHubProviderGeneratePAT:
    """Tests for GitHubProvider.generate_pat method."""

    def _make_provider(self, **extra_config) -> GitHubProvider:
        config = {
            "token": "ghp_test",
            "repository": "my-org/my-repo",
            "app_id": "12345",
            "installation_id": "67890",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----",
            **extra_config,
        }
        return GitHubProvider("test-github", config=config)

    def test_invalid_permissions_raises(self):
        """generate_pat rejects invalid permissions early."""
        provider = self._make_provider()
        with pytest.raises(ValueError, match="Invalid PAT permissions"):
            provider.generate_pat(permissions={"bad_scope": "read"})

    def test_missing_app_id_raises(self):
        """Must have app_id to create tokens."""
        provider = GitHubProvider("test", config={"token": "ghp_test", "installation_id": "1"})
        with pytest.raises(ValueError, match="app_id"):
            provider.generate_pat()

    def test_missing_installation_id_raises(self):
        """Must have installation_id to create tokens."""
        provider = GitHubProvider("test", config={"token": "ghp_test", "app_id": "1"})
        with pytest.raises(ValueError, match="installation_id"):
            provider.generate_pat()

    def test_missing_private_key_raises(self):
        """Must have private_key for JWT signing."""
        provider = GitHubProvider(
            "test",
            config={
                "token": "ghp_test",
                "app_id": "1",
                "installation_id": "1",
            },
        )
        with pytest.raises(ValueError, match="private key"):
            provider.generate_pat()

    @patch("requests.post")
    @patch("jwt.encode")
    def test_successful_token_creation(self, mock_encode, mock_post):
        """Happy path: API returns a valid token."""
        mock_encode.return_value = "fake.jwt.token"
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "token": "ghs_installation_token_abc123",
            "expires_at": "2026-02-25T12:00:00Z",
        }
        mock_post.return_value = mock_response

        provider = self._make_provider()
        token = provider.generate_pat(permissions={"contents": "read"})

        assert token == "ghs_installation_token_abc123"
        mock_post.assert_called_once()

        # Verify the POST body contains the permissions
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["permissions"] == {"contents": "read"}

    @patch("requests.post")
    @patch("jwt.encode")
    def test_scoped_to_repositories(self, mock_encode, mock_post):
        """Token is scoped to specific repositories when listed."""
        mock_encode.return_value = "jwt"
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"token": "ghs_scoped"}
        mock_post.return_value = mock_response

        provider = self._make_provider()
        provider.generate_pat(repositories=["repo-a", "repo-b"])

        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["repositories"] == ["repo-a", "repo-b"]

    @patch("requests.post")
    @patch("jwt.encode")
    def test_api_error_raises_runtime(self, mock_encode, mock_post):
        """Non-201 response raises RuntimeError."""
        mock_encode.return_value = "jwt"
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Validation Failed"
        mock_post.return_value = mock_response

        provider = self._make_provider()
        with pytest.raises(RuntimeError, match="422"):
            provider.generate_pat()

    @patch("requests.post")
    @patch("jwt.encode")
    def test_private_key_from_file(self, mock_encode, mock_post):
        """Private key can be read from a file path."""
        mock_encode.return_value = "jwt"
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"token": "ghs_from_file"}
        mock_post.return_value = mock_response

        provider = GitHubProvider(
            "test",
            config={
                "token": "ghp_test",
                "app_id": "1",
                "installation_id": "1",
                "private_key_path": "/fake/key.pem",
            },
        )
        with patch(
            "builtins.open",
            mock_open(
                read_data="-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----"
            ),
        ):
            token = provider.generate_pat()

        assert token == "ghs_from_file"

    def test_generate_pat_with_manifest(self):
        """generate_pat_with_manifest unpacks and delegates correctly."""
        provider = self._make_provider()

        manifest = {
            "permissions": {"contents": "read"},
            "repositories": ["repo-a"],
            "token_name": "test-token",
            "expires_in_hours": 1,
        }

        with patch.object(provider, "generate_pat", return_value="ghs_manifest") as mock:
            result = provider.generate_pat_with_manifest(manifest)

        assert result == "ghs_manifest"
        mock.assert_called_once_with(
            permissions={"contents": "read"},
            repositories=["repo-a"],
            repository=None,
            token_name="test-token",
            expires_in_hours=1,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GitHubPATGenerator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGitHubPATGenerator:
    """Tests for the GitHubPATGenerator class."""

    def test_generate_without_provider_raises(self):
        """Raises RuntimeError if no provider instance was injected."""
        gen = GitHubPATGenerator({"provider": "github", "permissions": {"contents": "read"}})
        with pytest.raises(RuntimeError, match="resolved provider instance"):
            gen.generate()

    def test_generate_delegates_to_provider(self):
        """Generator delegates to the provider's generate_pat_with_manifest."""
        mock_provider = MagicMock()
        mock_provider.generate_pat_with_manifest.return_value = "ghs_generated"

        gen = GitHubPATGenerator(
            {
                "provider": "github",
                "permissions": {"contents": "read"},
                "repositories": ["repo-x"],
                "_provider_instance": mock_provider,
            }
        )

        result = gen.generate()

        assert result == "ghs_generated"
        mock_provider.generate_pat_with_manifest.assert_called_once()

        # Verify the manifest passed to the provider
        call_args = mock_provider.generate_pat_with_manifest.call_args[0][0]
        assert call_args["permissions"] == {"contents": "read"}
        assert call_args["repositories"] == ["repo-x"]
        # Internal keys should be excluded
        assert "_provider_instance" not in call_args
        assert "provider" not in call_args

    def test_validate_configuration_valid(self):
        """Valid config passes validation."""
        gen = GitHubPATGenerator(
            {
                "provider": "github",
                "permissions": {"contents": "read", "issues": "write"},
            }
        )
        valid, err = gen.validate_configuration()
        assert valid is True
        assert err is None

    def test_validate_configuration_invalid_permissions(self):
        """Invalid permissions fail validation."""
        gen = GitHubPATGenerator(
            {
                "provider": "github",
                "permissions": {"not_a_real_scope": "read"},
            }
        )
        valid, err = gen.validate_configuration()
        assert valid is False
        assert "Unknown permission" in err

    def test_validate_configuration_no_permissions(self):
        """No permissions is valid (uses installation defaults)."""
        gen = GitHubPATGenerator({"provider": "github"})
        valid, err = gen.validate_configuration()
        assert valid is True

    def test_env_var_fallback(self):
        """Environment variable fallback takes precedence over generation."""
        import os

        os.environ["MY_PAT"] = "env_pat_value"
        try:
            gen = GitHubPATGenerator({"provider": "github"})
            result = gen.generate_with_fallback("MY_PAT")
            assert result == "env_pat_value"
        finally:
            del os.environ["MY_PAT"]

    def test_default_provider_name(self):
        """Default provider name is 'github' when not specified."""
        gen = GitHubPATGenerator({})
        assert gen._provider_name == "github"

    def test_custom_provider_name(self):
        """Custom provider name is stored."""
        gen = GitHubPATGenerator({"provider": "my_gh_app"})
        assert gen._provider_name == "my_gh_app"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Permission reference table completeness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPermissionsReference:
    """Ensure the permission reference table is well-formed."""

    def test_all_access_levels_are_strings(self):
        """Every access level list contains only strings."""
        for perm, levels in GITHUB_PAT_PERMISSIONS.items():
            assert isinstance(levels, list), f"{perm} value should be a list"
            for lvl in levels:
                assert isinstance(lvl, str), f"{perm} level {lvl!r} should be str"

    def test_common_permissions_present(self):
        """Spot-check that commonly used permissions are defined."""
        expected = {"contents", "pull_requests", "issues", "actions", "metadata", "workflows"}
        assert expected.issubset(GITHUB_PAT_PERMISSIONS.keys())

    def test_read_write_are_universal(self):
        """Most permissions should support at least 'read'."""
        for perm, levels in GITHUB_PAT_PERMISSIONS.items():
            # 'workflows' is the sole exception (write-only)
            if perm == "workflows":
                assert "write" in levels
            else:
                assert "read" in levels, f"{perm} should support 'read'"
