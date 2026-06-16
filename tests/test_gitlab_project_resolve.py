"""Tests for GitLab project auto-resolution."""

from __future__ import annotations

import pytest

from secretzero.providers.gitlab_project_resolve import (
    parse_gitlab_remote_project,
    resolve_gitlab_project,
)


class TestParseGitlabRemoteProject:
    def test_https_gitlab_com(self) -> None:
        assert (
            parse_gitlab_remote_project("https://gitlab.com/group/subgroup/project.git")
            == "group/subgroup/project"
        )

    def test_ssh_gitlab_com(self) -> None:
        assert parse_gitlab_remote_project("git@gitlab.com:group/project.git") == "group/project"

    def test_empty_remote_returns_none(self) -> None:
        assert parse_gitlab_remote_project("") is None


class TestResolveGitlabProject:
    def test_explicit_project(self) -> None:
        assert (
            resolve_gitlab_project(project="mygroup/myproject", provider_config={})
            == "mygroup/myproject"
        )

    def test_provider_project_fallback(self) -> None:
        assert (
            resolve_gitlab_project(
                project="auto",
                provider_config={"project": "provider/group/project"},
            )
            == "provider/group/project"
        )

    def test_ci_project_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PROJECT_PATH", "ci/group/project")
        assert resolve_gitlab_project(project="auto", provider_config={}) == "ci/group/project"

    def test_missing_project_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not resolve GitLab project"):
            resolve_gitlab_project(project="auto", provider_config={}, cwd="/tmp")
