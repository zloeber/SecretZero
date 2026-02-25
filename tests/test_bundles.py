"""Tests for the SecretZero provider bundle framework.

Covers:
- BundleManifest model creation and validation
- load_class() / load_class_safe() utilities
- BundleRegistry registration, lookup, and entry-point discovery
- Open-enum behaviour of GeneratorKind and TargetKind
- SyncEngine integration with the bundle registry
- validate-bundle CLI command
"""

from __future__ import annotations

import importlib.metadata
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from secretzero.bundles import (
    BundleManifest,
    BundleRegistry,
    discover_bundles,
    get_bundle_registry,
    load_class,
    load_class_safe,
    reset_bundle_registry,
)
from secretzero.bundles.registry import _register_builtin_generators, _register_builtin_targets
from secretzero.generators.base import BaseGenerator
from secretzero.generators.github_pat import GitHubPATGenerator
from secretzero.generators.provider_backed import ProviderBackedGenerator
from secretzero.models import GeneratorKind, TargetKind
from secretzero.targets.base import BaseTarget


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_bundle_registry():
    """Ensure each test starts with a fresh bundle registry singleton."""
    reset_bundle_registry()
    yield
    reset_bundle_registry()


class _FakeGenerator(BaseGenerator):
    """Minimal generator for testing."""

    def generate(self) -> str:  # type: ignore[override]
        return "fake-value"


class _FakeTarget(BaseTarget):
    """Minimal target for testing."""

    def store(self, secret_name: str, secret_value: str) -> bool:
        return True

    def retrieve(self, secret_name: str) -> str | None:
        return "fake-value"


# ---------------------------------------------------------------------------
# load_class / load_class_safe
# ---------------------------------------------------------------------------


class TestLoadClass:
    def test_load_known_class(self) -> None:
        cls = load_class("secretzero.generators.static:StaticGenerator")
        from secretzero.generators.static import StaticGenerator

        assert cls is StaticGenerator

    def test_load_class_missing_colon_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="expected"):
            load_class("secretzero.generators.static.StaticGenerator")

    def test_load_class_missing_module_raises_import_error(self) -> None:
        with pytest.raises(ImportError):
            load_class("secretzero.does_not_exist:Nope")

    def test_load_class_missing_attribute_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            load_class("secretzero.generators.static:DoesNotExist")

    def test_load_class_safe_returns_class_on_success(self) -> None:
        cls = load_class_safe("secretzero.generators.static:StaticGenerator")
        assert cls is not None

    def test_load_class_safe_returns_none_on_bad_module(self) -> None:
        result = load_class_safe("no.such.module:Foo")
        assert result is None

    def test_load_class_safe_returns_none_on_bad_format(self) -> None:
        result = load_class_safe("no_colon_in_this_path")
        assert result is None


# ---------------------------------------------------------------------------
# BundleManifest model
# ---------------------------------------------------------------------------


class TestBundleManifest:
    def test_minimal_manifest(self) -> None:
        m = BundleManifest(name="test")
        assert m.name == "test"
        assert m.version == "1.0.0"
        assert m.generators == {}
        assert m.targets == {}
        assert m.provider_class is None

    def test_full_manifest(self) -> None:
        m = BundleManifest(
            name="github",
            version="2.0.0",
            provider_class="secretzero.providers.github:GitHubProvider",
            generators={"github_pat": "secretzero.generators.github_pat:GitHubPATGenerator"},
            targets={"github_secret": "secretzero.targets.github:GitHubSecretTarget"},
            generator_kinds=["github_pat"],
            target_kinds=["github_secret"],
        )
        assert m.name == "github"
        assert m.version == "2.0.0"
        assert "github_pat" in m.generators
        assert "github_secret" in m.targets

    def test_manifest_serialisation(self) -> None:
        m = BundleManifest(name="test", version="1.2.3")
        data = m.model_dump()
        assert data["name"] == "test"
        assert data["version"] == "1.2.3"


