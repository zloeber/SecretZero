"""Tests for GitLab group access token generator and provider methods."""

from unittest.mock import MagicMock, patch

import pytest

from secretzero.generators.gitlab_group_token import GitLabGroupTokenGenerator
from secretzero.providers.gitlab import GitLabProvider


class TestGitLabGroupTokenGenerator:
    def test_validate_configuration_requires_token_name(self):
        generator = GitLabGroupTokenGenerator({"scopes": ["api"]})
        valid, error = generator.validate_configuration()
        assert valid is False
        assert "token_name" in (error or "")

    def test_generate_delegates_to_provider(self):
        provider = MagicMock()
        provider.generate_group_access_token_with_manifest.return_value = "glpat-group-test"
        generator = GitLabGroupTokenGenerator(
            {
                "provider": "gitlab",
                "_provider_instance": provider,
                "token_name": "org-deploy",
                "scopes": ["read_repository"],
                "group": "myorg",
            }
        )

        result = generator.generate()

        assert result == "glpat-group-test"
        provider.generate_group_access_token_with_manifest.assert_called_once()
        manifest = provider.generate_group_access_token_with_manifest.call_args[0][0]
        assert manifest["token_name"] == "org-deploy"
        assert manifest["revoke_existing"] is True


class TestGitLabGroupAccessTokenProvider:
    def test_generate_group_access_token(self):
        provider = GitLabProvider("gitlab", config={"auth": {"token": "bootstrap"}})
        mock_client = MagicMock()
        group = MagicMock()
        token_obj = MagicMock()
        token_obj.token = "glpat-created"
        token_obj.id = 55
        group.access_tokens.create.return_value = token_obj
        group.access_tokens.list.return_value = []
        mock_client.groups.get.return_value = group
        provider.auth._client = mock_client

        with patch(
            "secretzero.providers.gitlab.resolve_gitlab_group",
            return_value="myorg",
        ):
            token = provider.generate_group_access_token(
                token_name="deploy",
                scopes=["read_repository"],
                group="myorg",
                access_level=30,
                expires_in_days=90,
            )

        assert token == "glpat-created"

    def test_generate_group_access_token_with_manifest(self):
        provider = GitLabProvider("gitlab", config={"auth": {"token": "bootstrap"}})
        provider.generate_group_access_token = MagicMock(return_value="glpat-manifest")

        result = provider.generate_group_access_token_with_manifest(
            {
                "token_name": "deploy",
                "scopes": ["api"],
                "group": "auto",
                "revoke_existing": False,
            }
        )

        assert result == "glpat-manifest"
        provider.generate_group_access_token.assert_called_once()
