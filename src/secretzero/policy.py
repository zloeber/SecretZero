"""Policy management and validation."""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterator
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from secretzero.models import Secret, Secretfile, TargetConfig
from secretzero.rotation import parse_rotation_period, should_rotate_secret


class PolicyKind(str, Enum):
    """Policy kind enum."""

    ROTATION = "rotation"
    COMPLIANCE = "compliance"
    ACCESS = "access"
    PROVIDER_IDENTITY = "provider_identity"


class PolicySeverity(str, Enum):
    """Policy violation severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ProviderIdentityRule(BaseModel):
    """Single rule matched against :meth:`~secretzero.providers.base.BaseProvider.get_actor_info`."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(
        ...,
        description="Dotted path into the actor dict (e.g. `account`, `arn`, `scopes`).",
    )
    glob: str | None = Field(
        default=None,
        description="``fnmatchcase`` pattern applied to the string form of a scalar field value.",
    )
    regex: str | None = Field(
        default=None,
        description="``re.fullmatch`` pattern for a scalar field (mutually exclusive with glob).",
    )
    any_glob: list[str] | None = Field(
        default=None,
        description=(
            "For list-valued fields: true if at least one element matches at least one pattern "
            "(``fnmatchcase``)."
        ),
    )
    all_glob: list[str] | None = Field(
        default=None,
        description=(
            "For list-valued fields: true if every element matches at least one of these patterns."
        ),
    )

    @model_validator(mode="after")
    def _exactly_one_matcher(self) -> ProviderIdentityRule:
        flags = [
            self.glob is not None,
            self.regex is not None,
            self.any_glob is not None,
            self.all_glob is not None,
        ]
        if sum(1 for f in flags if f) != 1:
            raise ValueError(
                "Each provider_identity rule must set exactly one of: glob, regex, any_glob, all_glob"
            )
        if self.any_glob is not None and len(self.any_glob) == 0:
            raise ValueError("any_glob must be non-empty when set")
        if self.all_glob is not None and len(self.all_glob) == 0:
            raise ValueError("all_glob must be non-empty when set")
        return self