# ---------------------------------------------------------------------------
# BundleRegistry – direct registration
# ---------------------------------------------------------------------------


class TestBundleRegistryDirectRegistration:
    def test_register_generator(self) -> None:
        reg = BundleRegistry()
        reg.register_generator("fake_gen", _FakeGenerator)
        assert reg.get_generator_class("fake_gen") is _FakeGenerator

    def test_register_target(self) -> None:
        reg = BundleRegistry()
        reg.register_target("fake_target", _FakeTarget)
        assert reg.get_target_class("fake_target") is _FakeTarget

    def test_register_provider(self) -> None:
        from secretzero.providers.base import BaseProvider

        class _FakeProvider(BaseProvider):
            @property
            def provider_kind(self) -> str:
                return "fake"

            def test_connection(self) -> tuple[bool, str | None]:
                return True, None

            def get_supported_targets(self) -> list[str]:
                return []

        reg = BundleRegistry()
        reg.register_provider("fake", _FakeProvider)
        assert reg.get_provider_class("fake") is _FakeProvider

    def test_unknown_kind_returns_none(self) -> None:
        reg = BundleRegistry()
        assert reg.get_generator_class("nope") is None
        assert reg.get_target_class("nope") is None
        assert reg.get_provider_class("nope") is None

    def test_list_kinds_sorted(self) -> None:
        reg = BundleRegistry()
        reg.register_generator("z_gen", _FakeGenerator)
        reg.register_generator("a_gen", _FakeGenerator)
        kinds = reg.list_generator_kinds()
        assert kinds == sorted(kinds)

    def test_list_empty_registry(self) -> None:
        reg = BundleRegistry()
        assert reg.list_bundles() == []
        assert reg.list_generator_kinds() == []
        assert reg.list_target_kinds() == []
        assert reg.list_provider_kinds() == []


# ---------------------------------------------------------------------------
# BundleRegistry – manifest registration
# ---------------------------------------------------------------------------


class TestBundleRegistryManifest:
    def test_register_valid_bundle(self) -> None:
        reg = BundleRegistry()
        manifest = BundleManifest(
            name="builtin_test",
            generators={"static": "secretzero.generators.static:StaticGenerator"},
            targets={"file": "secretzero.targets.file:FileTarget"},
        )
        reg.register_bundle(manifest)
        assert reg.get_generator_class("static") is not None
        assert reg.get_target_class("file") is not None
        assert reg.get_bundle("builtin_test") is manifest

    def test_register_bundle_with_bad_path_skips_gracefully(self) -> None:
        reg = BundleRegistry()
        manifest = BundleManifest(
            name="broken",
            generators={"broken_gen": "no.such.module:FakeClass"},
        )
        # Should not raise; bad path is silently skipped
        reg.register_bundle(manifest)
        assert reg.get_generator_class("broken_gen") is None
        # Bundle itself is still registered (manifest metadata is valid)
        assert reg.get_bundle("broken") is manifest

    def test_register_bundle_provider_class(self) -> None:
        reg = BundleRegistry()
        manifest = BundleManifest(
            name="aws",
            provider_class="secretzero.providers.aws:AWSProvider",
        )
        reg.register_bundle(manifest)
        # AWSProvider is always importable (no optional dep at import time)
        cls = reg.get_provider_class("aws")
        assert cls is not None


# ---------------------------------------------------------------------------
# BundleRegistry – entry-point discovery
# ---------------------------------------------------------------------------


