"""Tests for CI/CD provider implementations (GitHub, GitLab, Jenkins)."""

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestGitHubProvider:
    """Tests for GitHub provider."""

    def test_import_github_provider(self):
        """Test importing GitHub provider."""
        try:
            from secretzero.providers.github import GitHubProvider, GitHubAuth
            assert GitHubProvider is not None
            assert GitHubAuth is not None
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_auth_initialization(self):
        """Test GitHub auth initialization."""
        try:
            from secretzero.providers.github import GitHubAuth
            auth = GitHubAuth({"token": "test-token", "api_url": "https://api.github.com"})
            assert auth.config["token"] == "test-token"
            assert auth.config["api_url"] == "https://api.github.com"
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_auth_authenticate_success(self):
        """Test GitHub authentication success."""
        try:
            from secretzero.providers.github import GitHubAuth
            
            # Mock GitHub client
            with patch("github.Github") as mock_github:
                mock_client = Mock()
                mock_user = Mock()
                mock_user.login = "testuser"
                mock_client.get_user.return_value = mock_user
                mock_github.return_value = mock_client
                
                auth = GitHubAuth({"token": "test-token"})
                result = auth.authenticate()
                
                assert result is True
                assert auth.is_authenticated() is True
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_auth_authenticate_failure(self):
        """Test GitHub authentication failure."""
        try:
            from secretzero.providers.github import GitHubAuth
            
            # Test without token
            auth = GitHubAuth({})
            result = auth.authenticate()
            assert result is False
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_provider_initialization(self):
        """Test GitHub provider initialization."""
        try:
            from secretzero.providers.github import GitHubProvider
            
            config = {
                "kind": "github",
                "auth": {"token": "test-token"}
            }
            provider = GitHubProvider(name="github", config=config)
            
            assert provider.name == "github"
            assert provider.config == config
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_provider_test_connection_success(self):
        """Test GitHub connection test success."""
        try:
            from secretzero.providers.github import GitHubProvider
            
            with patch("github.Github") as mock_github:
                mock_client = Mock()
                mock_user = Mock()
                mock_user.login = "testuser"
                mock_client.get_user.return_value = mock_user
                mock_github.return_value = mock_client
                
                config = {"auth": {"token": "test-token"}}
                provider = GitHubProvider(name="github", config=config)
                
                success, message = provider.test_connection()
                assert success is True
                assert "testuser" in message
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_provider_test_connection_failure(self):
        """Test GitHub connection test failure."""
        try:
            from secretzero.providers.github import GitHubProvider
            
            config = {"auth": {}}  # No token
            provider = GitHubProvider(name="github", config=config)
            
            success, message = provider.test_connection()
            assert success is False
            assert "Authentication failed" in message
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_provider_supported_targets(self):
        """Test GitHub provider supported targets."""
        try:
            from secretzero.providers.github import GitHubProvider
            
            provider = GitHubProvider(name="github", config={})
            targets = provider.get_supported_targets()
            
            assert "github_secret" in targets
            assert "github_environment_secret" in targets
        except ImportError:
            pytest.skip("PyGithub not installed")


class TestGitLabProvider:
    """Tests for GitLab provider."""

    def test_import_gitlab_provider(self):
        """Test importing GitLab provider."""
        try:
            from secretzero.providers.gitlab import GitLabProvider, GitLabAuth
            assert GitLabProvider is not None
            assert GitLabAuth is not None
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_auth_initialization(self):
        """Test GitLab auth initialization."""
        try:
            from secretzero.providers.gitlab import GitLabAuth
            auth = GitLabAuth({"token": "test-token", "url": "https://gitlab.com"})
            assert auth.config["token"] == "test-token"
            assert auth.config["url"] == "https://gitlab.com"
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_auth_authenticate_success(self):
        """Test GitLab authentication success."""
        try:
            from secretzero.providers.gitlab import GitLabAuth
            
            # Mock GitLab client
            with patch("gitlab.Gitlab") as mock_gitlab:
                mock_client = Mock()
                mock_client.auth.return_value = None  # Successful auth returns None
                mock_gitlab.return_value = mock_client
                
                auth = GitLabAuth({"token": "test-token"})
                result = auth.authenticate()
                
                assert result is True
                assert auth.is_authenticated() is True
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_auth_authenticate_failure(self):
        """Test GitLab authentication failure."""
        try:
            from secretzero.providers.gitlab import GitLabAuth
            
            # Test without token
            auth = GitLabAuth({})
            result = auth.authenticate()
            assert result is False
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_provider_initialization(self):
        """Test GitLab provider initialization."""
        try:
            from secretzero.providers.gitlab import GitLabProvider
            
            config = {
                "kind": "gitlab",
                "auth": {"token": "test-token"}
            }
            provider = GitLabProvider(name="gitlab", config=config)
            
            assert provider.name == "gitlab"
            assert provider.config == config
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_provider_test_connection_success(self):
        """Test GitLab connection test success."""
        try:
            from secretzero.providers.gitlab import GitLabProvider
            
            with patch("gitlab.Gitlab") as mock_gitlab:
                mock_client = Mock()
                mock_client.auth.return_value = None
                mock_user = Mock()
                mock_user.username = "testuser"
                mock_client.user = mock_user
                mock_gitlab.return_value = mock_client
                
                config = {"auth": {"token": "test-token"}}
                provider = GitLabProvider(name="gitlab", config=config)
                
                success, message = provider.test_connection()
                assert success is True
                assert "testuser" in message
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_provider_test_connection_failure(self):
        """Test GitLab connection test failure."""
        try:
            from secretzero.providers.gitlab import GitLabProvider
            
            config = {"auth": {}}  # No token
            provider = GitLabProvider(name="gitlab", config=config)
            
            success, message = provider.test_connection()
            assert success is False
            assert "Authentication failed" in message
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_provider_supported_targets(self):
        """Test GitLab provider supported targets."""
        try:
            from secretzero.providers.gitlab import GitLabProvider
            
            provider = GitLabProvider(name="gitlab", config={})
            targets = provider.get_supported_targets()
            
            assert "gitlab_variable" in targets
            assert "gitlab_group_variable" in targets
        except ImportError:
            pytest.skip("python-gitlab not installed")


