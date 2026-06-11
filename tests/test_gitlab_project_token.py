"""Tests for GitLab project access token generator and provider methods."""

from unittest.mock import MagicMock, patch

import pytest

from secretzero.generators.gitlab_project_token import GitLabProjectTokenGenerator
from secretzero.providers.gitlab import GitLabProvider


class TestGitLabProjectTokenGenerator:
    def test_validate_configuration_requires_token_name(self):
        generator = GitLabProjectTokenGenerator({"scopes": ["api"]})
        valid, error = generator.validate_configuration()
        assert valid is False
        assert "token_name" in (error or "")

    def test_validate_configuration_rejects_unknown_scope(self):
        generator = GitLabProjectTokenGenerator(
            {"token_name": "ci", "scopes": ["not_a_real_scope"]}
        )
        valid, error = generator.validate_configuration()
        assert valid is False
        assert "Unknown scopes" in (error or "")

    def test_generate_delegates_to_provider(self):
        provider = MagicMock()
        provider.generate_project_access_token_with_manifest.return_value = "glpat-test-token"
        generator = GitLabProjectTokenGenerator(
            {
                "provider": "gitlab",
                "_provider_instance": provider,
                "token_name": "ci-token",
                "scopes": ["api"],
                "project": "group/project",
            }
        )

        result = generator.generate()

        assert result == "glpat-test-token"
        provider.generate_project_access_token_with_manifest.assert_called_once()
        manifest = provider.generate_project_access_token_with_manifest.call_args[0][0]
        assert manifest["token_name"] == "ci-token"
        assert manifest["revoke_existing"] is True


class TestGitLabProjectAccessTokenProvider:
    def test_generate_project_access_token(self):
        provider = GitLabProvider("gitlab", config={"auth": {"token": "bootstrap"}})
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_project = MagicMock()
        created = MagicMock()
        created.token = "glptok-abc"
        mock_project.access_tokens.create.return_value = created
        mock_client.projects.get.return_value = mock_project
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        with patch(
            "secretzero.providers.gitlab.resolve_gitlab_project",
            return_value="mygroup/myproject",
        ):
            token = provider.generate_project_access_token(
                token_name="secretzero-ci",
                scopes=["api", "read_repository"],
                project="auto",
            )

        assert token == "glptok-abc"
        mock_project.access_tokens.create.assert_called_once()

    def test_revoke_project_access_tokens_by_name(self):
        provider = GitLabProvider("gitlab", config={"auth": {"token": "bootstrap"}})
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_project = MagicMock()
        token_a = MagicMock()
        token_a.name = "secretzero-ci"
        token_b = MagicMock()
        token_b.name = "other"
        mock_project.access_tokens.list.return_value = [token_a, token_b]
        mock_client.projects.get.return_value = mock_project
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        with patch(
            "secretzero.providers.gitlab.resolve_gitlab_project",
            return_value="mygroup/myproject",
        ):
            revoked = provider.revoke_project_access_tokens_by_name("secretzero-ci")

        assert revoked == 1
        token_a.delete.assert_called_once()
        token_b.delete.assert_not_called()