class TestBundleRegistryDiscovery:
    def test_discover_and_register_valid_bundle(self) -> None:
        """discover_and_register() ingests BundleManifest entry points."""
        manifest = BundleManifest(
            name="ep_test",
            generators={"static": "secretzero.generators.static:StaticGenerator"},
        )
        ep = MagicMock()
        ep.load.return_value = manifest

        reg = BundleRegistry()
        with patch("importlib.metadata.entry_points", return_value=[ep]):
            reg.discover_and_register()

        assert reg.get_generator_class("static") is not None

    def test_discover_and_register_ignores_non_manifest(self) -> None:
        """Non-BundleManifest entry-point values are silently ignored."""
        ep = MagicMock()
        ep.load.return_value = "not-a-manifest"

        reg = BundleRegistry()
        with patch("importlib.metadata.entry_points", return_value=[ep]):
            reg.discover_and_register()

        assert reg.list_bundles() == []

    def test_discover_and_register_ignores_failing_entry_point(self) -> None:
        """Entry points that raise on load are silently skipped."""
        ep = MagicMock()
        ep.load.side_effect = RuntimeError("oops")

        reg = BundleRegistry()
        with patch("importlib.metadata.entry_points", return_value=[ep]):
            reg.discover_and_register()  # must not raise

        assert reg.list_bundles() == []

    def test_discover_bundles_top_level(self) -> None:
        """discover_bundles() returns list of BundleManifest instances."""
        manifest = BundleManifest(name="disc_test")
        ep = MagicMock()
        ep.load.return_value = manifest

        with patch("importlib.metadata.entry_points", return_value=[ep]):
            found = discover_bundles()

        assert manifest in found


# ---------------------------------------------------------------------------
# get_bundle_registry singleton + built-ins
# ---------------------------------------------------------------------------


class TestGetBundleRegistry:
    def test_singleton_returns_same_instance(self) -> None:
        r1 = get_bundle_registry()
        r2 = get_bundle_registry()
        assert r1 is r2

    def test_builtin_generators_registered(self) -> None:
        reg = get_bundle_registry()
        for kind in ("random_password", "random_string", "static", "script"):
            assert reg.get_generator_class(kind) is not None, f"Missing generator: {kind}"

    def test_builtin_targets_registered(self) -> None:
        reg = get_bundle_registry()
        for kind in ("file", "template"):
            assert reg.get_target_class(kind) is not None, f"Missing target: {kind}"

    def test_builtin_providers_registered(self) -> None:
        reg = get_bundle_registry()
        # AWS provider is always importable
        assert reg.get_provider_class("aws") is not None

    def test_reset_clears_singleton(self) -> None:
        r1 = get_bundle_registry()
        reset_bundle_registry()
        r2 = get_bundle_registry()
        assert r1 is not r2


# ---------------------------------------------------------------------------
# BundleRegistry.validate_bundle_manifest
# ---------------------------------------------------------------------------


class TestValidateBundleManifest:
    def test_valid_manifest_returns_no_errors(self) -> None:
        reg = BundleRegistry()
        manifest = BundleManifest(
            name="valid",
            generators={"static": "secretzero.generators.static:StaticGenerator"},
            targets={"file": "secretzero.targets.file:FileTarget"},
        )
        errors = reg.validate_bundle_manifest(manifest)
        assert errors == []

    def test_bad_generator_path_returns_error(self) -> None:
        reg = BundleRegistry()
        manifest = BundleManifest(
            name="bad_gen",
            generators={"broken": "no.such.module:Cls"},
        )
        errors = reg.validate_bundle_manifest(manifest)
        assert any("broken" in e for e in errors)

    def test_wrong_base_class_returns_error(self) -> None:
        """A path pointing to a non-BaseGenerator class should fail."""
        reg = BundleRegistry()
        # Use a known non-generator class as a "generator"
        manifest = BundleManifest(
            name="wrong_base",
            generators={"file": "secretzero.targets.file:FileTarget"},
        )
        errors = reg.validate_bundle_manifest(manifest)
        assert any("BaseGenerator" in e for e in errors)

    def test_valid_provider_class_returns_no_errors(self) -> None:
        reg = BundleRegistry()
        manifest = BundleManifest(
            name="prov_test",
            provider_class="secretzero.providers.aws:AWSProvider",
        )
        errors = reg.validate_bundle_manifest(manifest)
        assert errors == []

    def test_invalid_provider_class_returns_error(self) -> None:
        reg = BundleRegistry()
        manifest = BundleManifest(
            name="bad_prov",
            provider_class="no.such.module:NoProv",
        )
        errors = reg.validate_bundle_manifest(manifest)
        assert len(errors) == 1
        assert "provider_class" in errors[0]