class TestJenkinsProvider:
    """Tests for Jenkins provider."""

    def test_import_jenkins_provider(self):
        """Test importing Jenkins provider."""
        try:
            from secretzero.providers.jenkins import JenkinsProvider, JenkinsAuth
            assert JenkinsProvider is not None
            assert JenkinsAuth is not None
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_auth_initialization(self):
        """Test Jenkins auth initialization."""
        try:
            from secretzero.providers.jenkins import JenkinsAuth
            auth = JenkinsAuth({
                "url": "https://jenkins.example.com",
                "username": "admin",
                "token": "test-token"
            })
            assert auth.config["url"] == "https://jenkins.example.com"
            assert auth.config["username"] == "admin"
            assert auth.config["token"] == "test-token"
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_auth_authenticate_success(self):
        """Test Jenkins authentication success."""
        try:
            from secretzero.providers.jenkins import JenkinsAuth
            
            # Mock Jenkins client
            with patch("jenkins.Jenkins") as mock_jenkins:
                mock_client = Mock()
                mock_client.get_version.return_value = "2.0.0"
                mock_jenkins.return_value = mock_client
                
                auth = JenkinsAuth({
                    "url": "https://jenkins.example.com",
                    "username": "admin",
                    "token": "test-token"
                })
                result = auth.authenticate()
                
                assert result is True
                assert auth.is_authenticated() is True
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_auth_authenticate_failure(self):
        """Test Jenkins authentication failure."""
        try:
            from secretzero.providers.jenkins import JenkinsAuth
            
            # Test without required fields
            auth = JenkinsAuth({"url": "https://jenkins.example.com"})
            result = auth.authenticate()
            assert result is False
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_provider_initialization(self):
        """Test Jenkins provider initialization."""
        try:
            from secretzero.providers.jenkins import JenkinsProvider
            
            config = {
                "kind": "jenkins",
                "auth": {
                    "url": "https://jenkins.example.com",
                    "username": "admin",
                    "token": "test-token"
                }
            }
            provider = JenkinsProvider(name="jenkins", config=config)
            
            assert provider.name == "jenkins"
            assert provider.config == config
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_provider_test_connection_success(self):
        """Test Jenkins connection test success."""
        try:
            from secretzero.providers.jenkins import JenkinsProvider
            
            with patch("jenkins.Jenkins") as mock_jenkins:
                mock_client = Mock()
                mock_client.get_version.return_value = "2.0.0"
                mock_jenkins.return_value = mock_client
                
                config = {
                    "auth": {
                        "url": "https://jenkins.example.com",
                        "username": "admin",
                        "token": "test-token"
                    }
                }
                provider = JenkinsProvider(name="jenkins", config=config)
                
                success, message = provider.test_connection()
                assert success is True
                assert "2.0.0" in message
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_provider_test_connection_failure(self):
        """Test Jenkins connection test failure."""
        try:
            from secretzero.providers.jenkins import JenkinsProvider
            
            config = {"auth": {"url": "https://jenkins.example.com"}}  # Missing credentials
            provider = JenkinsProvider(name="jenkins", config=config)
            
            success, message = provider.test_connection()
            assert success is False
            assert "Authentication failed" in message
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_provider_supported_targets(self):
        """Test Jenkins provider supported targets."""
        try:
            from secretzero.providers.jenkins import JenkinsProvider
            
            provider = JenkinsProvider(name="jenkins", config={})
            targets = provider.get_supported_targets()
            
            assert "jenkins_credential" in targets
        except ImportError:
            pytest.skip("python-jenkins not installed")


