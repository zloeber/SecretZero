"""Tests for GitLab group path resolution."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from secretzero.providers.gitlab_group_resolve import (
    derive_group_from_project,
    resolve_gitlab_group,
    resolve_gitlab_top_level_group,
)


def test_explicit_group():
    assert resolve_gitlab_group(group="myorg/platform") == "myorg/platform"


def test_auto_from_ci_namespace():
    with patch.dict(
        "os.environ",
        {"GITLAB_CI": "true", "CI_PROJECT_NAMESPACE": "myorg/platform"},
        clear=False,
    ):
        assert resolve_gitlab_group(group="auto") == "myorg/platform"


def test_auto_from_provider_config():
    assert resolve_gitlab_group(
        group="auto",
        provider_config={"group": "myorg/from-provider"},
    ) == "myorg/from-provider"


def test_auto_from_variables():
    assert resolve_gitlab_group(
        group="auto",
        variables={"gitlab_group": "myorg/from-vars"},
    ) == "myorg/from-vars"


def test_auto_derives_from_project_path():
    with patch(
        "secretzero.providers.gitlab_group_resolve.resolve_gitlab_project",
        return_value="myorg/platform/backend",
    ):
        assert resolve_gitlab_group(group="auto") == "myorg/platform"


def test_derive_group_from_project_strips_repo():
    assert derive_group_from_project("myorg/platform/backend") == "myorg/platform"
    assert derive_group_from_project("solo-project") == "solo-project"


def test_auto_failure_message():
    with patch(
        "secretzero.providers.gitlab_group_resolve.resolve_gitlab_project",
        side_effect=ValueError("no project"),
    ):
        with pytest.raises(ValueError, match="Could not resolve GitLab group"):
            resolve_gitlab_group(group="auto", cwd=Path("/tmp"))


def test_resolve_top_level_group_single_segment():
    assert resolve_gitlab_top_level_group(None, "myorg") == "myorg"


def test_resolve_top_level_group_nested_path():
    assert resolve_gitlab_top_level_group(None, "myorg/platform/team") == "myorg"


def test_resolve_top_level_group_via_api():
    client = MagicMock()
    group = MagicMock()
    group.parent_id = 99
    parent = MagicMock()
    parent.parent_id = None
    parent.full_path = "myorg"
    client.groups.get.side_effect = [group, parent]

    assert resolve_gitlab_top_level_group(client, "myorg/platform") == "myorg"
    assert client.groups.get.call_count == 2