# ---------------------------------------------------------------------------
# Open enums: GeneratorKind and TargetKind
# ---------------------------------------------------------------------------


class TestOpenEnums:
    def test_generator_kind_known_value(self) -> None:
        kind = GeneratorKind("random_password")
        assert kind == GeneratorKind.RANDOM_PASSWORD

    def test_generator_kind_unknown_value_accepted(self) -> None:
        kind = GeneratorKind("custom_vendor_generator")
        assert kind == "custom_vendor_generator"
        # The value property holds the plain string
        assert kind.value == "custom_vendor_generator"

    def test_generator_kind_unknown_is_string_comparable(self) -> None:
        kind = GeneratorKind("my_kind")
        assert kind == "my_kind"
        # Can be used as dict key
        d = {kind: "value"}
        assert d["my_kind"] == "value"

    def test_generator_kind_missing_empty_string_returns_none(self) -> None:
        result = GeneratorKind._missing_("")
        assert result is None

    def test_generator_kind_missing_non_string_returns_none(self) -> None:
        result = GeneratorKind._missing_(42)
        assert result is None

    def test_target_kind_known_value(self) -> None:
        kind = TargetKind("file")
        assert kind == TargetKind.FILE

    def test_target_kind_unknown_value_accepted(self) -> None:
        kind = TargetKind("my_custom_vault")
        assert kind == "my_custom_vault"

    def test_target_kind_missing_empty_string_returns_none(self) -> None:
        result = TargetKind._missing_("")
        assert result is None

    def test_target_kind_missing_non_string_returns_none(self) -> None:
        result = TargetKind._missing_(None)
        assert result is None


# ---------------------------------------------------------------------------
# Generator provider-injection class attributes
# ---------------------------------------------------------------------------


class TestGeneratorProviderInjectionAttributes:
    def test_github_pat_has_injection_keys(self) -> None:
        assert hasattr(GitHubPATGenerator, "PROVIDER_CONFIG_KEY")
        assert hasattr(GitHubPATGenerator, "PROVIDER_INJECTION_KEY")
        assert GitHubPATGenerator.PROVIDER_CONFIG_KEY == "provider"
        assert GitHubPATGenerator.PROVIDER_INJECTION_KEY == "_provider_instance"

    def test_provider_backed_has_injection_keys(self) -> None:
        assert hasattr(ProviderBackedGenerator, "PROVIDER_CONFIG_KEY")
        assert hasattr(ProviderBackedGenerator, "PROVIDER_INJECTION_KEY")
        assert ProviderBackedGenerator.PROVIDER_CONFIG_KEY == "provider"
        assert ProviderBackedGenerator.PROVIDER_INJECTION_KEY == "provider"


# ---------------------------------------------------------------------------
# SyncEngine integration – _resolve_provider_in_config
# ---------------------------------------------------------------------------


class TestSyncEngineProviderInjection:
    def _make_engine(self) -> Any:
        from secretzero.lockfile import Lockfile
        from secretzero.models import Secretfile
        from secretzero.sync import SyncEngine

        sf = Secretfile(version="1.0", secrets=[])
        lf = Lockfile()
        return SyncEngine(sf, lf)

    def test_resolve_no_injection_needed(self) -> None:
        engine = self._make_engine()

        class _Plain(BaseGenerator):
            def generate(self) -> str:
                return "x"

        config = {"foo": "bar"}
        result = engine._resolve_provider_in_config(_Plain, config)
        assert result is config  # unchanged

    def test_resolve_injects_provider_instance(self) -> None:
        engine = self._make_engine()
        fake_provider = MagicMock()
        engine._providers["myprov"] = fake_provider

        class _NeedsProvider(BaseGenerator):
            PROVIDER_CONFIG_KEY = "provider"
            PROVIDER_INJECTION_KEY = "_provider_instance"

            def generate(self) -> str:
                return "x"

        config = {"provider": "myprov"}
        result = engine._resolve_provider_in_config(_NeedsProvider, config)
        assert result["_provider_instance"] is fake_provider
        assert result["provider"] == "myprov"

    def test_resolve_missing_provider_returns_unchanged(self) -> None:
        engine = self._make_engine()

        class _NeedsProvider(BaseGenerator):
            PROVIDER_CONFIG_KEY = "provider"
            PROVIDER_INJECTION_KEY = "_provider_instance"

            def generate(self) -> str:
                return "x"

        config = {"provider": "missing_provider"}
        result = engine._resolve_provider_in_config(_NeedsProvider, config)
        # Provider not found → config returned unchanged
        assert "_provider_instance" not in result