class ProviderIdentityPolicy(BaseModel):
    """Require provider authentication identity to match before sync proceeds."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["provider_identity"] = "provider_identity"
    name: str
    description: str | None = None
    enabled: bool = True
    severity: PolicySeverity = PolicySeverity.ERROR
    providers: list[str] = Field(
        ...,
        min_length=1,
        description="Provider instance aliases (YAML keys under `providers:`) this policy applies to.",
    )
    match: Literal["all", "any"] = Field(
        default="all",
        description="Whether every rule must pass (`all`) or at least one (`any`).",
    )
    rules: list[ProviderIdentityRule] = Field(
        ...,
        min_length=1,
        description="Rules evaluated against `get_actor_info()` for each listed provider.",
    )


class RotationPolicy(BaseModel):
    """Rotation policy definition."""

    kind: PolicyKind = PolicyKind.ROTATION
    name: str
    description: str | None = None
    enabled: bool = True
    max_age: str | None = None  # Maximum secret age (e.g., "90d")
    require_rotation_period: bool = False
    severity: PolicySeverity = PolicySeverity.WARNING


class CompliancePolicy(BaseModel):
    """Compliance policy definition."""

    kind: PolicyKind = PolicyKind.COMPLIANCE
    name: str
    description: str | None = None
    enabled: bool = True
    standard: str  # e.g., "soc2", "iso27001"
    requirements: dict[str, Any] = Field(default_factory=dict)
    severity: PolicySeverity = PolicySeverity.ERROR


class AccessPolicy(BaseModel):
    """Access control policy definition."""

    kind: PolicyKind = PolicyKind.ACCESS
    name: str
    description: str | None = None
    enabled: bool = True
    allowed_targets: list[str] = Field(default_factory=list)
    denied_targets: list[str] = Field(default_factory=list)
    severity: PolicySeverity = PolicySeverity.ERROR


class PolicyViolation(BaseModel):
    """Policy violation result."""

    policy_name: str
    severity: PolicySeverity
    secret_name: str
    message: str
    suggestion: str | None = None


class PolicyEngine:
    """Policy validation engine."""

    def __init__(self, secretfile: Secretfile):
        """Initialize policy engine.

        Args:
            secretfile: Secretfile configuration
        """
        self.secretfile = secretfile
        self.policies = self._load_policies()

    def _load_policies(self) -> dict[str, Any]:
        """Load policies from secretfile."""
        policies = {}

        # Load user-defined policies
        for policy_name, policy_config in self.secretfile.policies.items():
            if isinstance(policy_config, dict):
                kind = policy_config.get("kind")
                if kind == "rotation":
                    policies[policy_name] = RotationPolicy(name=policy_name, **policy_config)
                elif kind == "compliance":
                    policies[policy_name] = CompliancePolicy(name=policy_name, **policy_config)
                elif kind == "access":
                    policies[policy_name] = AccessPolicy(name=policy_name, **policy_config)
                elif kind == "provider_identity":
                    policies[policy_name] = ProviderIdentityPolicy.model_validate(
                        {"name": policy_name, **policy_config}
                    )

        # Add predefined compliance policies if referenced in metadata
        if self.secretfile.metadata and self.secretfile.metadata.compliance:
            for standard in self.secretfile.metadata.compliance:
                if standard.lower() == "soc2":
                    policies["soc2_rotation"] = RotationPolicy(
                        name="soc2_rotation",
                        description="SOC2 requires regular secret rotation",
                        max_age="90d",
                        require_rotation_period=True,
                        severity=PolicySeverity.WARNING,
                    )
                elif standard.lower() == "iso27001":
                    policies["iso27001_rotation"] = RotationPolicy(
                        name="iso27001_rotation",
                        description="ISO27001 requires documented rotation policies",
                        require_rotation_period=True,
                        severity=PolicySeverity.WARNING,
                    )

        return policies

    def validate_secret(
        self,
        secret: Secret,
        lockfile_entry: Any | None = None,
    ) -> list[PolicyViolation]:
        """Validate a secret against all policies.

        Args:
            secret: Secret to validate
            lockfile_entry: Optional lockfile entry for the secret

        Returns:
            List of policy violations
        """
        violations = []

        for policy_name, policy in self.policies.items():
            if not policy.enabled:
                continue

            if isinstance(policy, RotationPolicy):
                violation = self._check_rotation_policy(secret, policy, lockfile_entry)
                if violation:
                    violations.append(violation)
            elif isinstance(policy, CompliancePolicy):
                violation = self._check_compliance_policy(secret, policy)
                if violation:
                    violations.append(violation)
            elif isinstance(policy, AccessPolicy):
                violations.extend(self._check_access_policy(secret, policy))
            elif isinstance(policy, ProviderIdentityPolicy):
                continue

        return violations

    def _check_rotation_policy(
        self,
        secret: Secret,
        policy: RotationPolicy,
        lockfile_entry: Any | None,
    ) -> PolicyViolation | None:
        """Check rotation policy for a secret."""
        # Check if rotation period is required
        if policy.require_rotation_period and not secret.rotation_period:
            return PolicyViolation(
                policy_name=policy.name,
                severity=policy.severity,
                secret_name=secret.name,
                message="Secret missing required rotation_period",
                suggestion=f"Add rotation_period to secret (e.g., rotation_period: '{policy.max_age or '90d'}')",
            )

        # Check if secret exceeds max age
        if policy.max_age and secret.rotation_period:
            max_period = parse_rotation_period(policy.max_age)
            secret_period = parse_rotation_period(secret.rotation_period)

            if max_period and secret_period and secret_period > max_period:
                return PolicyViolation(
                    policy_name=policy.name,
                    severity=policy.severity,
                    secret_name=secret.name,
                    message=f"Rotation period {secret.rotation_period} exceeds max allowed {policy.max_age}",
                    suggestion=f"Reduce rotation_period to {policy.max_age} or less",
                )

        # Check if secret is overdue for rotation
        if lockfile_entry and secret.rotation_period:
            should_rotate, reason = should_rotate_secret(
                secret.rotation_period,
                lockfile_entry.last_rotated,
                lockfile_entry.created_at,
            )
            if should_rotate and "overdue" in reason.lower():
                return PolicyViolation(
                    policy_name=policy.name,
                    severity=policy.severity,
                    secret_name=secret.name,
                    message=reason,
                    suggestion="Run 'secretzero rotate' to rotate overdue secrets",
                )

        return None

    def _check_compliance_policy(
        self,
        secret: Secret,
        policy: CompliancePolicy,
    ) -> PolicyViolation | None:
        """Check compliance policy for a secret."""
        # Generic compliance checks could be added here
        # For now, compliance is mainly handled via rotation policies
        return None

    def _check_access_policy(
        self,
        secret: Secret,
        policy: AccessPolicy,
    ) -> list[PolicyViolation]:
        """Check access policy for a secret."""
        violations = []

        for target in secret.targets:
            target_kind = str(target.kind)

            # Check denied targets
            if policy.denied_targets and target_kind in policy.denied_targets:
                violations.append(
                    PolicyViolation(
                        policy_name=policy.name,
                        severity=policy.severity,
                        secret_name=secret.name,
                        message=f"Target type '{target_kind}' is not allowed by policy",
                        suggestion=f"Remove target or update policy to allow '{target_kind}'",
                    )
                )

            # Check allowed targets (if specified)
            if policy.allowed_targets and target_kind not in policy.allowed_targets:
                violations.append(
                    PolicyViolation(
                        policy_name=policy.name,
                        severity=policy.severity,
                        secret_name=secret.name,
                        message=f"Target type '{target_kind}' is not in allowed list",
                        suggestion=f"Use one of: {', '.join(policy.allowed_targets)}",
                    )
                )

        return violations

    def validate_all(self, lockfile: Any | None = None) -> list[PolicyViolation]:
        """Validate all secrets against policies.

        Args:
            lockfile: Optional lockfile for rotation checks

        Returns:
            List of all policy violations
        """
        violations = []

        for secret in self.secretfile.secrets:
            lockfile_entry = None
            if lockfile:
                lockfile_entry = lockfile.get_secret_info(secret.name)

            violations.extend(self.validate_secret(secret, lockfile_entry))

        return violations


def actor_field_value(actor: dict[str, Any], field_path: str) -> Any:
    """Return a dotted-path value from an actor dict, or None if missing."""
    cur: Any = actor
    for part in field_path.split("."):
        if part == "":
            continue
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def evaluate_identity_rule(rule: ProviderIdentityRule, actor: dict[str, Any]) -> tuple[bool, str]:
    """Return (success, failure_reason)."""
    raw = actor_field_value(actor, rule.field)
    if rule.glob is not None:
        if raw is None:
            return False, f"missing field {rule.field!r}"
        s = str(raw)
        if fnmatch.fnmatchcase(s, rule.glob):
            return True, ""
        return False, f"field {rule.field!r} is {s!r}, expected glob {rule.glob!r}"
    if rule.regex is not None:
        if raw is None:
            return False, f"missing field {rule.field!r}"
        s = str(raw)
        try:
            if re.fullmatch(rule.regex, s):
                return True, ""
        except re.error as exc:
            return False, f"invalid regex {rule.regex!r}: {exc}"
        return False, f"field {rule.field!r} is {s!r}, expected regex {rule.regex!r}"
    patterns = rule.any_glob if rule.any_glob is not None else rule.all_glob
    assert patterns is not None
    if raw is None:
        items: list[str] = []
    elif isinstance(raw, list):
        items = [str(x) for x in raw]
    else:
        items = [str(raw)]
    if rule.any_glob is not None:
        matched = any(fnmatch.fnmatchcase(item, pat) for item in items for pat in patterns)
        if matched:
            return True, ""
        return (
            False,
            f"field {rule.field!r} values {items!r} do not match any pattern in {patterns!r}",
        )
    for item in items:
        if not any(fnmatch.fnmatchcase(item, pat) for pat in patterns):
            return (
                False,
                f"field {rule.field!r} value {item!r} matches no pattern in {patterns!r}",
            )
    return True, ""


def evaluate_provider_identity_policy(
    policy: ProviderIdentityPolicy, actor: dict[str, Any]
) -> tuple[bool, str]:
    """Return (success, failure_reason)."""
    results = [evaluate_identity_rule(r, actor) for r in policy.rules]
    if policy.match == "all":
        for ok, msg in results:
            if not ok:
                return False, msg
        return True, ""
    for ok, msg in results:
        if ok:
            return True, ""
    return False, "; ".join(msg for ok, msg in results if msg)


def enforce_provider_identity_policy(
    policy_name: str,
    policy: ProviderIdentityPolicy,
    provider_alias: str,
    actor: dict[str, Any],
) -> None:
    """Raise RuntimeError when the actor does not satisfy the policy."""
    ok, msg = evaluate_provider_identity_policy(policy, actor)
    if ok:
        return
    raise RuntimeError(
        f"Provider identity policy {policy_name!r} failed for provider {provider_alias!r}: {msg}"
    )


def iter_targets_for_secret(secret: Secret, secretfile: Secretfile) -> Iterator[TargetConfig]:
    """Yield all TargetConfig rows that participate in syncing this secret."""
    if secret.kind.startswith("templates."):
        template_name = secret.kind.replace("templates.", "")
        template = secretfile.templates.get(template_name)
        if template:
            for field in template.fields.values():
                yield from field.targets
            yield from template.targets
        return
    yield from secret.targets


def _providers_and_target_identity_refs(
    secretfile: Secretfile, secrets: list[Secret]
) -> tuple[set[str], set[str]]:
    providers_used: set[str] = set()
    policy_names_on_targets: set[str] = set()
    for secret in secrets:
        for tc in iter_targets_for_secret(secret, secretfile):
            providers_used.add(tc.provider)
            policy_names_on_targets.update(tc.identity_policies)
    return providers_used, policy_names_on_targets


def load_provider_identity_policies(secretfile: Secretfile) -> dict[str, ProviderIdentityPolicy]:
    """Parse and validate all ``kind: provider_identity`` policies."""
    out: dict[str, ProviderIdentityPolicy] = {}
    for policy_name, policy_config in secretfile.policies.items():
        if isinstance(policy_config, dict) and policy_config.get("kind") == "provider_identity":
            out[policy_name] = ProviderIdentityPolicy.model_validate(
                {"name": policy_name, **policy_config}
            )
    return out


def collect_applicable_provider_identity_policies(
    secretfile: Secretfile,
    secrets_in_scope: list[Secret],
) -> list[tuple[str, ProviderIdentityPolicy]]:
    """Policies to enforce for this sync scope (provider overlap + target identity_policies)."""
    loaded = load_provider_identity_policies(secretfile)
    if not loaded:
        return []
    providers_used, names_on_targets = _providers_and_target_identity_refs(
        secretfile, secrets_in_scope
    )
    applicable_names: set[str] = set()
    for name, pol in loaded.items():
        if set(pol.providers) & providers_used:
            applicable_names.add(name)
    applicable_names |= {n for n in names_on_targets if n in loaded}
    return [(n, loaded[n]) for n in sorted(applicable_names)]


def validate_secretfile_policy_shapes(secretfile: Secretfile) -> None:
    """Validate provider_identity policy documents and target references.

    Raises:
        ValueError: On invalid policy shape or broken ``identity_policies`` references.
    """
    load_provider_identity_policies(secretfile)
    for secret in secretfile.secrets:
        for tc in iter_targets_for_secret(secret, secretfile):
            for ref in tc.identity_policies:
                if ref not in secretfile.policies:
                    raise ValueError(
                        f"Unknown identity_policies reference {ref!r} "
                        f"(secret {secret.name!r} target {tc.provider}/{tc.kind})."
                    )
                raw = secretfile.policies[ref]
                if not isinstance(raw, dict) or raw.get("kind") != "provider_identity":
                    raise ValueError(
                        f"identity_policies entry {ref!r} must have kind: provider_identity "
                        f"(secret {secret.name!r})."
                    )
