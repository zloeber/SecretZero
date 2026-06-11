"""Tests for GitLab CI/CD variable helpers."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("gitlab")
import gitlab.exceptions

from secretzero.providers.gitlab_variables import (
    get_project_variable,
    upsert_group_variable,
    upsert_project_variable,
    validate_masked_value,
)


class TestValidateMaskedValue:
    def test_rejects_multiline(self):
        with pytest.raises(ValueError, match="single line"):
            validate_masked_value("line1\nline2", masked=True)

    def test_rejects_short_value(self):
        with pytest.raises(ValueError, match="at least 8"):
            validate_masked_value("short", masked=True)

    def test_allows_unmasked_short_value(self):
        validate_masked_value("x", masked=False)


class TestUpsertProjectVariable:
    def test_creates_new_variable(self):
        client = MagicMock()
        project = MagicMock()
        client.projects.get.return_value = project
        project.variables.get.side_effect = gitlab.exceptions.GitlabGetError("missing")

        upsert_project_variable(
            client,
            "mygroup/myproject",
            "API_KEY",
            "abcdefghij",
            masked=True,
            environment_scope="production",
        )

        project.variables.create.assert_called_once()
        payload = project.variables.create.call_args[0][0]
        assert payload["key"] == "API_KEY"
        assert payload["environment_scope"] == "production"

    def test_updates_existing_variable_with_scope_filter(self):
        client = MagicMock()
        project = MagicMock()
        variable = MagicMock()
        client.projects.get.return_value = project
        project.variables.get.return_value = variable

        upsert_project_variable(
            client,
            "123",
            "API_KEY",
            "abcdefghij",
            environment_scope="staging",
        )

        assert variable.filter == {"environment_scope": "staging"}
        variable.save.assert_called_once()
        project.variables.create.assert_not_called()


class TestGetProjectVariable:
    def test_returns_value(self):
        client = MagicMock()
        project = MagicMock()
        variable = MagicMock()
        variable.value = "secret"
        client.projects.get.return_value = project
        project.variables.get.return_value = variable

        assert get_project_variable(client, "group/proj", "API_KEY") == "secret"

    def test_returns_none_on_error(self):
        client = MagicMock()
        project = MagicMock()
        client.projects.get.return_value = project
        project.variables.get.side_effect = gitlab.exceptions.GitlabGetError("missing")

        assert get_project_variable(client, "group/proj", "API_KEY") is None


class TestUpsertGroupVariable:
    def test_creates_group_variable(self):
        client = MagicMock()
        group = MagicMock()
        client.groups.get.return_value = group
        group.variables.get.side_effect = gitlab.exceptions.GitlabGetError("missing")

        upsert_group_variable(client, "mygroup", "SHARED", "abcdefghijkl")

        group.variables.create.assert_called_once()