# ---------------------------------------------------------------------------
# SyncEngine integration – _generate_secret_value via bundle registry
# ---------------------------------------------------------------------------


class TestSyncEngineGenerateViaRegistry:
    def _make_engine(self) -> Any:
        from secretzero.lockfile import Lockfile
        from secretzero.models import Secretfile
        from secretzero.sync import SyncEngine

        sf = Secretfile(version="1.0", secrets=[])
        lf = Lockfile()
        return SyncEngine(sf, lf)

    def test_generate_random_password(self) -> None:
        engine = self._make_engine()
        value = engine._generate_secret_value("random_password", {}, "TEST_VAR")
        assert isinstance(value, str)
        assert len(value) > 0

    def test_generate_static(self) -> None:
        engine = self._make_engine()
        value = engine._generate_secret_value(
            "static", {"default": "hello"}, "TEST_VAR"
        )
        assert value == "hello"

    def test_generate_unknown_kind_raises(self) -> None:
        engine = self._make_engine()
        with pytest.raises(ValueError, match="Unknown generator kind"):
            engine._generate_secret_value("no_such_kind", {}, "TEST_VAR")

    def test_generate_from_bundle_registered_kind(self) -> None:
        """A generator registered via bundle registry is callable from sync engine."""
        from secretzero.bundles import get_bundle_registry

        reg = get_bundle_registry()
        reg.register_generator("test_fake", _FakeGenerator)

        engine = self._make_engine()
        # Force engine to use the freshly updated registry
        engine._bundle_registry = reg

        value = engine._generate_secret_value("test_fake", {}, "TEST_VAR")
        assert value == "fake-value"


# ---------------------------------------------------------------------------
# SyncEngine integration – _store_in_target via bundle registry
# ---------------------------------------------------------------------------


class TestSyncEngineStoreViaRegistry:
    def _make_engine(self) -> Any:
        from secretzero.lockfile import Lockfile
        from secretzero.models import Secretfile
        from secretzero.sync import SyncEngine

        sf = Secretfile(version="1.0", secrets=[])
        lf = Lockfile()
        return SyncEngine(sf, lf)

    def test_store_file_target(self, tmp_path: Any) -> None:
        engine = self._make_engine()

        tc = MagicMock()
        tc.provider = "local"
        tc.kind = "file"
        tc.config = {"path": str(tmp_path / ".env"), "format": "dotenv"}

        result = engine._store_in_target("MY_SECRET", "value123", tc)
        assert result["status"] == "stored"

    def test_store_unknown_kind_returns_unsupported(self) -> None:
        engine = self._make_engine()

        tc = MagicMock()
        tc.provider = "local"
        tc.kind = "no_such_target_kind"
        tc.config = {}

        result = engine._store_in_target("SECRET", "val", tc)
        assert result["status"] == "unsupported"
        assert "no_such_target_kind" in result["message"]

    def test_store_unknown_provider_not_initialized(self) -> None:
        engine = self._make_engine()

        # Use a known target kind but a provider that isn't configured
        reg = get_bundle_registry()
        reg.register_target("needs_provider_target", _FakeTarget)
        engine._bundle_registry = reg

        tc = MagicMock()
        tc.provider = "not_configured_provider"
        tc.kind = "needs_provider_target"
        tc.config = {}

        result = engine._store_in_target("SECRET", "val", tc)
        assert result["status"] == "error"
        assert "not initialized" in result["message"]

    def test_store_bundle_registered_target(self) -> None:
        """A target registered via bundle registry is callable from sync engine."""
        reg = get_bundle_registry()
        reg.register_target("bundle_fake_target", _FakeTarget)

        engine = self._make_engine()
        engine._bundle_registry = reg

        tc = MagicMock()
        tc.provider = "local"
        tc.kind = "bundle_fake_target"
        tc.config = {}

        result = engine._store_in_target("SECRET", "val", tc)
        assert result["status"] == "stored"


