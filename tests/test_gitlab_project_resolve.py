"""Tests for GitLab project path resolution."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from secretzero.providers.gitlab_project_resolve import (
    parse_gitlab_remote_project,
    resolve_gitlab_project,
)


class TestParseGitlabRemoteProject:
    def test_ssh_gitlab_com(self):
        assert (
            parse_gitlab_remote_project("git@gitlab.com:mygroup/myproject.git")
            == "mygroup/myproject"
        )

    def test_https_gitlab_com(self):
        assert (
            parse_gitlab_remote_project("https://gitlab.com/mygroup/myproject.git")
            == "mygroup/myproject"
        )

    def test_nested_group_path(self):
        assert (
            parse_gitlab_remote_project("https://gitlab.example.com/org/team/app.git")
            == "org/team/app"
        )

    def test_invalid_remote(self):
        assert parse_gitlab_remote_project("not-a-url") is None


class TestResolveGitlabProject:
    def test_explicit_project(self):
        assert (
            resolve_gitlab_project(project="mygroup/myproject", provider_config={})
            == "mygroup/myproject"
        )

    def test_provider_project_fallback(self):
        assert (
            resolve_gitlab_project(
                project="auto",
                provider_config={"project": "provider/group"},
            )
            == "provider/group"
        )

    def test_ci_project_path(self, monkeypatch):
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PROJECT_PATH", "ci/group/project")
        assert resolve_gitlab_project(project="auto", provider_config={}) == "ci/group/project"

    def test_git_remote_fallback(self, tmp_path: Path):
        with patch(
            "secretzero.providers.gitlab_project_resolve._git_origin_remote",
            return_value="git@gitlab.com:remote/group.git",
        ):
            assert resolve_gitlab_project(project="auto", provider_config={}, cwd=tmp_path) == (
                "remote/group"
            )

    def test_failure_includes_remediation(self, tmp_path: Path):
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "secretzero.providers.gitlab_project_resolve._git_origin_remote",
                return_value=None,
            ):
                with pytest.raises(ValueError, match="Could not resolve GitLab project"):
                    resolve_gitlab_project(project="auto", provider_config={}, cwd=tmp_path)
