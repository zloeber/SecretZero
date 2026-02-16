"""GitLab CI/CD variable targets."""

from typing import Any, Optional

from secretzero.targets.base import BaseTarget


class GitLabVariableTarget(BaseTarget):
    """Store secrets as GitLab CI/CD variables."""

    def __init__(self, provider: Any, config: Optional[dict[str, Any]] = None):
        """Initialize GitLab variable target.

        Args:
            provider: GitLab provider instance.
            config: Target configuration containing:
                - project: Project path (e.g., 'group/project' or project ID)
                - protected: Whether variable is protected (default: False)
                - masked: Whether variable is masked in logs (default: True)
                - environment_scope: Environment scope (default: '*' for all)
                - variable_type: Variable type ('env_var' or 'file', default: 'env_var')
        """
        super().__init__(config)
        self.provider = provider
        self.project = self.config.get("project")
        self.protected = self.config.get("protected", False)
        self.masked = self.config.get("masked", True)
        self.environment_scope = self.config.get("environment_scope", "*")
        self.variable_type = self.config.get("variable_type", "env_var")

        if not self.project:
            raise ValueError("GitLab variable target requires 'project' in config")

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret as GitLab CI/CD variable.

        Args:
            secret_name: Name of the variable.
            secret_value: Value of the variable.

        Returns:
            True if storage successful, False otherwise.
        """
        try:
            client = self.provider.auth.get_client()
            project = client.projects.get(self.project)

            # Check if variable already exists
            try:
                var = project.variables.get(secret_name)
                # Update existing variable
                var.value = secret_value
                var.protected = self.protected
                var.masked = self.masked
                var.environment_scope = self.environment_scope
                var.variable_type = self.variable_type
                var.save()
            except Exception:
                # Create new variable
                project.variables.create({
                    'key': secret_name,
                    'value': secret_value,
                    'protected': self.protected,
                    'masked': self.masked,
                    'environment_scope': self.environment_scope,
                    'variable_type': self.variable_type
                })
            
            return True
        except Exception as e:
            print(f"Failed to store variable in GitLab: {e}")
            return False

    def retrieve(self, secret_name: str) -> Optional[str]:
        """Retrieve variable from GitLab CI/CD.

        Args:
            secret_name: Name of the variable.

        Returns:
            Variable value if found, None otherwise.
        """
        try:
            client = self.provider.auth.get_client()
            project = client.projects.get(self.project)
            var = project.variables.get(secret_name)
            return var.value
        except Exception:
            return None


class GitLabGroupVariableTarget(BaseTarget):
    """Store secrets as GitLab group-level CI/CD variables."""

    def __init__(self, provider: Any, config: Optional[dict[str, Any]] = None):
        """Initialize GitLab group variable target.

        Args:
            provider: GitLab provider instance.
            config: Target configuration containing:
                - group: Group path or ID
                - protected: Whether variable is protected (default: False)
                - masked: Whether variable is masked in logs (default: True)
                - environment_scope: Environment scope (default: '*' for all)
                - variable_type: Variable type ('env_var' or 'file', default: 'env_var')
        """
        super().__init__(config)
        self.provider = provider
        self.group = self.config.get("group")
        self.protected = self.config.get("protected", False)
        self.masked = self.config.get("masked", True)
        self.environment_scope = self.config.get("environment_scope", "*")
        self.variable_type = self.config.get("variable_type", "env_var")

        if not self.group:
            raise ValueError("GitLab group variable target requires 'group' in config")

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret as GitLab group CI/CD variable.

        Args:
            secret_name: Name of the variable.
            secret_value: Value of the variable.

        Returns:
            True if storage successful, False otherwise.
        """
        try:
            client = self.provider.auth.get_client()
            group = client.groups.get(self.group)

            # Check if variable already exists
            try:
                var = group.variables.get(secret_name)
                # Update existing variable
                var.value = secret_value
                var.protected = self.protected
                var.masked = self.masked
                var.environment_scope = self.environment_scope
                var.variable_type = self.variable_type
                var.save()
            except Exception:
                # Create new variable
                group.variables.create({
                    'key': secret_name,
                    'value': secret_value,
                    'protected': self.protected,
                    'masked': self.masked,
                    'environment_scope': self.environment_scope,
                    'variable_type': self.variable_type
                })
            
            return True
        except Exception as e:
            print(f"Failed to store variable in GitLab group: {e}")
            return False

    def retrieve(self, secret_name: str) -> Optional[str]:
        """Retrieve variable from GitLab group CI/CD.

        Args:
            secret_name: Name of the variable.

        Returns:
            Variable value if found, None otherwise.
        """
        try:
            client = self.provider.auth.get_client()
            group = client.groups.get(self.group)
            var = group.variables.get(secret_name)
            return var.value
        except Exception:
            return None