# ---------------------------------------------------------------------------
# SyncEngine integration – _create_provider via bundle registry
# ---------------------------------------------------------------------------


class TestSyncEngineCreateProviderViaRegistry:
    def _make_engine(self) -> Any:
        from secretzero.lockfile import Lockfile
        from secretzero.models import Secretfile
        from secretzero.sync import SyncEngine

        sf = Secretfile(version="1.0", secrets=[])
        lf = Lockfile()
        return SyncEngine(sf, lf)

    def test_create_known_provider(self) -> None:
        engine = self._make_engine()
        provider = engine._create_provider("aws", {"kind": "aws"})
        # AWS provider is always importable
        assert provider is not None

    def test_create_unknown_provider_returns_none(self) -> None:
        engine = self._make_engine()
        provider = engine._create_provider("no_such_kind", {"kind": "no_such_kind"})
        assert provider is None


# ---------------------------------------------------------------------------
# CLI validate-bundle command
# ---------------------------------------------------------------------------


class TestValidateBundleCommand:
    def test_valid_bundle_file(self, tmp_path: Any) -> None:
        from click.testing import CliRunner

        from secretzero.cli import main

        # Write a minimal bundle file
        bundle_file = tmp_path / "mybundle.py"
        bundle_file.write_text(
            "from secretzero.bundles import BundleManifest\n"
            "BUNDLE_MANIFEST = BundleManifest(\n"
            "    name='test_bundle',\n"
            "    generators={'static': 'secretzero.generators.static:StaticGenerator'},\n"
            "    targets={'file': 'secretzero.targets.file:FileTarget'},\n"
            ")\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["validate-bundle", str(bundle_file)])
        assert result.exit_code == 0
        assert "test_bundle" in result.output
        assert "valid" in result.output.lower()

    def test_invalid_bundle_file_missing_manifest(self, tmp_path: Any) -> None:
        from click.testing import CliRunner

        from secretzero.cli import main

        bundle_file = tmp_path / "empty.py"
        bundle_file.write_text("x = 1\n")

        runner = CliRunner()
        result = runner.invoke(main, ["validate-bundle", str(bundle_file)])
        assert result.exit_code != 0

    def test_bundle_with_bad_path_shows_errors(self, tmp_path: Any) -> None:
        from click.testing import CliRunner

        from secretzero.cli import main

        bundle_file = tmp_path / "bad_paths.py"
        bundle_file.write_text(
            "from secretzero.bundles import BundleManifest\n"
            "BUNDLE_MANIFEST = BundleManifest(\n"
            "    name='bad_bundle',\n"
            "    generators={'broken': 'no.module:NoClass'},\n"
            ")\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["validate-bundle", str(bundle_file)])
        assert result.exit_code != 0
        assert "broken" in result.output

    def test_valid_bundle_json_output(self, tmp_path: Any) -> None:
        import json

        from click.testing import CliRunner

        from secretzero.cli import main

        bundle_file = tmp_path / "json_bundle.py"
        bundle_file.write_text(
            "from secretzero.bundles import BundleManifest\n"
            "BUNDLE_MANIFEST = BundleManifest(name='json_test')\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            main, ["validate-bundle", "--output-format", "json", str(bundle_file)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is True
        assert data["manifest"]["name"] == "json_test"
