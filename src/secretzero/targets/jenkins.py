"""Jenkins credential targets."""

import xml.etree.ElementTree as ET
from typing import Any, Optional

from secretzero.targets.base import BaseTarget


class JenkinsCredentialTarget(BaseTarget):
    """Store secrets as Jenkins credentials."""

    def __init__(self, provider: Any, config: Optional[dict[str, Any]] = None):
        """Initialize Jenkins credential target.

        Args:
            provider: Jenkins provider instance.
            config: Target configuration containing:
                - credential_id: Unique ID for the credential
                - description: Description of the credential
                - credential_type: Type of credential ('string', 'username_password', default: 'string')
                - username: Username (required if credential_type is 'username_password')
                - domain: Credential domain (default: '_')
                - folder: Optional Jenkins folder path
        """
        super().__init__(config)
        self.provider = provider
        self.credential_id = self.config.get("credential_id")
        self.description = self.config.get("description", "")
        self.credential_type = self.config.get("credential_type", "string")
        self.username = self.config.get("username")
        self.domain = self.config.get("domain", "_")
        self.folder = self.config.get("folder")

        if not self.credential_id:
            raise ValueError("Jenkins credential target requires 'credential_id' in config")
        
        if self.credential_type == "username_password" and not self.username:
            raise ValueError("username_password credential type requires 'username' in config")

    def _create_string_credential_xml(self, secret_value: str) -> str:
        """Create XML for a string credential.

        Args:
            secret_value: The secret value.

        Returns:
            XML string for the credential.
        """
        root = ET.Element("org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl")
        ET.SubElement(root, "scope").text = "GLOBAL"
        ET.SubElement(root, "id").text = self.credential_id
        ET.SubElement(root, "description").text = self.description
        ET.SubElement(root, "secret").text = secret_value
        return ET.tostring(root, encoding="unicode")

    def _create_username_password_credential_xml(self, secret_value: str) -> str:
        """Create XML for a username/password credential.

        Args:
            secret_value: The password value.

        Returns:
            XML string for the credential.
        """
        root = ET.Element("com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl")
        ET.SubElement(root, "scope").text = "GLOBAL"
        ET.SubElement(root, "id").text = self.credential_id
        ET.SubElement(root, "description").text = self.description
        ET.SubElement(root, "username").text = self.username
        ET.SubElement(root, "password").text = secret_value
        return ET.tostring(root, encoding="unicode")

    def _get_credential_xml(self, secret_value: str) -> str:
        """Get the XML for the credential based on type.

        Args:
            secret_value: The secret value.

        Returns:
            XML string for the credential.
        """
        if self.credential_type == "username_password":
            return self._create_username_password_credential_xml(secret_value)
        else:
            return self._create_string_credential_xml(secret_value)

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret as Jenkins credential.

        Args:
            secret_name: Name of the credential (used in description if not set).
            secret_value: Value of the credential.

        Returns:
            True if storage successful, False otherwise.
        """
        try:
            client = self.provider.auth.get_client()
            
            # Set description to secret name if not provided
            if not self.description:
                self.description = secret_name
            
            credential_xml = self._get_credential_xml(secret_value)
            
            # Determine the path for the credential
            if self.folder:
                path = f"job/{self.folder}/credentials/store/folder/domain/{self.domain}"
            else:
                path = f"credentials/store/system/domain/{self.domain}"
            
            # Check if credential exists
            try:
                existing_creds = client.list_credentials(self.folder if self.folder else None)
                credential_exists = any(
                    cred.get("id") == self.credential_id for cred in existing_creds
                )
                
                if credential_exists:
                    # Update existing credential
                    # Note: Jenkins API doesn't have a direct update method, so we delete and recreate
                    client.delete_credential(
                        self.credential_id,
                        folder_name=self.folder,
                        domain=self.domain
                    )
            except Exception:
                # Credential doesn't exist or error checking, proceed to create
                pass
            
            # Create the credential
            # Jenkins API uses a POST request to create credentials
            # The python-jenkins library may not have built-in support for this
            # We'll use the lower-level API request method
            create_url = f"{path}/createCredentials"
            client.requester.post_xml_and_confirm_status(
                create_url,
                credential_xml
            )
            
            return True
        except Exception as e:
            print(f"Failed to store credential in Jenkins: {e}")
            # Fallback: Try using the groovy script approach
            try:
                return self._store_via_groovy(secret_name, secret_value)
            except Exception as groovy_error:
                print(f"Groovy script fallback also failed: {groovy_error}")
                return False

    def _store_via_groovy(self, secret_name: str, secret_value: str) -> bool:
        """Store credential using Groovy script execution.

        This is a fallback method that uses Jenkins script console.

        Args:
            secret_name: Name of the credential.
            secret_value: Value of the credential.

        Returns:
            True if storage successful, False otherwise.
        """
        client = self.provider.auth.get_client()
        
        if self.credential_type == "username_password":
            script = f"""
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.impl.*
import com.cloudbees.plugins.credentials.domains.*
import hudson.util.Secret

def domain = Domain.global()
def store = SystemCredentialsProvider.getInstance().getStore()

def credentials = new UsernamePasswordCredentialsImpl(
    CredentialsScope.GLOBAL,
    "{self.credential_id}",
    "{self.description}",
    "{self.username}",
    "{secret_value}"
)

// Remove existing credential if it exists
def existing = store.getCredentials(domain).find {{ it.id == "{self.credential_id}" }}
if (existing) {{
    store.removeCredentials(domain, existing)
}}

store.addCredentials(domain, credentials)
"""
        else:
            script = f"""
import com.cloudbees.plugins.credentials.*
import org.jenkinsci.plugins.plaincredentials.impl.*
import com.cloudbees.plugins.credentials.domains.*
import hudson.util.Secret

def domain = Domain.global()
def store = SystemCredentialsProvider.getInstance().getStore()

def credentials = new StringCredentialsImpl(
    CredentialsScope.GLOBAL,
    "{self.credential_id}",
    "{self.description}",
    Secret.fromString("{secret_value}")
)

// Remove existing credential if it exists
def existing = store.getCredentials(domain).find {{ it.id == "{self.credential_id}" }}
if (existing) {{
    store.removeCredentials(domain, existing)
}}

store.addCredentials(domain, credentials)
"""
        
        client.run_script(script)
        return True

    def retrieve(self, secret_name: str) -> Optional[str]:
        """Retrieve credential from Jenkins.

        Note: Jenkins API does not expose credential values for security reasons.

        Args:
            secret_name: Name of the credential.

        Returns:
            None (credentials cannot be retrieved from Jenkins).
        """
        # Jenkins API does not expose credential values
        return None
