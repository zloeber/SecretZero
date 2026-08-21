"""Tests for GitLab group service account generator."""

from unittest.mock import MagicMock, patch

from secretzero.generators.gitlab_group_service_account import GitLabGroupServiceAccountGenerator
from secretzero.providers.gitlab import GitLabProvider


def test_generator_returns_structured_payload():
    provider = MagicMock()
    provider.provision_group_service_account_with_manifest.return_value = {
        "token": "glpat-sa",
        "service_account_user_id": 123,
        "token_id": 456,
    }
    generator = GitLabGroupServiceAccountGenerator(
        {
            "provider": "gitlab",
            "_provider_instance": provider,
            "service_account_name": "bot",
            "token_name": "token",
            "scopes": ["api"],
        }
    )

    result = generator.generate()

    assert result["token"] == "glpat-sa"
    assert result["service_account_user_id"] == 123


def test_provider_provision_group_service_account():
    provider = GitLabProvider("gitlab", config={"auth": {"token": "bootstrap"}})
    mock_client = MagicMock()
    provider.auth._client = mock_client

    with (
        patch(
            "secretzero.providers.gitlab.resolve_gitlab_group",
            return_value="myorg/platform",
        ),
        patch(
            "secretzero.providers.gitlab.resolve_gitlab_top_level_group",
            return_value="myorg",
        ),
        patch(
            "secretzero.providers.gitlab.create_group_service_account",
            return_value={"user_id": 10, "username": "sa_bot"},
        ),
        patch(
            "secretzero.providers.gitlab.create_service_account_pat",
            return_value={"token": "glpat-x", "token_id": 20, "expires_at": "2027-01-01"},
        ),
        patch("secretzero.providers.gitlab.apply_memberships") as mock_members,
    ):
        result = provider.provision_group_service_account(
            service_account_name="bot",
            token_name="token",
            scopes=["api"],
            memberships=[{"resource_type": "project", "resource": "myorg/app", "access_level": 30}],
        )

    assert result["token"] == "glpat-x"
    assert result["service_account_user_id"] == 10
    mock_members.assert_called_once()
