"""Drift detection for secrets."""

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from secretzero.config import ConfigLoader
from secretzero.lockfile import Lockfile
from secretzero.models import Secret, TargetConfig


class DriftStatus(BaseModel):
    """Drift detection status."""
    
    secret_name: str
    has_drift: bool
    message: str
    details: dict[str, Any] = {}


class DriftDetector:
    """Detect drift between lockfile and actual targets."""
    
    def __init__(self, secretfile_path: Path, lockfile_path: Path):
        """Initialize drift detector.
        
        Args:
            secretfile_path: Path to Secretfile
            lockfile_path: Path to lockfile
        """
        self.secretfile_path = secretfile_path
        self.lockfile_path = lockfile_path
        
        loader = ConfigLoader()
        self.config = loader.load_file(secretfile_path)
        self.lockfile = Lockfile.load(lockfile_path)
    
    def check_drift(self, secret_name: Optional[str] = None) -> list[DriftStatus]:
        """Check for drift in secrets.
        
        Args:
            secret_name: Optional specific secret to check
            
        Returns:
            List of drift status results
        """
        results = []
        
        # Filter secrets to check
        secrets_to_check = self.config.secrets
        if secret_name:
            secrets_to_check = [s for s in self.config.secrets if s.name == secret_name]
        
        for secret in secrets_to_check:
            result = self._check_secret_drift(secret)
            results.append(result)
        
        return results
    
    def _check_secret_drift(self, secret: Secret) -> DriftStatus:
        """Check drift for a single secret.
        
        Args:
            secret: Secret to check
            
        Returns:
            Drift status
        """
        # Check if secret exists in lockfile
        if not self.lockfile.has_secret(secret.name):
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Secret not found in lockfile",
                details={"reason": "never_generated"},
            )
        
        lockfile_entry = self.lockfile.get_secret_info(secret.name)
        if not lockfile_entry:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Secret entry corrupted in lockfile",
                details={"reason": "corrupted"},
            )
        
        # Check if we can verify drift against targets
        # For now, we'll focus on file targets which we can read
        file_targets = self._get_file_targets(secret)
        
        if not file_targets:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=False,
                message="No verifiable targets (file targets only)",
                details={
                    "reason": "no_file_targets",
                    "lockfile_hash": lockfile_entry.hash,
                },
            )
        
        # Check file targets for drift
        drift_detected = False
        drift_details = {}
        
        for target in file_targets:
            target_path = Path(target.config.get('path', ''))
            if not target_path.exists():
                drift_detected = True
                drift_details[str(target_path)] = "file_missing"
                continue
            
            # For now, we mark as "needs_verification" since we can't read
            # the actual secret value from the file without knowing the format
            # and key name
            drift_details[str(target_path)] = "exists"
        
        if drift_detected:
            return DriftStatus(
                secret_name=secret.name,
                has_drift=True,
                message="Target files missing",
                details=drift_details,
            )
        
        return DriftStatus(
            secret_name=secret.name,
            has_drift=False,
            message="No drift detected in file targets",
            details=drift_details,
        )
    
    def _get_file_targets(self, secret: Secret) -> list[TargetConfig]:
        """Get file targets for a secret.
        
        Args:
            secret: Secret to get targets for
            
        Returns:
            List of file target configs
        """
        return [t for t in secret.targets if t.kind == "file"]
    
    def auto_remediate(self, secret_name: Optional[str] = None) -> dict[str, Any]:
        """Auto-remediate drift by regenerating secrets.
        
        Args:
            secret_name: Optional specific secret to remediate
            
        Returns:
            Remediation results
        """
        # Check for drift first
        drift_results = self.check_drift(secret_name)
        
        secrets_with_drift = [r for r in drift_results if r.has_drift]
        
        if not secrets_with_drift:
            return {
                "remediated": 0,
                "message": "No drift detected",
            }
        
        # For auto-remediation, we'd need to call the sync engine
        # This is a placeholder for the actual implementation
        return {
            "remediated": 0,
            "message": "Auto-remediation requires running 'secretzero sync --force'",
            "secrets_with_drift": [r.secret_name for r in secrets_with_drift],
        }
