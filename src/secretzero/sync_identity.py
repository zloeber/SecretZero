"""Collect non-sensitive identity context for lockfile metadata."""

from __future__ import annotations

import getpass
import os
import platform
import socket
import subprocess
from pathlib import Path

from secretzero import __version__
from secretzero.lockfile import LockfileSyncIdentity


def _git_line(args: list[str], cwd: Path | None) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    out = (proc.stdout or "").strip()
    return out or None


def _pick_ci(env: dict[str, str]) -> dict[str, str | None]:
    """Map well-known CI environments to LockfileSyncIdentity CI fields (no tokens)."""
    if env.get("GITHUB_ACTIONS") == "true":
        server = env.get("GITHUB_SERVER_URL", "").rstrip("/")
        repo = env.get("GITHUB_REPOSITORY")
        run_id = env.get("GITHUB_RUN_ID")
        run_url = None
        if server and repo and run_id:
            run_url = f"{server}/{repo}/actions/runs/{run_id}"
        return {
            "ci_system": "github_actions",
            "ci_actor": env.get("GITHUB_ACTOR"),
            "ci_repository": repo,
            "ci_job_id": run_id,
            "ci_run_url": run_url,
            "ci_workflow_name": env.get("GITHUB_WORKFLOW"),
            "ci_pipeline_name": env.get("GITHUB_JOB"),
        }

    if env.get("GITLAB_CI") == "true":
        return {
            "ci_system": "gitlab_ci",
            "ci_actor": env.get("GITLAB_USER_LOGIN") or env.get("CI_COMMIT_AUTHOR"),
            "ci_repository": env.get("CI_PROJECT_PATH"),
            "ci_job_id": env.get("CI_PIPELINE_ID") or env.get("CI_JOB_ID"),
            "ci_run_url": env.get("CI_PIPELINE_URL") or env.get("CI_JOB_URL"),
            "ci_workflow_name": env.get("CI_JOB_NAME"),
            "ci_pipeline_name": env.get("CI_PIPELINE_NAME"),
        }

    if env.get("JENKINS_URL"):
        return {
            "ci_system": "jenkins",
            "ci_actor": env.get("BUILD_USER_ID") or env.get("BUILD_USER"),
            "ci_repository": env.get("GIT_URL") or env.get("JOB_NAME"),
            "ci_job_id": env.get("BUILD_NUMBER"),
            "ci_run_url": env.get("BUILD_URL"),
            "ci_workflow_name": env.get("JOB_NAME"),
            "ci_pipeline_name": env.get("JOB_BASE_NAME"),
        }

    if env.get("CIRCLECI") == "true":
        cu, cr = env.get("CIRCLE_PROJECT_USERNAME"), env.get("CIRCLE_PROJECT_REPONAME")
        circle_repo = f"{cu}/{cr}" if cu and cr else None
        return {
            "ci_system": "circleci",
            "ci_actor": env.get("CIRCLE_USERNAME"),
            "ci_repository": circle_repo,
            "ci_job_id": env.get("CIRCLE_BUILD_NUM") or env.get("CIRCLE_WORKFLOW_ID"),
            "ci_run_url": env.get("CIRCLE_BUILD_URL"),
            "ci_workflow_name": env.get("CIRCLE_WORKFLOW_ID"),
            "ci_pipeline_name": env.get("CIRCLE_JOB"),
        }

    if env.get("BUILDKITE") == "true":
        return {
            "ci_system": "buildkite",
            "ci_actor": env.get("BUILDKITE_BUILD_CREATOR"),
            "ci_repository": env.get("BUILDKITE_REPO"),
            "ci_job_id": env.get("BUILDKITE_BUILD_NUMBER"),
            "ci_run_url": env.get("BUILDKITE_BUILD_URL"),
            "ci_workflow_name": env.get("BUILDKITE_PIPELINE_SLUG"),
            "ci_pipeline_name": env.get("BUILDKITE_PIPELINE_NAME"),
        }

    if env.get("TF_BUILD") == "True":
        return {
            "ci_system": "azure_pipelines",
            "ci_actor": env.get("BUILD_REQUESTEDFOR") or env.get("BUILD_REQUESTEDFOREMAIL"),
            "ci_repository": env.get("BUILD_REPOSITORY_NAME"),
            "ci_job_id": env.get("BUILD_BUILDID"),
            "ci_run_url": env.get("BUILD_URL") or env.get("BUILD_BUILDURI"),
            "ci_workflow_name": env.get("BUILD_DEFINITIONNAME"),
            "ci_pipeline_name": env.get("BUILD_REPOSITORY_NAME"),
        }

    if env.get("TEAMCITY_VERSION"):
        return {
            "ci_system": "teamcity",
            "ci_actor": None,
            "ci_repository": env.get("TEAMCITY_PROJECT_NAME"),
            "ci_job_id": env.get("BUILD_NUMBER"),
            "ci_run_url": None,
            "ci_workflow_name": env.get("TEAMCITY_BUILDCONF_NAME"),
            "ci_pipeline_name": env.get("TEAMCITY_BUILD_TYPE_ID"),
        }

    if env.get("CI") and env.get("TRAVIS") == "true":
        return {
            "ci_system": "travis",
            "ci_actor": None,
            "ci_repository": env.get("TRAVIS_REPO_SLUG"),
            "ci_job_id": env.get("TRAVIS_BUILD_ID"),
            "ci_run_url": env.get("TRAVIS_BUILD_WEB_URL"),
            "ci_workflow_name": env.get("TRAVIS_BUILD_STAGE_NAME"),
            "ci_pipeline_name": env.get("TRAVIS_JOB_NAME"),
        }

    if env.get("CI"):
        return {
            "ci_system": "generic",
            "ci_actor": env.get("CI_USER") or env.get("USER"),
            "ci_repository": None,
            "ci_job_id": env.get("CI_JOB_ID") or env.get("CI_PIPELINE_ID"),
            "ci_run_url": env.get("CI_JOB_URL"),
            "ci_workflow_name": None,
            "ci_pipeline_name": None,
        }

    return {
        "ci_system": None,
        "ci_actor": None,
        "ci_repository": None,
        "ci_job_id": None,
        "ci_run_url": None,
        "ci_workflow_name": None,
        "ci_pipeline_name": None,
    }


