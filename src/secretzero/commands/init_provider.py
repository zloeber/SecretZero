"""Scaffold external SecretZero provider plugin packages."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console


def scaffold_provider_bundle(
    name: str,
    output_dir: str,
    target_kinds: tuple[str, ...],
    generator_kinds: tuple[str, ...],
    provider_description: str | None,
    *,
    console: Console,
) -> None:
    """Generate a pip-installable provider bundle with entry-point registration."""
    import re
    import textwrap

    # Validate name
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        console.print(
            f"[red]Error:[/red] Bundle name must be lowercase alphanumeric with "
            f"underscores (got '{name}')"
        )
        raise SystemExit(1)

    pkg_name = f"secretzero_{name}"
    class_prefix = name.replace("_", " ").title().replace(" ", "")
    provider_class_name = f"{class_prefix}Provider"
    auth_class_name = f"{class_prefix}Auth"
    desc = provider_description or f"{class_prefix} provider for SecretZero"

    base_dir = Path(output_dir) / pkg_name
    src_dir = base_dir / "src" / pkg_name
    tests_dir = base_dir / "tests"

    if base_dir.exists():
        console.print(f"[red]Error:[/red] Directory already exists: {base_dir}")
        raise SystemExit(1)

    # Collect file definitions
    files: dict[str, str] = {}

    # ---- pyproject.toml ----
    entry_generators = ""
    entry_targets = ""
    for gk in generator_kinds:
        entry_generators += f'  # "{gk}" generator available via bundle manifest\n'
    for tk in target_kinds:
        entry_targets += f'  # "{tk}" target available via bundle manifest\n'

    files[str(base_dir / "pyproject.toml")] = textwrap.dedent(f"""\
        [build-system]
        requires = ["setuptools>=68.0", "setuptools-scm>=8.0"]
        build-backend = "setuptools.backends._legacy:_Backend"

        [project]
        name = "{pkg_name}"
        version = "0.1.0"
        description = "{desc}"
        requires-python = ">=3.12"
        dependencies = [
            "secretzero>=0.2",
        ]

        [project.entry-points."secretzero.providers"]
        {name} = "{pkg_name}:BUNDLE_MANIFEST"
    """)

    # ---- src/<pkg>/__init__.py (bundle manifest) ----
    def _fmt_dict(items: dict[str, str], indent: int = 8) -> str:
        """Format a dict literal with one entry per line."""
        if not items:
            return "{}"
        pad = " " * indent
        lines = ["{"]
        for k, v in items.items():
            lines.append(f'{pad}"{k}": "{v}",')
        lines.append(" " * (indent - 4) + "}")
        return "\n".join(lines)

    def _fmt_list(items: tuple[str, ...], indent: int = 8) -> str:
        """Format a list literal."""
        if not items:
            return "[]"
        pad = " " * indent
        lines = ["["]
        for item in items:
            lines.append(f'{pad}"{item}",')
        lines.append(" " * (indent - 4) + "]")
        return "\n".join(lines)

    gen_map: dict[str, str] = {}
    for gk in generator_kinds:
        gc_name = gk.replace("_", " ").title().replace(" ", "") + "Generator"
        gen_map[gk] = f"{pkg_name}.generators:{gc_name}"
    target_map: dict[str, str] = {}
    for tk in target_kinds:
        tc_name = tk.replace("_", " ").title().replace(" ", "") + "Target"
        target_map[tk] = f"{pkg_name}.targets:{tc_name}"

    init_lines = [
        f'"""{desc}."""',
        "",
        "from secretzero.bundles.registry import BundleManifest",
        "",
        "BUNDLE_MANIFEST = BundleManifest(",
        f'    name="{name}",',
        '    version="0.1.0",',
        f'    provider_class="{pkg_name}.provider:{provider_class_name}",',
        f"    generators={_fmt_dict(gen_map)},",
        f"    targets={_fmt_dict(target_map)},",
        f"    generator_kinds={_fmt_list(generator_kinds)},",
        f"    target_kinds={_fmt_list(target_kinds)},",
        ")",
        "",
    ]
    files[str(src_dir / "__init__.py")] = "\n".join(init_lines)

    # ---- src/<pkg>/provider.py ----
    files[str(src_dir / "provider.py")] = textwrap.dedent(f'''\
        """{class_prefix} provider implementation."""

        from typing import Any

        from secretzero.providers.base import BaseProvider, ProviderAuth


        class {auth_class_name}(ProviderAuth):
            """Authentication handler for {class_prefix}."""

            ENV_TOKEN: str = "{name.upper()}_TOKEN"

            def authenticate(self) -> bool:
                """Authenticate with {class_prefix}."""
                token = self.config.get("token") or __import__("os").environ.get(self.ENV_TOKEN)
                if not token:
                    return False
                self._token = token
                return True

            def is_authenticated(self) -> bool:
                """Check if authenticated."""
                return hasattr(self, "_token") and self._token is not None

            def get_client(self) -> Any:
                """Return an authenticated API client."""
                if not self.is_authenticated():
                    self.authenticate()
                # TODO: return your SDK client here
                return None


        class {provider_class_name}(BaseProvider):
            """{class_prefix} provider for SecretZero."""

            display_name = "{desc}"
            description = "{desc}"
            required_package: tuple[str, str] | None = None  # e.g. ("my_sdk", "{pkg_name}")
            auth_class = {auth_class_name}

            auth_methods: dict[str, str] = {{
                "token": "Use a {class_prefix} API token",
            }}
            config_options: dict[str, str] = {{
                "url": "{class_prefix} API URL (optional)",
            }}
            config_example: str = (
                "providers:\\n"
                "  {name}:\\n"
                "    kind: {name}\\n"
                "    auth:\\n"
                "      kind: token\\n"
                "      config:\\n"
                "        token: ${{{name.upper()}_TOKEN}}"
            )
            target_details: dict[str, dict[str, Any]] = {{}}

            def __init__(
                self,
                name: str = "{name}",
                config: dict[str, Any] | None = None,
                auth: ProviderAuth | None = None,
            ) -> None:
                super().__init__(name=name, config=config or {{}}, auth=auth)

            @property
            def provider_kind(self) -> str:
                return "{name}"

            def test_connection(self) -> tuple[bool, str | None]:
                """Test connectivity to {class_prefix}."""
                # TODO: implement real connectivity test
                if self.auth and self.auth.is_authenticated():
                    return True, None
                return False, "Not authenticated"

            def get_supported_targets(self) -> list[str]:
                return {[*target_kinds] if target_kinds else []}
    ''')

    # ---- src/<pkg>/targets.py (if targets requested) ----
    if target_kinds:
        target_classes = ""
        for tk in target_kinds:
            tc_name = tk.replace("_", " ").title().replace(" ", "") + "Target"
            target_classes += textwrap.dedent(f'''\

                class {tc_name}(BaseTarget):
                    """{class_prefix} target: {tk}."""

                    def store(self, secret_name: str, secret_value: str) -> bool:
                        """Store a secret in {class_prefix}."""
                        # TODO: implement store
                        raise NotImplementedError

                    def retrieve(self, secret_name: str) -> str | None:
                        """Retrieve a secret from {class_prefix}."""
                        # TODO: implement retrieve
                        raise NotImplementedError

            ''')
        files[str(src_dir / "targets.py")] = textwrap.dedent(f'''\
            """{class_prefix} target implementations."""

            from secretzero.targets.base import BaseTarget
            {target_classes}
        ''')

    # ---- src/<pkg>/generators.py (if generators requested) ----
    if generator_kinds:
        gen_classes = ""
        for gk in generator_kinds:
            gc_name = gk.replace("_", " ").title().replace(" ", "") + "Generator"
            gen_classes += textwrap.dedent(f'''\

                class {gc_name}(BaseGenerator):
                    """{class_prefix} generator: {gk}."""

                    def generate(self) -> str:
                        """Generate a secret value."""
                        # TODO: implement generation logic
                        raise NotImplementedError

            ''')
        files[str(src_dir / "generators.py")] = textwrap.dedent(f'''\
            """{class_prefix} generator implementations."""

            from secretzero.generators.base import BaseGenerator
            {gen_classes}
        ''')

    # ---- tests/__init__.py ----
    files[str(tests_dir / "__init__.py")] = ""

    # ---- tests/test_provider.py ----
    files[str(tests_dir / "test_provider.py")] = textwrap.dedent(f'''\
        """Tests for {class_prefix} provider."""

        from {pkg_name}.provider import {auth_class_name}, {provider_class_name}


        def test_provider_kind():
            """Provider reports correct kind."""
            provider = {provider_class_name}()
            assert provider.provider_kind == "{name}"


        def test_auth_env_token():
            """{auth_class_name} declares expected ENV_TOKEN."""
            assert {auth_class_name}.ENV_TOKEN == "{name.upper()}_TOKEN"


        def test_provider_display_name():
            """Provider has a display_name set."""
            assert {provider_class_name}.display_name != ""
    ''')

    # ---- tests/test_bundle.py ----
    files[str(tests_dir / "test_bundle.py")] = textwrap.dedent(f'''\
        """Tests for {class_prefix} bundle manifest."""

        from secretzero.bundles.registry import BundleManifest

        from {pkg_name} import BUNDLE_MANIFEST


        def test_manifest_is_bundle_manifest():
            """BUNDLE_MANIFEST is a valid BundleManifest."""
            assert isinstance(BUNDLE_MANIFEST, BundleManifest)


        def test_manifest_name():
            """Bundle name matches provider name."""
            assert BUNDLE_MANIFEST.name == "{name}"


        def test_manifest_provider_class():
            """Provider class path is set."""
            assert BUNDLE_MANIFEST.provider_class is not None
    ''')

    # ---- README.md ----
    target_section = ""
    if target_kinds:
        kinds_list = ", ".join(f"`{tk}`" for tk in target_kinds)
        target_section = f"\n**Targets:** {kinds_list}\n"
    gen_section = ""
    if generator_kinds:
        kinds_list = ", ".join(f"`{gk}`" for gk in generator_kinds)
        gen_section = f"\n**Generators:** {kinds_list}\n"

    files[str(base_dir / "README.md")] = textwrap.dedent(f"""\
        # {pkg_name}

        {desc}

        ## Installation

        ```bash
        pip install {pkg_name}
        ```

        SecretZero discovers the bundle automatically via `entry_points`.
        {target_section}{gen_section}
        ## Development

        ```bash
        pip install -e ".[dev]"
        pytest
        ```

        ## Usage

        ```yaml
        providers:
          {name}:
            kind: {name}
            auth:
              kind: token
              config:
                token: ${{{name.upper()}_TOKEN}}
        ```
    """)

    # Write all files
    for file_path, content in files.items():
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    console.print(f"[green]✓[/green] Scaffolded bundle [bold]{pkg_name}[/bold] at {base_dir}\n")
    console.print("Generated files:")
    for file_path in sorted(files.keys()):
        rel = Path(file_path).relative_to(base_dir)
        console.print(f"  [cyan]{rel}[/cyan]")

    console.print("\nNext steps:")
    console.print(f"  1. cd {base_dir}")
    console.print(f"  2. Implement the TODO stubs in [cyan]src/{pkg_name}/provider.py[/cyan]")
    if target_kinds:
        console.print(f"  3. Implement target methods in [cyan]src/{pkg_name}/targets.py[/cyan]")
    if generator_kinds:
        console.print(
            f"  {'4' if target_kinds else '3'}. Implement generator in "
            f"[cyan]src/{pkg_name}/generators.py[/cyan]"
        )
    console.print("  • Run [bold]pytest[/bold] to test")
    console.print(f"  • Run [bold]secretzero validate-bundle src/{pkg_name}[/bold] to validate")
    console.print("  • Run [bold]pip install -e .[/bold] to register with SecretZero")


@click.command("provider")
@click.argument("name")
@click.option("--output-dir", "-o", default=".", help="Parent directory for the new package")
@click.option("--with-target", "target_kinds", multiple=True, help="Target kind to scaffold")
@click.option(
    "--with-generator", "generator_kinds", multiple=True, help="Generator kind to scaffold"
)
@click.option("--description", "provider_description", default=None, help="Provider description")
def init_provider(
    name: str,
    output_dir: str,
    target_kinds: tuple[str, ...],
    generator_kinds: tuple[str, ...],
    provider_description: str | None,
) -> None:
    """Scaffold a new SecretZero provider plugin (pip package + entry point)."""
    console = Console()
    scaffold_provider_bundle(
        name,
        output_dir,
        target_kinds,
        generator_kinds,
        provider_description,
        console=console,
    )
