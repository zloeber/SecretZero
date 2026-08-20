"""Gated live validation for GitLab group automation.

Skipped unless ``GITLAB_TOKEN`` and ``GITLAB_TEST_GROUP`` are set.
Requires Owner role on the test group for group token / service account APIs.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("GITLAB_TOKEN") and os.environ.get("GITLAB_TEST_GROUP")),
    reason="Requires GITLAB_TOKEN and GITLAB_TEST_GROUP",
)


@pytest.fixture
def gitlab_provider():
    from secretzero.providers.gitlab import GitLabProvider

    provider = GitLabProvider(
        "gitlab",
        config={
            "auth": {
                "kind": "token",
                "config": {
                    "token": os.environ["GITLAB_TOKEN"],
                    "url": os.environ.get("GITLAB_URL", "https://gitlab.com"),
                },
            },
            "group": os.environ["GITLAB_TEST_GROUP"],
        },
    )
    ok, message = provider.test_connection()
    assert ok, message or "GitLab connection failed"
    return provider


def test_live_gitlab_group_resolve(gitlab_provider):
    from secretzero.providers.gitlab_group_resolve import resolve_gitlab_group

    group = resolve_gitlab_group(
        group="auto",
        provider_config=gitlab_provider.config or {},
    )
    assert group
    assert group == os.environ["GITLAB_TEST_GROUP"] or group.startswith(
        os.environ["GITLAB_TEST_GROUP"].split("/")[0]
    )


def test_live_gitlab_token_info(gitlab_provider):
    info = gitlab_provider.auth.get_token_info()
    assert isinstance(info, dict)
    assert info.get("token_type")
    # Identity metadata must not contain a raw token field.
    assert "token" not in info


def test_live_gitlab_group_token_create_and_revoke(gitlab_provider):
    """Create then revoke a short-lived group access token (metadata-only asserts)."""
    from secretzero.providers.gitlab_tokens import revoke_group_access_tokens_by_name

    token_name = "secretzero-live-validation"
    token = gitlab_provider.generate_group_access_token(
        token_name=token_name,
        scopes=["read_api"],
        group=os.environ["GITLAB_TEST_GROUP"],
        access_level=30,
        expires_in_days=1,
        description="SecretZero gated live validation",
        revoke_existing=True,
    )
    assert isinstance(token, str) and token
    # Immediately revoke so the live token does not linger.
    revoked = revoke_group_access_tokens_by_name(
        gitlab_provider.auth.get_client(),
        os.environ["GITLAB_TEST_GROUP"],
        token_name,
    )
    assert revoked >= 1
