"""Tests for policy enforcement."""

import pytest
from datetime import UTC, datetime, timedelta

from secretzero.models import Metadata, Secret, Secretfile, TargetConfig
from secretzero.policy import (
    PolicyEngine,
    PolicyKind,
    PolicySeverity,
    RotationPolicy,
    CompliancePolicy,
    AccessPolicy,
)
from secretzero.lockfile import SecretLockEntry


class TestRotationPolicy:
    """Tests for rotation policy enforcement."""
    
    def test_require_rotation_period(self):
        """Test that rotation period can be required."""
        secretfile = Secretfile(
            version="1.0",
            policies={
                "test_policy": {
                    "kind": "rotation",
                    "require_rotation_period": True,
                }
            },
            secrets=[
                Secret(name="test", kind="random_password", config={}),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        assert len(violations) == 1
        assert violations[0].secret_name == "test"
        assert "rotation_period" in violations[0].message
    
    def test_max_age_policy(self):
        """Test maximum rotation age enforcement."""
        secretfile = Secretfile(
            version="1.0",
            policies={
                "max_age": {
                    "kind": "rotation",
                    "max_age": "90d",
                }
            },
            secrets=[
                Secret(
                    name="test",
                    kind="random_password",
                    rotation_period="180d",
                    config={},
                ),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        assert len(violations) == 1
        assert "exceeds max allowed" in violations[0].message
    
    def test_rotation_overdue(self):
        """Test detection of overdue rotation."""
        # Create secret that's overdue
        created_at = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        lockfile_entry = SecretLockEntry(
            hash="abc123",
            created_at=created_at,
            updated_at=created_at,
        )
        
        secretfile = Secretfile(
            version="1.0",
            policies={
                "rotation": {
                    "kind": "rotation",
                    "max_age": "90d",
                }
            },
            secrets=[
                Secret(
                    name="test",
                    kind="random_password",
                    rotation_period="90d",
                    config={},
                ),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        
        # Mock lockfile
        class MockLockfile:
            def get_secret_info(self, name):
                return lockfile_entry
        
        violations = engine.validate_all(MockLockfile())
        
        assert len(violations) == 1
        assert "overdue" in violations[0].message.lower()


class TestCompliancePolicy:
    """Tests for compliance policy enforcement."""
    
    def test_soc2_rotation_policy(self):
        """Test SOC2 compliance requires rotation policies."""
        secretfile = Secretfile(
            version="1.0",
            metadata=Metadata(compliance=["soc2"]),
            secrets=[
                Secret(name="test", kind="random_password", config={}),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        # Should have SOC2 rotation policy violation
        assert len(violations) == 1
        assert violations[0].policy_name == "soc2_rotation"
    
    def test_iso27001_rotation_policy(self):
        """Test ISO27001 compliance requires rotation policies."""
        secretfile = Secretfile(
            version="1.0",
            metadata=Metadata(compliance=["iso27001"]),
            secrets=[
                Secret(name="test", kind="random_password", config={}),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        # Should have ISO27001 rotation policy violation
        assert len(violations) == 1
        assert violations[0].policy_name == "iso27001_rotation"
    
    def test_multiple_compliance_standards(self):
        """Test multiple compliance standards."""
        secretfile = Secretfile(
            version="1.0",
            metadata=Metadata(compliance=["soc2", "iso27001"]),
            secrets=[
                Secret(name="test", kind="random_password", config={}),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        # Should have violations for both standards
        assert len(violations) == 2
        policy_names = {v.policy_name for v in violations}
        assert "soc2_rotation" in policy_names
        assert "iso27001_rotation" in policy_names


class TestAccessPolicy:
    """Tests for access control policy enforcement."""
    
    def test_denied_targets(self):
        """Test that denied targets are caught."""
        secretfile = Secretfile(
            version="1.0",
            policies={
                "access": {
                    "kind": "access",
                    "denied_targets": ["file"],
                }
            },
            secrets=[
                Secret(
                    name="test",
                    kind="random_password",
                    config={},
                    targets=[
                        TargetConfig(
                            provider="local",
                            kind="file",
                            config={"path": ".env"},
                        ),
                    ],
                ),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        assert len(violations) == 1
        assert "not allowed" in violations[0].message
    
    def test_allowed_targets(self):
        """Test that only allowed targets are permitted."""
        secretfile = Secretfile(
            version="1.0",
            policies={
                "access": {
                    "kind": "access",
                    "allowed_targets": ["ssm_parameter"],
                }
            },
            secrets=[
                Secret(
                    name="test",
                    kind="random_password",
                    config={},
                    targets=[
                        TargetConfig(
                            provider="local",
                            kind="file",
                            config={"path": ".env"},
                        ),
                    ],
                ),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        assert len(violations) == 1
        assert "not in allowed list" in violations[0].message
    
    def test_multiple_targets(self):
        """Test policy enforcement across multiple targets."""
        secretfile = Secretfile(
            version="1.0",
            policies={
                "access": {
                    "kind": "access",
                    "allowed_targets": ["ssm_parameter"],
                }
            },
            secrets=[
                Secret(
                    name="test",
                    kind="random_password",
                    config={},
                    targets=[
                        TargetConfig(
                            provider="local",
                            kind="file",
                            config={"path": ".env"},
                        ),
                        TargetConfig(
                            provider="aws",
                            kind="ssm_parameter",
                            config={"name": "/test"},
                        ),
                    ],
                ),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        # Should have one violation for file target
        assert len(violations) == 1
        assert "file" in violations[0].message


class TestPolicyEngine:
    """Tests for PolicyEngine overall functionality."""
    
    def test_disabled_policies_ignored(self):
        """Test that disabled policies are not enforced."""
        secretfile = Secretfile(
            version="1.0",
            policies={
                "test_policy": {
                    "kind": "rotation",
                    "require_rotation_period": True,
                    "enabled": False,
                }
            },
            secrets=[
                Secret(name="test", kind="random_password", config={}),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        assert len(violations) == 0
    
    def test_multiple_violations(self):
        """Test that multiple violations are detected."""
        secretfile = Secretfile(
            version="1.0",
            metadata=Metadata(compliance=["soc2"]),
            policies={
                "access": {
                    "kind": "access",
                    "denied_targets": ["file"],
                }
            },
            secrets=[
                Secret(
                    name="test",
                    kind="random_password",
                    config={},
                    targets=[
                        TargetConfig(
                            provider="local",
                            kind="file",
                            config={"path": ".env"},
                        ),
                    ],
                ),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        # Should have violations for both rotation and access
        assert len(violations) == 2
    
    def test_no_policies(self):
        """Test that no policies means no violations."""
        secretfile = Secretfile(
            version="1.0",
            secrets=[
                Secret(name="test", kind="random_password", config={}),
            ],
        )
        
        engine = PolicyEngine(secretfile)
        violations = engine.validate_all()
        
        assert len(violations) == 0
