"""Graph visualization for Secretfile relationships."""

from pathlib import Path
from typing import Any, Literal

from secretzero.config import ConfigLoader
from secretzero.lockfile import Lockfile
from secretzero.lockfile_state import sync_state_for_secret_target
from secretzero.models import Secretfile

GraphType = Literal["flow", "detailed", "architecture", "destination"]
OutputFormat = Literal["mermaid", "terminal"]

# Mermaid linkStyle classes (order must match edge declaration order in each diagram).
_EDGE_LINK_STYLES = {
    "neutral": "stroke:#6c757d,stroke-width:2px,color:#6c757d",
    "synced": "stroke:#198754,stroke-width:4px,color:#198754",
    "pending": "stroke:#e97109,stroke-width:4px,color:#e97109",
    "drift": "stroke:#c82832,stroke-width:4px,color:#c82832",
    # Match CLI compact status "unknown" when identity/access prevents classifying as pending.
    "unknown": "stroke:#ffc107,stroke-width:4px,color:#ffc107",
}


class SecretGraphGenerator:
    """Generate visual representations of Secretfile relationships."""

    def __init__(
        self,
        secretfile_path: Path,
        *,
        secretfile: Secretfile | None = None,
        lockfile: Lockfile | None = None,
        identity_preflight: dict[str, Any] | None = None,
    ):
        """Initialize graph generator with a Secretfile.

        Args:
            secretfile_path: Path to Secretfile
            lockfile: Optional lockfile for per-target sync edge coloring
            identity_preflight: Optional ``preflight_provider_identity_policies()`` result for
                policy-aware edge styling (unknown when policies fail for that provider).
        """
        self.secretfile_path = secretfile_path
        self.config_loader = ConfigLoader()
        self.secretfile: Secretfile = (
            secretfile if secretfile is not None else self.config_loader.load_file(secretfile_path)
        )
        self.lockfile = lockfile
        self.identity_preflight = identity_preflight

    def _target_sync_state(self, secret_name: str, target) -> str:
        """Return sync state for target: synced | pending | drift."""
        if self.lockfile is None:
            return "pending"
        return sync_state_for_secret_target(self.lockfile, secret_name, target)

    def _mermaid_edge_class(self, lock_state: str, provider_alias: str) -> str:
        """Map lockfile + identity preflight to Mermaid linkStyle token."""
        if lock_state == "synced":
            return "synced"
        pf = self.identity_preflight
        if pf and pf.get("preflight_error"):
            return "unknown"
        if pf and pf.get("has_policies") and not pf.get("all_ok"):
            for row in pf.get("rows") or []:
                if row.get("provider_alias") == provider_alias and row.get("status") != "ok":
                    return "unknown"
        if lock_state == "pending":
            return "pending"
        return "drift"

    @staticmethod
    def _edge_status_label(edge_class: str) -> str:
        """Short edge label for secret→target links."""
        return {
            "synced": "synced",
            "pending": "pending",
            "drift": "drift",
            "unknown": "unknown",
        }.get(edge_class, "pending")

    @staticmethod
    def _emit_edge_styles(lines: list[str], edge_styles: list[str]) -> None:
        """Emit Mermaid per-edge linkStyle directives."""
        if not edge_styles:
            return
        lines.append("")
        for idx, edge_class in enumerate(edge_styles):
            style = _EDGE_LINK_STYLES.get(edge_class)
            if style is None:
                style = "stroke:#6c757d,stroke-width:3px,color:#6c757d"
            lines.append(f"    linkStyle {idx} {style}")

    def generate_flow_diagram(self) -> str:
        """Generate a flowchart diagram showing generator → secret → targets.

        Returns:
            Mermaid flowchart diagram source
        """
        lines = ["```mermaid", "flowchart LR", "    %% Generators/Sources"]

        generators_seen: set[str] = set()
        destination_groups: dict[tuple[str, str, str], dict[str, str]] = {}
        generator_edge_count = 0
        edges: list[tuple[str, str, str]] = []

        for secret in self.secretfile.secrets:
            secret_id = self._safe_id(secret.name)
            generator_kind = secret.kind
            generator_id = self._safe_id(f"gen_{generator_kind}")

            if generator_id not in generators_seen:
                generator_label = self._format_generator_label(generator_kind)
                lines.append(f'    {generator_id}["{self._escape_mermaid_label(generator_label)}"]')
                generators_seen.add(generator_id)

            secret_label = f"Secret<br/>{secret.name}<br/>type: {generator_kind}"
            lines.append(f'    {secret_id}["{self._escape_mermaid_label(secret_label)}"]')
            lines.append(f"    {generator_id} -->|generates| {secret_id}")
            generator_edge_count += 1

            for idx, target in enumerate(secret.targets):
                provider, kind, destination = self._target_destination(target)
                group_key = (provider, kind, destination)
                group = destination_groups.setdefault(group_key, {})
                entry_label = self._target_entry_label(secret.name, target, idx)
                entry_id = self._safe_id(f"entry_{provider}_{kind}_{destination}_{entry_label}")
                group[entry_id] = entry_label
                state = self._target_sync_state(secret.name, target)
                prov = target.provider or "local"
                edge_class = self._mermaid_edge_class(state, prov)
                edges.append((secret_id, entry_id, edge_class))

        lines.append("")
        lines.append('    subgraph Targets["Target Destinations"]')
        for idx, ((provider, kind, destination), entries) in enumerate(
            sorted(destination_groups.items())
        ):
            cluster_id = self._safe_id(f"dest_cluster_{idx}_{provider}_{kind}_{destination}")
            cluster_title = f"{provider}/{kind}"
            lines.append(
                f'        subgraph {cluster_id}["{self._escape_mermaid_label(cluster_title)}"]'
            )
            for entry_id, entry_label in sorted(entries.items(), key=lambda item: item[1]):
                lines.append(f'            {entry_id}["{self._escape_mermaid_label(entry_label)}"]')
            lines.append("        end")
        lines.append("    end")

        for secret_id, entry_id, edge_class in edges:
            label = self._edge_status_label(edge_class)
            lines.append(f"    {secret_id} -->|{label}| {entry_id}")

        edge_styles = ["neutral"] * generator_edge_count + [e[2] for e in edges]
        self._emit_edge_styles(lines, edge_styles)
        lines.append("```")
        return "\n".join(lines)

    def generate_detailed_diagram(self) -> str:
        """Generate detailed diagram with configuration details.

        Returns:
            Mermaid diagram source with detailed configuration
        """
        lines = ["```mermaid", "flowchart TB", "    %% Detailed Secret Configuration", ""]
        destination_groups: dict[tuple[str, str, str], dict[str, str]] = {}
        generator_edge_count = 0
        edges: list[tuple[str, str, str]] = []

        for secret in self.secretfile.secrets:
            secret_id = self._safe_id(secret.name)
            generator_id = self._safe_id(f"gen_{secret.name}")

            # Generator node with config details
            generator_label = self._format_detailed_generator(secret)
            lines.append(f'    {generator_id}["{self._escape_mermaid_label(generator_label)}"]')

            # Secret node
            secret_label = f"🔐 {secret.name}"
            lines.append(f'    {secret_id}["{self._escape_mermaid_label(secret_label)}"]')
            lines.append(f"    {generator_id} --> {secret_id}")
            generator_edge_count += 1

            for idx, target in enumerate(secret.targets):
                provider, kind, destination = self._target_destination(target)
                group_key = (provider, kind, destination)
                group = destination_groups.setdefault(group_key, {})
                entry_label = self._target_entry_label(secret.name, target, idx)
                detail = self._format_detailed_target(target)
                child_label = f"{entry_label}<br/>{detail}"
                entry_id = self._safe_id(f"d_entry_{provider}_{kind}_{destination}_{entry_label}")
                group[entry_id] = child_label
                state = self._target_sync_state(secret.name, target)
                prov = target.provider or "local"
                edge_class = self._mermaid_edge_class(state, prov)
                edges.append((secret_id, entry_id, edge_class))

            lines.append("")  # Add spacing between secrets

        lines.append('    subgraph Targets["Target Destinations"]')
        for idx, ((provider, kind, destination), entries) in enumerate(
            sorted(destination_groups.items())
        ):
            cluster_id = self._safe_id(f"d_dest_cluster_{idx}_{provider}_{kind}_{destination}")
            cluster_title = f"{provider}/{kind}"
            lines.append(
                f'        subgraph {cluster_id}["{self._escape_mermaid_label(cluster_title)}"]'
            )
            for entry_id, entry_label in sorted(entries.items(), key=lambda item: item[1]):
                lines.append(f'            {entry_id}["{self._escape_mermaid_label(entry_label)}"]')
            lines.append("        end")
        lines.append("    end")

        for secret_id, entry_id, edge_class in edges:
            label = self._edge_status_label(edge_class)
            lines.append(f"    {secret_id} -->|{label}| {entry_id}")

        edge_styles = ["neutral"] * generator_edge_count + [e[2] for e in edges]
        self._emit_edge_styles(lines, edge_styles)
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
                lines.append(f'        {target_id}["{self._escape_mermaid_label(target_label)}"]')

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

    def generate_destination_diagram(self) -> str:
        """Generate destination-centric graph grouped by target destinations."""
        lines = [
            "```mermaid",
            "flowchart LR",
            "    %% Destination-centric Secret Mapping",
            "",
            '    subgraph Secrets["Secrets"]',
        ]
        for secret in self.secretfile.secrets:
            secret_id = self._safe_id(f"secret_{secret.name}")
            lines.append(
                f'        {secret_id}["{self._escape_mermaid_label(f"🔐 {secret.name}<br/>{secret.kind}")}"]'
            )
        lines.append("    end")
        lines.append("")
        lines.append('    subgraph Destinations["Target Destinations"]')

        destination_groups: dict[tuple[str, str, str], dict[str, str]] = {}
        edges: list[tuple[str, str, str]] = []
        edge_styles: list[str] = []
        for secret in self.secretfile.secrets:
            secret_id = self._safe_id(f"secret_{secret.name}")
            for idx, target in enumerate(secret.targets):
                provider, kind, destination = self._target_destination(target)
                key = (provider, kind, destination)
                entry_label = self._target_entry_label(secret.name, target, idx)
                entry_id = self._safe_id(
                    f"dest_entry_{provider}_{kind}_{destination}_{entry_label}"
                )
                destination_groups.setdefault(key, {})[entry_id] = entry_label
                state = self._target_sync_state(secret.name, target)
                prov = target.provider or "local"
                edge_class = self._mermaid_edge_class(state, prov)
                edges.append((secret_id, entry_id, edge_class))
                edge_styles.append(edge_class)

        for idx, ((provider, kind, destination), entries) in enumerate(
            sorted(destination_groups.items())
        ):
            cluster_id = self._safe_id(f"dest_group_{idx}_{provider}_{kind}_{destination}")
            lines.append(
                f'        subgraph {cluster_id}["{self._escape_mermaid_label(f"{provider}/{kind}")}"]'
            )
            for entry_id, entry_label in sorted(entries.items(), key=lambda x: x[1]):
                lines.append(f'            {entry_id}["{self._escape_mermaid_label(entry_label)}"]')
            lines.append("        end")
        lines.append("    end")
        lines.append("")
        for secret_id, entry_id, edge_class in edges:
            label = self._edge_status_label(edge_class)
            lines.append(f"    {secret_id} -->|{label}| {entry_id}")
        self._emit_edge_styles(lines, edge_styles)
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

    def _escape_mermaid_label(self, text: str) -> str:
        """Escape Mermaid label text used inside double-quoted nodes."""
        return text.replace("\\", "\\\\").replace('"', "&quot;")

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

    def _cfg_get(self, target, key: str) -> str | None:
        cfg = target.config
        if isinstance(cfg, dict):
            val = cfg.get(key)
        else:
            val = getattr(cfg, key, None)
        if val is None:
            return None
        txt = str(val).strip()
        return txt if txt else None

    def _target_destination(self, target) -> tuple[str, str, str]:
        provider = target.provider or "local"
        kind = str(target.kind)
        destination = (
            self._cfg_get(target, "path")
            or self._cfg_get(target, "repo")
            or self._cfg_get(target, "name")
            or self._cfg_get(target, "secret_name")
            or self._cfg_get(target, "output_path")
            or "default"
        )
        return provider, kind, destination

    def _target_entry_label(self, secret_name: str, target, idx: int) -> str:
        for candidate in ("key", "secret_name", "data_key", "name"):
            value = self._cfg_get(target, candidate)
            if value:
                return f"{candidate}: {value}"
        return f"name: {secret_name}" if secret_name else f"entry: {idx + 1}"

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
    *,
    secretfile: Secretfile | None = None,
    lockfile: Lockfile | None = None,
    identity_preflight: dict[str, Any] | None = None,
) -> str:
    """Generate visual graph from Secretfile.

    Args:
        secretfile_path: Path to Secretfile
        graph_type: Type of graph to generate
        output_format: Output format (mermaid or terminal)
        lockfile: Optional lockfile for per-target edge colors
        identity_preflight: Optional result of
            :meth:`secretzero.sync.SyncEngine.preflight_provider_identity_policies`

    Returns:
        Graph representation as string
    """
    generator = SecretGraphGenerator(
        secretfile_path,
        secretfile=secretfile,
        lockfile=lockfile,
        identity_preflight=identity_preflight,
    )

    if output_format == "terminal":
        return generator.generate_terminal_summary()

    # Mermaid diagrams
    if graph_type == "flow":
        return generator.generate_flow_diagram()
    elif graph_type == "detailed":
        return generator.generate_detailed_diagram()
    elif graph_type == "architecture":
        return generator.generate_architecture_diagram()
    elif graph_type == "destination":
        return generator.generate_destination_diagram()
    else:
        raise ValueError(f"Unknown graph type: {graph_type}")
