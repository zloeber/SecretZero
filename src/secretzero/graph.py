"""Graph visualization for Secretfile relationships."""

from pathlib import Path
from typing import Literal

from secretzero.config import ConfigLoader
from secretzero.models import Secretfile

GraphType = Literal["flow", "detailed", "architecture"]
OutputFormat = Literal["mermaid", "terminal"]


class SecretGraphGenerator:
    """Generate visual representations of Secretfile relationships."""

    def __init__(self, secretfile_path: Path):
        """Initialize graph generator with a Secretfile.

        Args:
            secretfile_path: Path to Secretfile
        """
        self.secretfile_path = secretfile_path
        self.config_loader = ConfigLoader()
        self.secretfile: Secretfile = self.config_loader.load_file(secretfile_path)

    def generate_flow_diagram(self) -> str:
        """Generate a flowchart diagram showing generator → secret → targets.

        Returns:
            Mermaid flowchart diagram source
        """
        lines = [
            "```mermaid",
            "flowchart LR",
            "    %% Generators/Sources",
        ]

        # Track unique generators and targets
        generators_seen = set()
        targets_seen = set()

        # Process each secret
        for secret in self.secretfile.secrets:
            secret_id = self._safe_id(secret.name)
            generator_kind = secret.kind
            generator_id = self._safe_id(f"gen_{generator_kind}")

            # Add generator node if not seen before
            if generator_id not in generators_seen:
                generator_label = self._format_generator_label(generator_kind)
                lines.append(f"    {generator_id}[{generator_label}]")
                generators_seen.add(generator_id)

            # Add secret node
            secret_label = f"Secret<br/>{secret.name}<br/>type: {generator_kind}"
            lines.append(f'    {secret_id}["{secret_label}"]')

            # Connect generator to secret
            lines.append(f"    {generator_id} -->|generates| {secret_id}")

            # Add target nodes and connections
            for idx, target in enumerate(secret.targets):
                target_provider = target.provider or "local"
                target_kind = target.kind
                target_id = self._safe_id(
                    f"target_{secret.name}_{target_provider}_{target_kind}_{idx}"
                )

                if target_id not in targets_seen:
                    target_label = self._format_target_label(target)
                    lines.append(f'    {target_id}["{target_label}"]')
                    targets_seen.add(target_id)

                lines.append(f"    {secret_id} -->|syncs to| {target_id}")

        lines.append("```")
        return "\n".join(lines)

    def generate_detailed_diagram(self) -> str:
        """Generate detailed diagram with configuration details.

        Returns:
            Mermaid diagram source with detailed configuration
        """
        lines = [
            "```mermaid",
            "flowchart TB",
            "    %% Detailed Secret Configuration",
            "",
        ]

        for secret in self.secretfile.secrets:
            secret_id = self._safe_id(secret.name)
            generator_id = self._safe_id(f"gen_{secret.name}")

            # Generator node with config details
            generator_label = self._format_detailed_generator(secret)
            lines.append(f'    {generator_id}["{generator_label}"]')

            # Secret node
            secret_label = f"🔐 {secret.name}"
            lines.append(f'    {secret_id}["{secret_label}"]')
            lines.append(f"    {generator_id} --> {secret_id}")

            # Target nodes with details
            for idx, target in enumerate(secret.targets):
                target_id = self._safe_id(f"target_{secret.name}_{idx}")
                target_label = self._format_detailed_target(target)
                lines.append(f'    {target_id}["{target_label}"]')
                lines.append(f"    {secret_id} --> {target_id}")

            lines.append("")  # Add spacing between secrets

        lines.append("```")
        return "\n".join(lines)

    def generate_architecture_diagram(self) -> str:
        """Generate high-level architecture diagram showing providers and flow.

        Returns:
            Mermaid diagram source showing system architecture
        """
        lines = [
            "```mermaid",
            "graph TB",
            "    %% SecretZero Architecture",
            "",
            '    subgraph Sources["Secret Generators"]',
        ]

        # Collect unique generators
        generators = set()
        for secret in self.secretfile.secrets:
            generators.add(secret.kind)

        for gen in sorted(generators):
            gen_id = self._safe_id(f"src_{gen}")
            gen_label = self._format_generator_label(gen)
            lines.append(f"        {gen_id}[{gen_label}]")

        lines.append("    end")
        lines.append("")
        lines.append('    subgraph Secrets["Secret Store"]')
        lines.append("        SecretZero[SecretZero Engine]")
        lines.append("    end")
        lines.append("")
        lines.append('    subgraph Targets["Target Destinations"]')

        # Collect unique target types grouped by provider
        provider_targets = {}
        for secret in self.secretfile.secrets:
            for target in secret.targets:
                provider = target.provider or "local"
                if provider not in provider_targets:
                    provider_targets[provider] = set()
                provider_targets[provider].add(target.kind)

        for provider, target_kinds in sorted(provider_targets.items()):
            for kind in sorted(target_kinds):
                target_id = self._safe_id(f"tgt_{provider}_{kind}")
                target_label = f"{provider}/{kind}"
                lines.append(f'        {target_id}["{target_label}"]')

        lines.append("    end")
        lines.append("")

        # Connect generators to SecretZero
        for gen in sorted(generators):
            gen_id = self._safe_id(f"src_{gen}")
            lines.append(f"    {gen_id} --> SecretZero")

        # Connect SecretZero to targets
        for provider, target_kinds in sorted(provider_targets.items()):
            for kind in sorted(target_kinds):
                target_id = self._safe_id(f"tgt_{provider}_{kind}")
                lines.append(f"    SecretZero --> {target_id}")

        lines.append("```")
        return "\n".join(lines)

    def generate_terminal_summary(self) -> str:
        """Generate text-based summary for terminal display.

        Returns:
            Formatted text summary
        """
        lines = [
            "SecretZero Configuration Summary",
            "=" * 80,
            "",
        ]

        # Metadata
        if self.secretfile.metadata:
            lines.append("Metadata:")
            if hasattr(self.secretfile.metadata, "project") and self.secretfile.metadata.project:
                lines.append(f"  Project: {self.secretfile.metadata.project}")
            if hasattr(self.secretfile.metadata, "owner") and self.secretfile.metadata.owner:
                lines.append(f"  Owner: {self.secretfile.metadata.owner}")
            if (
                hasattr(self.secretfile.metadata, "description")
                and self.secretfile.metadata.description
            ):
                lines.append(f"  Description: {self.secretfile.metadata.description}")
            lines.append("")

        # Providers
        if self.secretfile.providers:
            lines.append(f"Providers ({len(self.secretfile.providers)}):")
            for name, provider in self.secretfile.providers.items():
                lines.append(f"  • {name} ({provider.kind})")
            lines.append("")

        # Secrets
        lines.append(f"Secrets ({len(self.secretfile.secrets)}):")
        for secret in self.secretfile.secrets:
            lines.append(f"\n  {secret.name}")
            lines.append(f"    Generator: {secret.kind}")

            if secret.targets:
                lines.append(f"    Targets ({len(secret.targets)}):")
                for target in secret.targets:
                    provider = target.provider or "local"
                    lines.append(f"      → {provider}/{target.kind}")
                    # Show key config details
                    if hasattr(target.config, "path"):
                        lines.append(f"        path: {target.config.path}")
                    if hasattr(target.config, "secret_name"):
                        lines.append(f"        secret_name: {target.config.secret_name}")
                    if hasattr(target.config, "namespace"):
                        lines.append(f"        namespace: {target.config.namespace}")

        lines.append("")
        lines.append("=" * 80)
        return "\n".join(lines)

    def _safe_id(self, text: str) -> str:
        """Convert text to safe Mermaid node ID.

        Args:
            text: Text to convert

        Returns:
            Safe node ID
        """
        # Replace special characters with underscores
        safe = text.replace("-", "_").replace(".", "_").replace(" ", "_")
        safe = "".join(c if c.isalnum() or c == "_" else "" for c in safe)
        return safe

    def _format_generator_label(self, generator_kind: str) -> str:
        """Format generator label for display.

        Args:
            generator_kind: Generator type

        Returns:
            Formatted label
        """
        # Humanize generator names
        label = generator_kind.replace("_", " ").title()
        return f"📝 {label}"

    def _format_target_label(self, target) -> str:
        """Format target label for display.

        Args:
            target: Target configuration

        Returns:
            Formatted label
        """
        provider = target.provider or "local"
        kind = target.kind

        # Add relevant config details
        details = []
        if hasattr(target.config, "path"):
            details.append(f"path: {target.config.path}")
        elif hasattr(target.config, "secret_name"):
            details.append(target.config.secret_name)
        elif hasattr(target.config, "name"):
            details.append(target.config.name)

        label = f"Target<br/>{provider}/{kind}"
        if details:
            label += f"<br/>{details[0]}"

        return label

    def _format_detailed_generator(self, secret) -> str:
        """Format detailed generator information.

        Args:
            secret: Secret configuration

        Returns:
            Formatted generator label
        """
        lines = [f"Generator: {secret.kind}"]

        # Add key config parameters
        if secret.config:
            config_dict = (
                secret.config if isinstance(secret.config, dict) else secret.config.model_dump()
            )
            for key, value in list(config_dict.items())[:3]:  # Show first 3 config items
                if not str(value).startswith("${"):  # Don't show env vars
                    lines.append(f"{key}: {value}")

        return "<br/>".join(lines)

    def _format_detailed_target(self, target) -> str:
        """Format detailed target information.

        Args:
            target: Target configuration

        Returns:
            Formatted target label
        """
        provider = target.provider or "local"
        lines = [
            f"Target: {provider}/{target.kind}",
        ]

        # Add key config parameters
        if hasattr(target.config, "path"):
            lines.append(f"path: {target.config.path}")
        if hasattr(target.config, "format"):
            lines.append(f"format: {target.config.format}")
        if hasattr(target.config, "secret_name"):
            lines.append(f"secret: {target.config.secret_name}")
        if hasattr(target.config, "namespace"):
            lines.append(f"namespace: {target.config.namespace}")

        return "<br/>".join(lines)


def generate_graph(
    secretfile_path: Path,
    graph_type: GraphType = "flow",
    output_format: OutputFormat = "mermaid",
) -> str:
    """Generate visual graph from Secretfile.

    Args:
        secretfile_path: Path to Secretfile
        graph_type: Type of graph to generate
        output_format: Output format (mermaid or terminal)

    Returns:
        Graph representation as string
    """
    generator = SecretGraphGenerator(secretfile_path)

    if output_format == "terminal":
        return generator.generate_terminal_summary()

    # Mermaid diagrams
    if graph_type == "flow":
        return generator.generate_flow_diagram()
    elif graph_type == "detailed":
        return generator.generate_detailed_diagram()
    elif graph_type == "architecture":
        return generator.generate_architecture_diagram()
    else:
        raise ValueError(f"Unknown graph type: {graph_type}")
