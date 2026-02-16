"""Policy management and validation."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from secretzero.models import Secret, Secretfile
from secretzero.rotation import parse_rotation_period, should_rotate_secret


class PolicyKind(str, Enum):
    """Policy kind enum."""
    
    ROTATION = "rotation"
    COMPLIANCE = "compliance"
    ACCESS = "access"


class PolicySeverity(str, Enum):
    """Policy violation severity."""
    
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RotationPolicy(BaseModel):
    """Rotation policy definition."""
    
    kind: PolicyKind = PolicyKind.ROTATION
    name: str
    description: Optional[str] = None
    enabled: bool = True
    max_age: Optional[str] = None  # Maximum secret age (e.g., "90d")
    require_rotation_period: bool = False
    severity: PolicySeverity = PolicySeverity.WARNING


class CompliancePolicy(BaseModel):
    """Compliance policy definition."""
    
    kind: PolicyKind = PolicyKind.COMPLIANCE
    name: str
    description: Optional[str] = None
    enabled: bool = True
    standard: str  # e.g., "soc2", "iso27001"
    requirements: dict[str, Any] = Field(default_factory=dict)
    severity: PolicySeverity = PolicySeverity.ERROR


class AccessPolicy(BaseModel):
    """Access control policy definition."""
    
    kind: PolicyKind = PolicyKind.ACCESS
    name: str
    description: Optional[str] = None
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
    suggestion: Optional[str] = None


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
                kind = policy_config.get('kind')
                if kind == 'rotation':
                    policies[policy_name] = RotationPolicy(name=policy_name, **policy_config)
                elif kind == 'compliance':
                    policies[policy_name] = CompliancePolicy(name=policy_name, **policy_config)
                elif kind == 'access':
                    policies[policy_name] = AccessPolicy(name=policy_name, **policy_config)
        
        # Add predefined compliance policies if referenced in metadata
        if self.secretfile.metadata and self.secretfile.metadata.compliance:
            for standard in self.secretfile.metadata.compliance:
                if standard.lower() == 'soc2':
                    policies['soc2_rotation'] = RotationPolicy(
                        name='soc2_rotation',
                        description='SOC2 requires regular secret rotation',
                        max_age='90d',
                        require_rotation_period=True,
                        severity=PolicySeverity.WARNING,
                    )
                elif standard.lower() == 'iso27001':
                    policies['iso27001_rotation'] = RotationPolicy(
                        name='iso27001_rotation',
                        description='ISO27001 requires documented rotation policies',
                        require_rotation_period=True,
                        severity=PolicySeverity.WARNING,
                    )
        
        return policies
    
    def validate_secret(
        self,
        secret: Secret,
        lockfile_entry: Optional[Any] = None,
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
        
        return violations
    
    def _check_rotation_policy(
        self,
        secret: Secret,
        policy: RotationPolicy,
        lockfile_entry: Optional[Any],
    ) -> Optional[PolicyViolation]:
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
    ) -> Optional[PolicyViolation]:
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
                violations.append(PolicyViolation(
                    policy_name=policy.name,
                    severity=policy.severity,
                    secret_name=secret.name,
                    message=f"Target type '{target_kind}' is not allowed by policy",
                    suggestion=f"Remove target or update policy to allow '{target_kind}'",
                ))
            
            # Check allowed targets (if specified)
            if policy.allowed_targets and target_kind not in policy.allowed_targets:
                violations.append(PolicyViolation(
                    policy_name=policy.name,
                    severity=policy.severity,
                    secret_name=secret.name,
                    message=f"Target type '{target_kind}' is not in allowed list",
                    suggestion=f"Use one of: {', '.join(policy.allowed_targets)}",
                ))
        
        return violations
    
    def validate_all(self, lockfile: Optional[Any] = None) -> list[PolicyViolation]:
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
