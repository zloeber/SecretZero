"""AI-powered secret discovery for SecretZero.

This module implements the :class:`DiscoveryAgent`, which scans a project
directory for files that may contain secrets, credentials, or other sensitive
configuration values.  It operates in two complementary modes:

1. **Pattern-based** (always available): Regular-expression heuristics
   identify common secret patterns (API keys, passwords, database URLs, etc.)
   and produce a confidence score based on the strength of the match.

2. **LLM-enhanced** (optional, requires ``secretzero[ai]`` extras): When one
   of the supported LangChain/LangGraph provider packages is installed and
   configured, the agent passes file snippets to the LLM for deeper semantic
   analysis.  LLM results are merged with pattern results and weighted by
   confidence.

The output is a ``Secretfile.detect.yml`` YAML file with recommended secret
definitions, generators, and targets.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from secretzero.cli_config import CliConfig, CliConfigLoader


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class SecretCandidate(BaseModel):
    """A single secret discovered during a scan."""

    name: str = ""
    description: str = ""
    source_file: str = ""
    line_number: int = 0
    raw_value: str = ""
    confidence: float = 0.0
    suggested_generator: str = "static"
    suggested_target_kind: str = "file"
    tags: list[str] = []

    def to_secretfile_entry(self) -> dict[str, Any]:
        """Convert to a Secretfile secret definition.

        Returns:
            Dictionary ready to serialise into a Secretfile YAML entry.
        """
        entry: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "kind": self.suggested_generator,
            "config": {},
            "targets": [
                {
                    "provider": "local",
                    "kind": self.suggested_target_kind,
                    "config": {"path": ".env", "format": "dotenv", "merge": True},
                }
            ],
        }
        if self.tags:
            entry["labels"] = {tag: "true" for tag in self.tags}
        return entry


@dataclass
class DiscoveryResult:
    """Aggregated result of a discovery run."""

    candidates: list[SecretCandidate] = field(default_factory=list)
    files_scanned: int = 0
    output_path: Path | None = None
    dry_run: bool = False

    @property
    def total_secrets(self) -> int:
        """Number of candidate secrets found."""
        return len(self.candidates)

    def summary(self) -> str:
        """Human-readable one-line summary.

        Returns:
            Summary string for display.
        """
        status = "dry-run" if self.dry_run else "written"
        out = str(self.output_path) if self.output_path else "N/A"
        return (
            f"Scanned {self.files_scanned} file(s), "
            f"found {self.total_secrets} candidate(s) [{status}] → {out}"
        )


# ---------------------------------------------------------------------------
# Secret patterns
# ---------------------------------------------------------------------------

# Each entry: (pattern_name, regex, confidence, suggested_generator, tags)
_SECRET_PATTERNS: list[tuple[str, str, float, str, list[str]]] = [
    # High confidence patterns (well-known formats)
    (
        "aws_access_key",
        r"AKIA[0-9A-Z]{16}",
        0.95,
        "static",
        ["aws", "access-key"],
    ),
    (
        "aws_secret_key",
        r"(?i)(aws_secret_access_key|aws_secret_key)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
        0.90,
        "random_string",
        ["aws", "secret-key"],
    ),
    (
        "github_token",
        r"gh[pousr]_[A-Za-z0-9_]{36,255}",
        0.95,
        "static",
        ["github", "token"],
    ),
    (
        "stripe_key",
        r"sk_(live|test)_[0-9a-zA-Z]{24,}",
        0.95,
        "static",
        ["stripe", "api-key"],
    ),
    (
        "jwt_secret",
        r"(?i)(jwt_secret|jwt_key|secret_key)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{32,})['\"]?",
        0.85,
        "random_string",
        ["jwt", "secret"],
    ),
    # Medium-high confidence
    (
        "database_url",
        r"(?i)(database_url|db_url|connection_string)\s*[=:]\s*['\"]?([a-z]+:\/\/[^\s'\"]+)['\"]?",
        0.80,
        "static",
        ["database", "connection"],
    ),
    (
        "database_password",
        r"(?i)(db_password|database_password|db_pass|postgres_password|mysql_password)\s*[=:]\s*['\"]?([^\s'\"]{8,})['\"]?",
        0.80,
        "random_password",
        ["database", "password"],
    ),
    (
        "api_key_generic",
        r"(?i)(api_key|apikey|api_secret|api_token)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?",
        0.75,
        "random_string",
        ["api-key"],
    ),
    (
        "password_generic",
        r"(?i)(password|passwd|pwd|secret)\s*[=:]\s*['\"]?([^\s'\"]{8,})['\"]?",
        0.70,
        "random_password",
        ["password"],
    ),
    # Medium confidence
    (
        "slack_webhook",
        r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+",
        0.90,
        "static",
        ["slack", "webhook"],
    ),
    (
        "private_key_header",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        0.95,
        "static",
        ["private-key", "tls"],
    ),
    (
        "oauth_client_secret",
        r"(?i)(client_secret|oauth_secret|consumer_secret)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?",
        0.80,
        "random_string",
        ["oauth", "secret"],
    ),
    (
        "sendgrid_key",
        r"SG\.[A-Za-z0-9_\-]{22,}\.[A-Za-z0-9_\-]{43,}",
        0.95,
        "static",
        ["sendgrid", "api-key"],
    ),
    (
        "twilio_key",
        r"SK[0-9a-fA-F]{32}",
        0.90,
        "static",
        ["twilio", "api-key"],
    ),
    (
        "vault_token",
        r"(?i)(vault_token|vault_addr)\s*[=:]\s*['\"]?([^\s'\"]{10,})['\"]?",
        0.75,
        "static",
        ["vault", "token"],
    ),
    (
        "encryption_key",
        r"(?i)(encryption_key|encrypt_key|aes_key|secret_key)\s*[=:]\s*['\"]?([A-Fa-f0-9]{32,64})['\"]?",
        0.80,
        "random_string",
        ["encryption", "key"],
    ),
]

# Compiled patterns (lazy)
_COMPILED: list[tuple[str, re.Pattern[str], float, str, list[str]]] | None = None


def _get_compiled_patterns() -> list[tuple[str, re.Pattern[str], float, str, list[str]]]:
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = [
            (name, re.compile(pattern, re.MULTILINE), confidence, generator, tags)
            for name, pattern, confidence, generator, tags in _SECRET_PATTERNS
        ]
    return _COMPILED


# ---------------------------------------------------------------------------
# Discovery agent
# ---------------------------------------------------------------------------


class DiscoveryAgent:
    """Scans a project directory for secrets and generates a ``Secretfile.detect.yml``.

    Args:
        config: Optional :class:`~secretzero.cli_config.CliConfig`; defaults
            to settings loaded via :class:`~secretzero.cli_config.CliConfigLoader`.
    """

    def __init__(self, config: CliConfig | None = None) -> None:
        if config is None:
            loader = CliConfigLoader()
            config = loader.load()
        self.config = config
        self._llm: Any = None
        self._llm_available: bool | None = None  # cached availability check

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(
        self,
        project_root: Path | str = ".",
        output_path: Path | str | None = None,
        dry_run: bool = False,
        use_llm: bool = True,
        local_only: bool = False,
        provider: str | None = None,
        model: str | None = None,
    ) -> DiscoveryResult:
        """Run the full discovery pipeline.

        Args:
            project_root: Root directory of the project to scan.
            output_path: Where to write the generated ``Secretfile.detect.yml``.
                Defaults to ``<project_root>/Secretfile.detect.yml``.
            dry_run: When ``True``, analyse but do not write any files.
            use_llm: When ``True`` (default), attempt to enhance results with
                an LLM if one is available.
            local_only: Restrict LLM usage to local providers only (e.g. Ollama).
            provider: Override the default LLM provider from config.
            model: Override the default model from config.

        Returns:
            :class:`DiscoveryResult` with all candidate secrets and metadata.
        """
        root = Path(project_root).resolve()
        if output_path is None:
            out = root / "Secretfile.detect.yml"
        else:
            out = Path(output_path).resolve()

        # 1. Scan files
        files = self._collect_files(root)

        # 2. Analyse with pattern engine
        candidates: list[SecretCandidate] = []
        for file_path in files:
            candidates.extend(self._scan_file(file_path, root))

        # 3. Optionally enhance with LLM
        if use_llm:
            effective_provider = provider or self.config.llm.default_provider
            if local_only and effective_provider not in ("ollama",):
                effective_provider = "ollama"
            llm_candidates = self._llm_enhance(
                files=files,
                root=root,
                provider=effective_provider,
                model=model,
            )
            candidates = self._merge_candidates(candidates, llm_candidates)

        # 4. Filter by confidence threshold
        threshold = self.config.discovery.confidence_threshold
        candidates = [c for c in candidates if c.confidence >= threshold]

        # 5. Deduplicate by name
        candidates = self._deduplicate(candidates)

        result = DiscoveryResult(
            candidates=candidates,
            files_scanned=len(files),
            output_path=out,
            dry_run=dry_run,
        )

        # 6. Write output unless dry-run
        if not dry_run and candidates:
            self._write_secretfile(candidates, out)

        return result

    # ------------------------------------------------------------------
    # File collection
    # ------------------------------------------------------------------

    def _collect_files(self, root: Path) -> list[Path]:
        """Collect files matching the discovery include/exclude patterns.

        Args:
            root: Project root directory.

        Returns:
            List of matching :class:`~pathlib.Path` objects.
        """
        include_patterns = self.config.discovery.include_patterns
        exclude_patterns = self.config.discovery.exclude_patterns
        max_files = self.config.discovery.max_files

        collected: list[Path] = []

        for item in root.rglob("*"):
            if not item.is_file():
                continue
            if len(collected) >= max_files:
                break

            rel = item.relative_to(root)
            rel_str = str(rel)

            # Check exclusions using all path parts to support **/dir/** patterns
            if self._is_excluded(rel_str, rel.parts, exclude_patterns):
                continue

            # Check inclusions
            included = any(fnmatch.fnmatch(item.name, pat) for pat in include_patterns)
            # Also check full relative path for patterns like **/.github/workflows/*.yml
            if not included:
                included = any(fnmatch.fnmatch(rel_str, pat) for pat in include_patterns)

            if included:
                collected.append(item)

        return collected

    def _is_excluded(self, rel_str: str, parts: tuple[str, ...], patterns: list[str]) -> bool:
        """Return ``True`` if a relative path matches any exclusion pattern.

        Handles patterns containing ``**`` by testing each possible sub-path
        slice against the inner glob expression.

        Args:
            rel_str: Relative path as a POSIX string (e.g. ``"node_modules/pkg/.env"``).
            parts: Tuple of path parts (e.g. ``("node_modules", "pkg", ".env")``).
            patterns: Exclusion glob patterns from config.

        Returns:
            ``True`` when the file should be excluded.
        """
        for pat in patterns:
            # Direct match against the full relative path string
            if fnmatch.fnmatch(rel_str, pat):
                return True

            # Handle **/dir/** and **/dir patterns by checking if any path
            # segment or segment sequence matches the inner pattern
            if "**" in pat:
                # Strip leading and trailing ** components, leaving the
                # "inner" pattern to test against individual parts or
                # sub-path strings built from consecutive parts.
                inner = pat.strip("*").strip("/")
                if not inner:
                    continue
                # Check if any consecutive sub-sequence of parts matches
                n = len(parts)
                for start in range(n):
                    for end in range(start + 1, n + 1):
                        sub = "/".join(parts[start:end])
                        if fnmatch.fnmatch(sub, inner):
                            return True
        return False

    # ------------------------------------------------------------------
    # Pattern-based scanning
    # ------------------------------------------------------------------

    def _scan_file(self, file_path: Path, root: Path) -> list[SecretCandidate]:
        """Scan a single file for secret patterns.

        Args:
            file_path: Path to the file.
            root: Project root (used for relative path display).

        Returns:
            List of :class:`SecretCandidate` instances found in the file.
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        rel = str(file_path.relative_to(root))
        candidates: list[SecretCandidate] = []
        seen_names: set[str] = set()

        for name, pattern, confidence, generator, tags in _get_compiled_patterns():
            for match in pattern.finditer(content):
                line_no = content[: match.start()].count("\n") + 1
                raw = match.group(0)[:80]  # truncate for safety

                # Derive a unique variable name from the pattern name and file
                var_name = self._derive_var_name(name, file_path, match)

                # Avoid duplicate names within the same file scan
                if var_name in seen_names:
                    continue
                seen_names.add(var_name)

                # Skip obvious placeholder/example values
                if self._is_placeholder(raw):
                    continue

                candidates.append(
                    SecretCandidate(
                        name=var_name,
                        description=f"Detected {name.replace('_', ' ')} in {rel}",
                        source_file=rel,
                        line_number=line_no,
                        raw_value="",  # Never store raw secret values
                        confidence=confidence,
                        suggested_generator=generator,
                        suggested_target_kind="file",
                        tags=list(tags),
                    )
                )

        return candidates

    def _derive_var_name(
        self, pattern_name: str, file_path: Path, match: re.Match  # type: ignore[type-arg]
    ) -> str:
        """Derive a clean variable name for a discovered secret.

        Args:
            pattern_name: Name of the matched pattern.
            file_path: File where the match was found.
            match: The regex match object.

        Returns:
            Snake-case variable name.
        """
        # Try to extract the key name from the match (group 1 if available)
        try:
            key = match.group(1).strip().lower()
            key = re.sub(r"[^a-z0-9_]", "_", key)
            if key:
                return key
        except IndexError:
            pass

        return pattern_name

    def _is_placeholder(self, value: str) -> bool:
        """Return ``True`` if the value looks like a placeholder, not a real secret.

        Args:
            value: Raw value extracted from source.

        Returns:
            ``True`` when the value should be skipped.
        """
        placeholder_patterns = [
            r"^[Xx]+$",
            r"^(your|change|replace|placeholder|example|test|dummy|sample|fake)",
            r"^\$\{.*\}$",
            r"^<.*>$",
            r"^.*TODO.*$",
            r"^.*FIXME.*$",
            r"^\*+$",
        ]
        lower = value.lower().strip(" '\"")
        for pat in placeholder_patterns:
            if re.match(pat, lower, re.IGNORECASE):
                return True
        return False

    # ------------------------------------------------------------------
    # LLM enhancement
    # ------------------------------------------------------------------

    def _llm_enhance(
        self,
        files: list[Path],
        root: Path,
        provider: str,
        model: str | None,
    ) -> list[SecretCandidate]:
        """Attempt LLM-based discovery enhancement.

        Gracefully returns an empty list if no LLM libraries are installed
        or if the provider is unreachable.

        Args:
            files: Files to analyse.
            root: Project root directory.
            provider: LLM provider name to use.
            model: Model override; ``None`` uses the configured default.

        Returns:
            List of :class:`SecretCandidate` instances from LLM analysis.
        """
        llm = self._get_llm(provider=provider, model=model)
        if llm is None:
            return []

        candidates: list[SecretCandidate] = []
        # Process a sample of files (limit to avoid excessive API calls)
        sample = files[:20]

        for file_path in sample:
            try:
                snippet = self._build_file_snippet(file_path, root)
                if not snippet:
                    continue
                llm_result = self._call_llm(llm, snippet)
                candidates.extend(self._parse_llm_result(llm_result, file_path, root))
            except Exception:  # noqa: BLE001 – graceful degradation
                continue

        return candidates

    def _get_llm(self, provider: str, model: str | None) -> Any:
        """Instantiate the LLM client for the given provider.

        Returns ``None`` if the required library is not installed.

        Args:
            provider: Provider name (ollama, openai, anthropic, azure_openai).
            model: Optional model override.

        Returns:
            LangChain LLM instance or ``None``.
        """
        try:
            if provider == "ollama":
                from langchain_ollama import OllamaLLM  # type: ignore[import-untyped]

                cfg = self.config.llm.providers.ollama
                return OllamaLLM(
                    base_url=cfg.base_url,
                    model=model or cfg.model,
                    temperature=cfg.temperature,
                )

            if provider == "openai":
                from langchain_openai import OpenAI  # type: ignore[import-untyped]

                cfg = self.config.llm.providers.openai
                kwargs: dict[str, Any] = {
                    "model_name": model or cfg.model,
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                }
                api_key = cfg.api_key or os.environ.get("OPENAI_API_KEY")
                if api_key:
                    kwargs["openai_api_key"] = api_key
                if cfg.organization or os.environ.get("OPENAI_ORG_ID"):
                    kwargs["openai_organization"] = cfg.organization or os.environ.get(
                        "OPENAI_ORG_ID"
                    )
                return OpenAI(**kwargs)

            if provider == "anthropic":
                from langchain_anthropic import Anthropic  # type: ignore[import-untyped]

                cfg = self.config.llm.providers.anthropic
                kwargs = {
                    "model_name": model or cfg.model,
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                }
                api_key = cfg.api_key or os.environ.get("ANTHROPIC_API_KEY")
                if api_key:
                    kwargs["anthropic_api_key"] = api_key
                return Anthropic(**kwargs)

            if provider == "azure_openai":
                from langchain_openai import AzureOpenAI  # type: ignore[import-untyped]

                cfg = self.config.llm.providers.azure_openai
                kwargs = {
                    "azure_deployment": model
                    or cfg.deployment
                    or os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
                    "azure_endpoint": cfg.endpoint
                    or os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                    "openai_api_version": cfg.api_version,
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                }
                api_key = cfg.api_key or os.environ.get("AZURE_OPENAI_API_KEY")
                if api_key:
                    kwargs["openai_api_key"] = api_key
                return AzureOpenAI(**kwargs)

        except ImportError:
            return None
        except Exception:  # noqa: BLE001
            return None

        return None

    def _build_file_snippet(self, file_path: Path, root: Path, max_chars: int = 2000) -> str:
        """Build a truncated snippet of a file for LLM analysis.

        Args:
            file_path: File to read.
            root: Project root (for relative path display).
            max_chars: Maximum number of characters to include.

        Returns:
            Formatted snippet string, or empty string on read error.
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            snippet = content[:max_chars]
            rel = file_path.relative_to(root)
            return f"File: {rel}\n---\n{snippet}"
        except OSError:
            return ""

    def _call_llm(self, llm: Any, prompt_context: str) -> str:
        """Invoke the LLM with a discovery prompt.

        Args:
            llm: LangChain LLM instance.
            prompt_context: File content context to include in the prompt.

        Returns:
            Raw LLM response string.
        """
        prompt = (
            "You are a security expert analysing project files for secrets, credentials, "
            "and sensitive configuration values.\n\n"
            "Review the following file snippet and list any secrets you find. "
            "For each secret, respond with one line in the format:\n"
            "SECRET_NAME|description|generator_type|confidence\n\n"
            "Where:\n"
            "- SECRET_NAME: snake_case name for the secret\n"
            "- description: brief description of what it is\n"
            "- generator_type: one of: static, random_password, random_string\n"
            "- confidence: a float from 0.0 to 1.0\n\n"
            "Only list genuine secrets, not placeholder values.\n"
            "If no secrets are found, respond with: NONE\n\n"
            f"{prompt_context}"
        )
        try:
            return str(llm.invoke(prompt))
        except Exception:  # noqa: BLE001
            return ""

    def _parse_llm_result(
        self, llm_output: str, file_path: Path, root: Path
    ) -> list[SecretCandidate]:
        """Parse structured LLM output into :class:`SecretCandidate` instances.

        Args:
            llm_output: Raw response from the LLM.
            file_path: The file that was analysed.
            root: Project root for relative path display.

        Returns:
            List of parsed candidates.
        """
        if not llm_output or llm_output.strip().upper() == "NONE":
            return []

        rel = str(file_path.relative_to(root))
        candidates: list[SecretCandidate] = []

        for line in llm_output.strip().splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4:
                continue

            secret_name, description, generator, conf_str = parts[:4]

            # Sanitise name
            secret_name = re.sub(r"[^a-z0-9_]", "_", secret_name.lower())
            if not secret_name:
                continue

            # Parse confidence
            try:
                confidence = float(conf_str)
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                confidence = 0.5

            # Validate generator type
            valid_generators = {"static", "random_password", "random_string"}
            if generator not in valid_generators:
                generator = "static"

            candidates.append(
                SecretCandidate(
                    name=secret_name,
                    description=description,
                    source_file=rel,
                    line_number=0,
                    raw_value="",
                    confidence=confidence,
                    suggested_generator=generator,
                    suggested_target_kind="file",
                    tags=["llm-detected"],
                )
            )

        return candidates

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _merge_candidates(
        self,
        pattern_candidates: list[SecretCandidate],
        llm_candidates: list[SecretCandidate],
    ) -> list[SecretCandidate]:
        """Merge pattern and LLM candidate lists.

        When both lists contain a candidate with the same name, the entry
        with the higher confidence score is retained (with LLM description
        preferred when available).

        Args:
            pattern_candidates: Candidates from pattern-based detection.
            llm_candidates: Candidates from LLM analysis.

        Returns:
            Merged, deduplicated list.
        """
        by_name: dict[str, SecretCandidate] = {c.name: c for c in pattern_candidates}

        for llm_c in llm_candidates:
            if llm_c.name in by_name:
                existing = by_name[llm_c.name]
                # Boost confidence if both methods agree
                merged_confidence = min(1.0, max(existing.confidence, llm_c.confidence) + 0.05)
                by_name[llm_c.name] = existing.model_copy(
                    update={
                        "confidence": merged_confidence,
                        "description": llm_c.description or existing.description,
                    }
                )
            else:
                by_name[llm_c.name] = llm_c

        return list(by_name.values())

    def _deduplicate(self, candidates: list[SecretCandidate]) -> list[SecretCandidate]:
        """Remove duplicate candidates, keeping the highest-confidence entry.

        Args:
            candidates: Raw candidate list (may have duplicates).

        Returns:
            Deduplicated list sorted by descending confidence.
        """
        by_name: dict[str, SecretCandidate] = {}
        for c in candidates:
            if c.name not in by_name or c.confidence > by_name[c.name].confidence:
                by_name[c.name] = c
        return sorted(by_name.values(), key=lambda x: x.confidence, reverse=True)

    # ------------------------------------------------------------------
    # Output generation
    # ------------------------------------------------------------------

    def _write_secretfile(
        self, candidates: list[SecretCandidate], output_path: Path
    ) -> None:
        """Write the generated Secretfile to disk.

        Args:
            candidates: Candidate secrets to include.
            output_path: Destination path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self._build_secretfile_yaml(candidates)
        output_path.write_text(content, encoding="utf-8")

    def _build_secretfile_yaml(self, candidates: list[SecretCandidate]) -> str:
        """Render the Secretfile YAML string.

        Args:
            candidates: Candidate secrets.

        Returns:
            YAML string for the ``Secretfile.detect.yml``.
        """
        doc: dict[str, Any] = {
            "version": "1.0",
            "metadata": {
                "description": "Auto-generated by secretzero discover",
                "generated_by": "secretzero-discovery-agent",
            },
            "variables": {},
            "providers": {
                "local": {
                    "kind": "local",
                    "config": {},
                }
            },
            "secrets": [c.to_secretfile_entry() for c in candidates],
            "templates": {},
        }
        return yaml.dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False)
