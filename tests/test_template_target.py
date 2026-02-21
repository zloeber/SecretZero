"""Tests for Jinja2 template target."""

import tempfile
from pathlib import Path

import pytest

from secretzero.targets.template import TemplateTarget


class TestTemplateTarget:
    """Test Jinja2 template target."""

    def test_template_target_initialization(self):
        """Test template target initialization."""
        config = {
            "template_path": "/path/to/template.j2",
            "output_path": "/path/to/output.txt",
        }
        target = TemplateTarget(config)

        assert target.template_path == Path("/path/to/template.j2")
        assert target.output_path == Path("/path/to/output.txt")
        assert target.overwrite is True

    def test_template_target_missing_template_path(self):
        """Test that error is raised when template_path is missing."""
        config = {"output_path": "/path/to/output.txt"}

        with pytest.raises(ValueError, match="template_path"):
            TemplateTarget(config)

    def test_template_target_missing_output_path(self):
        """Test that error is raised when output_path is missing."""
        config = {"template_path": "/path/to/template.j2"}

        with pytest.raises(ValueError, match="output_path"):
            TemplateTarget(config)

    def test_store_method(self):
        """Test that store method returns True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "template_path": str(Path(tmpdir) / "template.j2"),
                "output_path": str(Path(tmpdir) / "output.txt"),
            }
            target = TemplateTarget(config)

            # Store should return True (accepting the secret for later rendering)
            success = target.store("DB_PASSWORD", "secret123")
            assert success is True

    def test_retrieve_method(self):
        """Test that retrieve method returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "template_path": str(Path(tmpdir) / "template.j2"),
                "output_path": str(Path(tmpdir) / "output.txt"),
            }
            target = TemplateTarget(config)

            # Retrieve should return None (templates don't store individual secrets)
            result = target.retrieve("DB_PASSWORD")
            assert result is None

    def test_render_basic_template(self):
        """Test rendering a basic template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a template file
            template_path = Path(tmpdir) / "template.j2"
            template_content = "Database URL: {{ secrets.DB_HOST }}:{{ secrets.DB_PORT }}\n"
            template_path.write_text(template_content)

            output_path = Path(tmpdir) / "output.txt"

            config = {
                "template_path": str(template_path),
                "output_path": str(output_path),
            }
            target = TemplateTarget(config)

            # Render with secrets
            secrets = {"DB_HOST": "localhost", "DB_PORT": "5432"}
            success = target.render(secrets)

            assert success is True
            assert output_path.exists()

            output_content = output_path.read_text()
            assert "Database URL: localhost:5432" in output_content

    def test_render_with_dict_access(self):
        """Test rendering template with dict-style access."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a template with dict access
            template_path = Path(tmpdir) / "config.j2"
            template_content = (
                "export DB_HOST={{ DB_HOST }}\n"
                "export DB_USER={{ DB_USER }}\n"
                "export DB_PASS={{ DB_PASS }}\n"
            )
            template_path.write_text(template_content)

            output_path = Path(tmpdir) / ".env"

            config = {
                "template_path": str(template_path),
                "output_path": str(output_path),
            }
            target = TemplateTarget(config)

            secrets = {
                "DB_HOST": "db.example.com",
                "DB_USER": "admin",
                "DB_PASS": "supersecret",
            }
            success = target.render(secrets)

            assert success is True
            output_content = output_path.read_text()
            assert "export DB_HOST=db.example.com" in output_content
            assert "export DB_USER=admin" in output_content
            assert "export DB_PASS=supersecret" in output_content

    def test_render_with_jinja_filters(self):
        """Test rendering template with Jinja2 filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a template with filters
            template_path = Path(tmpdir) / "readme.j2"
            template_content = (
                "# Configuration\n\n"
                "API Key: {{ API_KEY | upper }}\n"
                "Token: {{ TOKEN | length }} chars\n"
            )
            template_path.write_text(template_content)

            output_path = Path(tmpdir) / "README.md"

            config = {
                "template_path": str(template_path),
                "output_path": str(output_path),
            }
            target = TemplateTarget(config)

            secrets = {"API_KEY": "myapikey123", "TOKEN": "token"}
            success = target.render(secrets)

            assert success is True
            output_content = output_path.read_text()
            assert "API Key: MYAPIKEY123" in output_content
            assert "Token: 5 chars" in output_content

    def test_render_template_not_found(self):
        """Test error when template file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "template_path": str(Path(tmpdir) / "nonexistent.j2"),
                "output_path": str(Path(tmpdir) / "output.txt"),
            }
            target = TemplateTarget(config)

            with pytest.raises(ValueError, match="Template file not found"):
                target.render({"SECRET": "value"})

    def test_render_invalid_jinja_syntax(self):
        """Test error when template has invalid Jinja syntax."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a template with invalid Jinja syntax
            template_path = Path(tmpdir) / "bad.j2"
            template_content = "Config: {{ secrets.VALUE | nonexistent_filter }}\n"
            template_path.write_text(template_content)

            output_path = Path(tmpdir) / "output.txt"

            config = {
                "template_path": str(template_path),
                "output_path": str(output_path),
            }
            target = TemplateTarget(config)

            with pytest.raises(RuntimeError, match="Template rendering failed"):
                target.render({"VALUE": "test"})

    def test_render_creates_parent_directories(self):
        """Test that parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a template file
            template_path = Path(tmpdir) / "template.j2"
            template_content = "Value: {{ VALUE }}\n"
            template_path.write_text(template_content)

            # Output in nested non-existent directories
            output_path = Path(tmpdir) / "nested" / "deep" / "output.txt"

            config = {
                "template_path": str(template_path),
                "output_path": str(output_path),
            }
            target = TemplateTarget(config)

            success = target.render({"VALUE": "test"})

            assert success is True
            assert output_path.exists()
            assert output_path.read_text() == "Value: test\n"

    def test_render_with_conditional_logic(self):
        """Test rendering template with conditional logic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "config.j2"
            template_content = (
                "{% if ENV == 'production' %}\n"
                "DEBUG=False\n"
                "LOG_LEVEL=WARNING\n"
                "{% else %}\n"
                "DEBUG=True\n"
                "LOG_LEVEL=DEBUG\n"
                "{% endif %}\n"
                "DATABASE_URL={{ DB_URL }}\n"
            )
            template_path.write_text(template_content)

            output_path = Path(tmpdir) / ".env"

            config = {
                "template_path": str(template_path),
                "output_path": str(output_path),
            }
            target = TemplateTarget(config)

            # Test production config
            secrets = {"ENV": "production", "DB_URL": "prod-db.example.com"}
            target.render(secrets)

            output_content = output_path.read_text()
            assert "DEBUG=False" in output_content
            assert "LOG_LEVEL=WARNING" in output_content

            # Test development config
            secrets = {"ENV": "development", "DB_URL": "localhost"}
            target.render(secrets)

            output_content = output_path.read_text()
            assert "DEBUG=True" in output_content
            assert "LOG_LEVEL=DEBUG" in output_content

    def test_render_with_loops(self):
        """Test rendering template with loops."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "hosts.j2"
            template_content = (
                "servers:\n"
                "{% for host in HOSTS.split(',') %}\n"
                "  - {{ host }}\n"
                "{% endfor %}\n"
            )
            template_path.write_text(template_content)

            output_path = Path(tmpdir) / "servers.yml"

            config = {
                "template_path": str(template_path),
                "output_path": str(output_path),
            }
            target = TemplateTarget(config)

            secrets = {"HOSTS": "server1.example.com,server2.example.com,server3.example.com"}
            success = target.render(secrets)

            assert success is True
            output_content = output_path.read_text()
            assert "server1.example.com" in output_content
            assert "server2.example.com" in output_content
            assert "server3.example.com" in output_content

    def test_render_overwrites_existing_file(self):
        """Test that render overwrites existing output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "template.j2"
            template_path.write_text("Value: {{ VALUE }}\n")

            output_path = Path(tmpdir) / "output.txt"
            output_path.write_text("Old content\n")

            config = {
                "template_path": str(template_path),
                "output_path": str(output_path),
                "overwrite": True,
            }
            target = TemplateTarget(config)

            success = target.render({"VALUE": "new"})

            assert success is True
            assert output_path.read_text() == "Value: new\n"

    def test_missing_jinja2_library(self, monkeypatch):
        """Test error message when Jinja2 is not installed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "template.j2"
            template_path.write_text("test")

            config = {
                "template_path": str(template_path),
                "output_path": str(Path(tmpdir) / "output.txt"),
            }
            target = TemplateTarget(config)

            # Mock jinja2 import to raise ImportError
            import sys

            jinja2_backup = sys.modules.get("jinja2")

            def mock_import(name, *args, **kwargs):
                if "jinja2" in name:
                    raise ImportError("No module named 'jinja2'")
                return original_import(name, *args, **kwargs)

            original_import = __import__

            try:
                monkeypatch.setattr("builtins.__import__", mock_import)

                with pytest.raises(RuntimeError, match="Jinja2 is required"):
                    target.render({"VALUE": "test"})
            finally:
                # Restore jinja2 if it was available
                if jinja2_backup:
                    sys.modules["jinja2"] = jinja2_backup
