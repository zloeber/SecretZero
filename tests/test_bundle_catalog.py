"""Tests for the machine-complete bundle capability catalog."""

import json

from secretzero.bundle_catalog import build_bundle_catalog, find_catalog_entry


class TestBuildBundleCatalog:
    def test_includes_core_and_bundle_generators(self):
        catalog = build_bundle_catalog()
        kinds = set(catalog["generator_kinds"])
        assert "random_password" in kinds
        assert "github_pat" in kinds
        assert "gitlab_project_token" in kinds

    def test_includes_gitlab_targets(self):
        catalog = build_bundle_catalog()
        kinds = set(catalog["target_kinds"])
        assert "gitlab_variable" in kinds
        assert "gitlab_group_variable" in kinds

    def test_gitlab_bundle_entry(self):
        catalog = build_bundle_catalog(bundle="gitlab")
        assert len(catalog["bundles"]) == 1
        bundle = catalog["bundles"][0]
        assert bundle["name"] == "gitlab"
        assert "gitlab_project_token" in bundle["generator_kinds"]
        assert "gitlab_group_variable" in bundle["target_kinds"]

    def test_filter_kind_generator(self):
        catalog = build_bundle_catalog(kind="gitlab_project_token", kind_type="generator")
        assert len(catalog["generators"]) == 1
        assert catalog["generators"][0]["kind"] == "gitlab_project_token"
        assert catalog["targets"] == []

    def test_find_catalog_entry(self):
        catalog = build_bundle_catalog()
        entry = find_catalog_entry(catalog, "gitlab_variable")
        assert entry is not None
        assert entry["type"] == "target"
        assert entry["bundle"] == "gitlab"
        assert "typical_generators" in entry

    def test_json_serializable(self):
        catalog = build_bundle_catalog()
        json.dumps(catalog)


class TestCatalogCLI:
    def test_catalog_command_json(self):
        from click.testing import CliRunner

        from secretzero.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["catalog", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "generator_kinds" in payload
        assert "gitlab_project_token" in payload["generator_kinds"]