class TestGitHubTarget:
    """Tests for GitHub secret target."""

    def test_import_github_target(self):
        """Test importing GitHub target."""
        try:
            from secretzero.targets.github import GitHubSecretTarget
            assert GitHubSecretTarget is not None
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_target_initialization(self):
        """Test GitHub target initialization."""
        try:
            from secretzero.targets.github import GitHubSecretTarget
            
            provider = Mock()
            config = {"owner": "testorg", "repo": "testrepo"}
            target = GitHubSecretTarget(provider, config)
            
            assert target.owner == "testorg"
            assert target.repo == "testrepo"
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_target_missing_config(self):
        """Test GitHub target with missing required config."""
        try:
            from secretzero.targets.github import GitHubSecretTarget
            
            provider = Mock()
            config = {"owner": "testorg"}  # Missing repo
            
            with pytest.raises(ValueError):
                GitHubSecretTarget(provider, config)
        except ImportError:
            pytest.skip("PyGithub not installed")

    def test_github_target_store_repository_secret(self):
        """Test storing a repository secret."""
        try:
            from secretzero.targets.github import GitHubSecretTarget
            
            provider = Mock()
            mock_auth = Mock()
            mock_client = Mock()
            mock_repo = Mock()
            mock_public_key = Mock()
            mock_public_key.key = "test-public-key-base64"
            
            mock_repo.get_public_key.return_value = mock_public_key
            mock_repo.create_secret = Mock(return_value=None)
            mock_client.get_repo.return_value = mock_repo
            mock_auth.get_client.return_value = mock_client
            provider.auth = mock_auth
            
            config = {"owner": "testorg", "repo": "testrepo"}
            target = GitHubSecretTarget(provider, config)
            
            with patch("base64.b64decode"), \
                 patch("base64.b64encode"), \
                 patch("nacl.public.SealedBox"), \
                 patch("nacl.public.PublicKey"):
                result = target.store("TEST_SECRET", "secret-value")
                assert result is True
        except ImportError:
            pytest.skip("PyGithub not installed")


class TestGitLabTarget:
    """Tests for GitLab variable target."""

    def test_import_gitlab_target(self):
        """Test importing GitLab target."""
        try:
            from secretzero.targets.gitlab import GitLabVariableTarget
            assert GitLabVariableTarget is not None
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_target_initialization(self):
        """Test GitLab target initialization."""
        try:
            from secretzero.targets.gitlab import GitLabVariableTarget
            
            provider = Mock()
            config = {"project": "group/project"}
            target = GitLabVariableTarget(provider, config)
            
            assert target.project == "group/project"
            assert target.masked is True  # Default
        except ImportError:
            pytest.skip("python-gitlab not installed")

    def test_gitlab_target_missing_config(self):
        """Test GitLab target with missing required config."""
        try:
            from secretzero.targets.gitlab import GitLabVariableTarget
            
            provider = Mock()
            config = {}  # Missing project
            
            with pytest.raises(ValueError):
                GitLabVariableTarget(provider, config)
        except ImportError:
            pytest.skip("python-gitlab not installed")


class TestJenkinsTarget:
    """Tests for Jenkins credential target."""

    def test_import_jenkins_target(self):
        """Test importing Jenkins target."""
        try:
            from secretzero.targets.jenkins import JenkinsCredentialTarget
            assert JenkinsCredentialTarget is not None
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_target_initialization(self):
        """Test Jenkins target initialization."""
        try:
            from secretzero.targets.jenkins import JenkinsCredentialTarget
            
            provider = Mock()
            config = {"credential_id": "my-secret"}
            target = JenkinsCredentialTarget(provider, config)
            
            assert target.credential_id == "my-secret"
            assert target.credential_type == "string"  # Default
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_target_missing_config(self):
        """Test Jenkins target with missing required config."""
        try:
            from secretzero.targets.jenkins import JenkinsCredentialTarget
            
            provider = Mock()
            config = {}  # Missing credential_id
            
            with pytest.raises(ValueError):
                JenkinsCredentialTarget(provider, config)
        except ImportError:
            pytest.skip("python-jenkins not installed")

    def test_jenkins_target_username_password_missing_username(self):
        """Test Jenkins username/password credential missing username."""
        try:
            from secretzero.targets.jenkins import JenkinsCredentialTarget
            
            provider = Mock()
            config = {
                "credential_id": "my-secret",
                "credential_type": "username_password"
                # Missing username
            }
            
            with pytest.raises(ValueError):
                JenkinsCredentialTarget(provider, config)
        except ImportError:
            pytest.skip("python-jenkins not installed")