def collect_lockfile_sync_identity(
    *,
    client: str = "cli",
    cwd: Path | None = None,
) -> LockfileSyncIdentity:
    """Gather host, user, git, and CI metadata safe to persist in the lockfile."""
    env = {k: str(v) for k, v in os.environ.items() if isinstance(v, str)}
    git_cwd = cwd if cwd is not None else Path.cwd()

    uid: int | None = None
    euid: int | None = None
    try:
        uid = os.getuid()
        euid = os.geteuid()
    except AttributeError:
        pass

    fqdn: str | None = None
    try:
        fqdn = socket.getfqdn()
    except OSError:
        fqdn = None

    hostname: str | None = None
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = None

    git_user_name = _git_line(["config", "user.name"], git_cwd)
    git_user_email = _git_line(["config", "user.email"], git_cwd)
    git_head = _git_line(["rev-parse", "--short", "HEAD"], git_cwd)

    ci = _pick_ci(env)

    env_label = (
        env.get("SZ_SYNC_ENVIRONMENT")
        or env.get("DEPLOYMENT_ENVIRONMENT")
        or env.get("ENVIRONMENT")
        or env.get("ENV")
    )

    return LockfileSyncIdentity(
        client=client,
        secretzero_version=__version__,
        os_user=getpass.getuser(),
        os_uid=uid,
        os_euid=euid,
        hostname=hostname,
        host_fqdn=fqdn,
        platform=platform.platform(),
        environment_label=env_label,
        git_user_name=git_user_name,
        git_user_email=git_user_email,
        git_commit_sha=git_head,
        **ci,
    )
