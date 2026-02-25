"""Tests for the discovery module and 'secretzero discover' CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from secretzero.cli import main
from secretzero.cli_config import CliConfig, DiscoveryConfig
from secretzero.discovery import DiscoveryAgent, DiscoveryResult, SecretCandidate

# ---------------------------------------------------------------------------
# SecretCandidate
# ---------------------------------------------------------------------------


class TestSecretCandidate:
    def test_to_secretfile_entry_basic(self) -> None:
        candidate = SecretCandidate(
            name="database_password",
            description="Database password",
            suggested_generator="random_password",
            suggested_target_kind="file",
        )
        entry = candidate.to_secretfile_entry()
        assert entry["name"] == "database_password"
        assert entry["kind"] == "random_password"
        assert len(entry["targets"]) == 1
        assert entry["targets"][0]["kind"] == "file"

    def test_to_secretfile_entry_with_tags(self) -> None:
        candidate = SecretCandidate(
            name="api_key",
            description="API key",
            suggested_generator="random_string",
            tags=["aws", "api-key"],
        )
        entry = candidate.to_secretfile_entry()
        assert "labels" in entry
        assert entry["labels"]["aws"] == "true"


# ---------------------------------------------------------------------------
# DiscoveryResult
# ---------------------------------------------------------------------------


class TestDiscoveryResult:
    def test_total_secrets(self) -> None:
        result = DiscoveryResult(
            candidates=[
                SecretCandidate(name="a", confidence=0.9),
                SecretCandidate(name="b", confidence=0.7),
            ]
        )
        assert result.total_secrets == 2

    def test_summary_dry_run(self) -> None:
        result = DiscoveryResult(
            candidates=[SecretCandidate(name="a", confidence=0.9)],
            files_scanned=5,
            output_path=Path("Secretfile.detect.yml"),
            dry_run=True,
        )
        summary = result.summary()
        assert "5" in summary
        assert "dry-run" in summary

    def test_summary_written(self) -> None:
        result = DiscoveryResult(
            candidates=[],
            files_scanned=3,
            output_path=Path("Secretfile.detect.yml"),
            dry_run=False,
        )
        summary = result.summary()
        assert "written" in summary


# ---------------------------------------------------------------------------
# DiscoveryAgent – file collection
# ---------------------------------------------------------------------------


class TestDiscoveryAgentFileCollection:
    @pytest.fixture
    def agent(self) -> DiscoveryAgent:
        cfg = CliConfig()
        return DiscoveryAgent(config=cfg)

    def test_collects_env_files(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        (tmp_path / ".env").write_text("SECRET=abc")
        (tmp_path / ".env.local").write_text("OTHER=xyz")
        files = agent._collect_files(tmp_path)
        names = [f.name for f in files]
        assert ".env" in names
        assert ".env.local" in names

    def test_excludes_node_modules(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / ".env").write_text("SECRET=abc")
        files = agent._collect_files(tmp_path)
        for f in files:
            assert "node_modules" not in str(f)

    def test_excludes_git_directory(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        git = tmp_path / ".git"
        git.mkdir()
        (git / "config").write_text("url = ...")
        files = agent._collect_files(tmp_path)
        for f in files:
            assert ".git" not in str(f)

    def test_respects_max_files(self, tmp_path: Path) -> None:
        for i in range(20):
            (tmp_path / f"config{i}.yml").write_text(f"key{i}: value{i}")

        cfg = CliConfig()
        cfg.discovery.max_files = 5
        agent = DiscoveryAgent(config=cfg)
        files = agent._collect_files(tmp_path)
        assert len(files) <= 5


# ---------------------------------------------------------------------------
# DiscoveryAgent – pattern scanning
# ---------------------------------------------------------------------------


class TestDiscoveryAgentPatternScan:
    @pytest.fixture
    def agent(self) -> DiscoveryAgent:
        cfg = CliConfig()
        return DiscoveryAgent(config=cfg)

    def test_detects_aws_access_key(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / ".env"
        env.write_text("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n")
        candidates = agent._scan_file(env, tmp_path)
        assert any("aws" in c.name.lower() or "aws" in c.tags for c in candidates)

    def test_detects_database_password(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / ".env"
        env.write_text("DATABASE_PASSWORD=supersecretpassword123\n")
        candidates = agent._scan_file(env, tmp_path)
        assert len(candidates) > 0

    def test_detects_generic_api_key(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / ".env"
        env.write_text("API_KEY=abcdefghijklmnopqrstuvwxyz123456\n")
        candidates = agent._scan_file(env, tmp_path)
        assert len(candidates) > 0

    def test_skips_placeholder_values(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / ".env"
        env.write_text("API_KEY=your_api_key_here\nPASSWORD=changeme_please\n")
        candidates = agent._scan_file(env, tmp_path)
        # Should not include obvious placeholders
        for c in candidates:
            assert c.confidence >= agent.config.discovery.confidence_threshold

    def test_github_token_detection(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / ".env"
        env.write_text("GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890\n")
        candidates = agent._scan_file(env, tmp_path)
        assert any("github" in c.tags for c in candidates)

    def test_detects_jwt_secret(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / ".env"
        env.write_text("JWT_SECRET=my_very_long_jwt_secret_value_here_abc123\n")
        candidates = agent._scan_file(env, tmp_path)
        assert len(candidates) > 0

    def test_detects_database_url(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / ".env"
        env.write_text("DATABASE_URL=postgres://user:pass@localhost/mydb\n")
        candidates = agent._scan_file(env, tmp_path)
        assert len(candidates) > 0

    def test_unreadable_file_returns_empty(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        fake = tmp_path / ".env"
        # Don't write anything – simulate by patching read_text
        fake.write_text("")
        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            candidates = agent._scan_file(fake, tmp_path)
        assert candidates == []

    def test_records_source_file(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / "config" / ".env"
        env.parent.mkdir()
        env.write_text("API_KEY=realvaluenotplaceholder1234567890\n")
        candidates = agent._scan_file(env, tmp_path)
        if candidates:
            assert "config" in candidates[0].source_file or ".env" in candidates[0].source_file

    def test_does_not_store_raw_value(self, tmp_path: Path, agent: DiscoveryAgent) -> None:
        env = tmp_path / ".env"
        real_secret = "supersecret_realpassword12345"
        env.write_text(f"DATABASE_PASSWORD={real_secret}\n")
        candidates = agent._scan_file(env, tmp_path)
        for c in candidates:
            assert real_secret not in c.raw_value


# ---------------------------------------------------------------------------
# DiscoveryAgent – is_placeholder
# ---------------------------------------------------------------------------


class TestIsPlaceholder:
    @pytest.fixture
    def agent(self) -> DiscoveryAgent:
        return DiscoveryAgent(config=CliConfig())

    def test_your_prefix(self, agent: DiscoveryAgent) -> None:
        assert agent._is_placeholder("your_api_key_here") is True

    def test_change_prefix(self, agent: DiscoveryAgent) -> None:
        assert agent._is_placeholder("changeme") is True

    def test_env_var_reference(self, agent: DiscoveryAgent) -> None:
        assert agent._is_placeholder("${SOME_VAR}") is True

    def test_angle_brackets(self, agent: DiscoveryAgent) -> None:
        assert agent._is_placeholder("<your-secret>") is True

    def test_real_value_not_placeholder(self, agent: DiscoveryAgent) -> None:
        assert agent._is_placeholder("sk_live_abcdef123456") is False


# ---------------------------------------------------------------------------
# DiscoveryAgent – deduplication and merging
# ---------------------------------------------------------------------------


class TestDeduplication:
    @pytest.fixture
    def agent(self) -> DiscoveryAgent:
        return DiscoveryAgent(config=CliConfig())

    def test_deduplicates_by_name(self, agent: DiscoveryAgent) -> None:
        candidates = [
            SecretCandidate(name="api_key", confidence=0.7),
            SecretCandidate(name="api_key", confidence=0.9),
            SecretCandidate(name="db_pass", confidence=0.8),
        ]
        result = agent._deduplicate(candidates)
        names = [c.name for c in result]
        assert names.count("api_key") == 1
        assert len(result) == 2

    def test_keeps_highest_confidence(self, agent: DiscoveryAgent) -> None:
        candidates = [
            SecretCandidate(name="api_key", confidence=0.7),
            SecretCandidate(name="api_key", confidence=0.9),
        ]
        result = agent._deduplicate(candidates)
        assert result[0].confidence == 0.9

    def test_sorted_by_descending_confidence(self, agent: DiscoveryAgent) -> None:
        candidates = [
            SecretCandidate(name="low", confidence=0.5),
            SecretCandidate(name="high", confidence=0.95),
            SecretCandidate(name="mid", confidence=0.75),
        ]
        result = agent._deduplicate(candidates)
        assert result[0].confidence >= result[1].confidence >= result[2].confidence


class TestMergeCandidates:
    @pytest.fixture
    def agent(self) -> DiscoveryAgent:
        return DiscoveryAgent(config=CliConfig())

    def test_adds_new_llm_candidates(self, agent: DiscoveryAgent) -> None:
        pattern = [SecretCandidate(name="db_pass", confidence=0.8)]
        llm = [SecretCandidate(name="stripe_key", confidence=0.9)]
        merged = agent._merge_candidates(pattern, llm)
        names = [c.name for c in merged]
        assert "db_pass" in names
        assert "stripe_key" in names

    def test_boosts_confidence_on_agreement(self, agent: DiscoveryAgent) -> None:
        pattern = [SecretCandidate(name="api_key", confidence=0.7)]
        llm = [SecretCandidate(name="api_key", confidence=0.8)]
        merged = agent._merge_candidates(pattern, llm)
        api = next(c for c in merged if c.name == "api_key")
        # Confidence should be boosted above the highest individual score
        assert api.confidence > 0.8


# ---------------------------------------------------------------------------
# DiscoveryAgent – full discover pipeline
# ---------------------------------------------------------------------------


class TestDiscoveryAgentFullPipeline:
    def test_discover_dry_run(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("DATABASE_PASSWORD=supersecretpassword123\nAPI_KEY=realkey123456789\n")

        cfg = CliConfig()
        agent = DiscoveryAgent(config=cfg)
        result = agent.discover(
            project_root=tmp_path,
            output_path=tmp_path / "Secretfile.detect.yml",
            dry_run=True,
            use_llm=False,
        )

        assert result.dry_run is True
        assert result.files_scanned >= 1
        assert not (tmp_path / "Secretfile.detect.yml").exists()

    def test_discover_writes_output(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("DATABASE_PASSWORD=supersecretpassword123\n")

        cfg = CliConfig()
        cfg.discovery.confidence_threshold = 0.5
        agent = DiscoveryAgent(config=cfg)
        result = agent.discover(
            project_root=tmp_path,
            output_path=tmp_path / "Secretfile.detect.yml",
            dry_run=False,
            use_llm=False,
        )

        if result.total_secrets > 0:
            assert (tmp_path / "Secretfile.detect.yml").exists()
            # Validate YAML
            content = yaml.safe_load((tmp_path / "Secretfile.detect.yml").read_text())
            assert "secrets" in content
            assert isinstance(content["secrets"], list)

    def test_discover_filters_by_threshold(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("DATABASE_PASSWORD=supersecretpass123\n")

        cfg = CliConfig()
        cfg.discovery.confidence_threshold = 1.0  # Impossible threshold
        agent = DiscoveryAgent(config=cfg)
        result = agent.discover(
            project_root=tmp_path,
            dry_run=True,
            use_llm=False,
        )
        # Nothing should meet 100% confidence
        assert result.total_secrets == 0

    def test_discover_empty_project(self, tmp_path: Path) -> None:
        cfg = CliConfig()
        agent = DiscoveryAgent(config=cfg)
        result = agent.discover(project_root=tmp_path, dry_run=True, use_llm=False)
        assert result.files_scanned == 0
        assert result.total_secrets == 0

    def test_discover_default_output_path(self, tmp_path: Path) -> None:
        cfg = CliConfig()
        agent = DiscoveryAgent(config=cfg)
        result = agent.discover(
            project_root=tmp_path,
            output_path=None,
            dry_run=True,
            use_llm=False,
        )
        assert result.output_path == tmp_path / "Secretfile.detect.yml"

    def test_discover_skips_llm_when_library_missing(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("API_KEY=real_api_key_12345678901234\n")

        cfg = CliConfig()
        cfg.llm.default_provider = "ollama"
        agent = DiscoveryAgent(config=cfg)

        # Patch _get_llm to return None (simulates missing library)
        with patch.object(agent, "_get_llm", return_value=None):
            result = agent.discover(
                project_root=tmp_path,
                dry_run=True,
                use_llm=True,
            )
        # Should still work with pattern-based detection
        assert result.files_scanned >= 1


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestDiscoverCLICommand:
    def test_discover_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["discover", "--help"])
        assert result.exit_code == 0
        assert "secret" in result.output.lower() or "discover" in result.output.lower()

    def test_discover_dry_run_empty_project(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["discover", "--path", str(tmp_path), "--dry-run", "--no-llm"])
        assert result.exit_code == 0
        assert "Scanned" in result.output

    def test_discover_with_env_file(self, runner: CliRunner, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("DATABASE_PASSWORD=supersecretpassword123\n")

        result = runner.invoke(
            main,
            [
                "discover",
                "--path",
                str(tmp_path),
                "--dry-run",
                "--no-llm",
            ],
        )
        assert result.exit_code == 0
        assert "Scanned" in result.output

    def test_discover_json_output(self, runner: CliRunner, tmp_path: Path) -> None:
        import json

        env = tmp_path / ".env"
        env.write_text("API_KEY=realkey123456789abcdef\n")

        result = runner.invoke(
            main,
            [
                "discover",
                "--path",
                str(tmp_path),
                "--dry-run",
                "--no-llm",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "files_scanned" in data
        assert "total_secrets" in data
        assert "secrets" in data
        assert isinstance(data["secrets"], list)

    def test_discover_yaml_output(self, runner: CliRunner, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("API_KEY=realkey123456789abcdef\n")

        result = runner.invoke(
            main,
            [
                "discover",
                "--path",
                str(tmp_path),
                "--dry-run",
                "--no-llm",
                "--format",
                "yaml",
            ],
        )
        assert result.exit_code == 0
        data = yaml.safe_load(result.output)
        assert "files_scanned" in data
        assert "secrets" in data

    def test_discover_writes_output_file(self, runner: CliRunner, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("DATABASE_PASSWORD=supersecretpassword123\n")
        out = tmp_path / "Secretfile.detect.yml"

        result = runner.invoke(
            main,
            [
                "discover",
                "--path",
                str(tmp_path),
                "--output",
                str(out),
                "--no-llm",
            ],
        )
        assert result.exit_code == 0

    def test_discover_with_custom_config(self, runner: CliRunner, tmp_path: Path) -> None:
        config_file = tmp_path / "secretzero.yml"
        config_file.write_text(
            yaml.dump(
                {
                    "version": "1.0",
                    "llm": {"default_provider": "ollama"},
                    "discovery": {"confidence_threshold": 0.5},
                }
            )
        )
        env = tmp_path / ".env"
        env.write_text("API_KEY=realvalue123456789abcdef\n")

        result = runner.invoke(
            main,
            [
                "discover",
                "--path",
                str(tmp_path),
                "--config",
                str(config_file),
                "--dry-run",
                "--no-llm",
            ],
        )
        assert result.exit_code == 0

    def test_discover_threshold_override(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            main,
            [
                "discover",
                "--path",
                str(tmp_path),
                "--dry-run",
                "--no-llm",
                "--threshold",
                "0.99",
            ],
        )
        assert result.exit_code == 0
        assert "0" in result.output  # 0 secrets at impossible threshold

    def test_discover_in_help_text(self, runner: CliRunner) -> None:
        """discover command should appear in main help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "discover" in result.output
