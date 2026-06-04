# Jenkins Credentials

Jenkins credentials targets allow you to securely store secrets as Jenkins credentials for use in pipelines, freestyle jobs, and other Jenkins automation. Credentials can be stored as simple strings (for API keys and tokens) or username/password pairs, with support for folder-scoped credentials and domain management.

## Overview

Jenkins provides multiple credential types for secure secret storage:

- **String Credentials** - Store simple text secrets like API keys, tokens, and passwords
- **Username/Password Credentials** - Store authentication pairs for databases, services, and APIs

SecretZero integrates with Jenkins' API to automatically create and update credentials using either XML-based REST API calls or Groovy script execution as a fallback. Credentials are encrypted by Jenkins and stored securely in its credential store.

!!! warning "Secret Retrieval Limitation"
    Jenkins' API does not allow retrieving credential values for security reasons. Once a credential is stored, it cannot be read back via the API. This is a Jenkins security feature, not a SecretZero limitation.

## Use Cases

- **Jenkins Pipelines** - Automate credential management for declarative and scripted pipelines
- **Jenkinsfiles** - Reference credentials in pipeline-as-code configurations
- **Freestyle Jobs** - Inject credentials into build environments
- **Multi-Environment Deployments** - Manage separate credentials for different deployment targets
- **Folder-Based Organization** - Scope credentials to specific Jenkins folders for better access control
- **Credential Rotation** - Regularly update credentials across all Jenkins jobs from a single source
- **Infrastructure as Code** - Version control credential configurations without exposing values

## Prerequisites

### Required Dependencies

Jenkins support requires the python-jenkins library:

```bash
# Install with Jenkins support
pip install secretzero[jenkins]

# Or install python-jenkins separately
pip install python-jenkins
```

### Jenkins API Token Generation

You need a Jenkins API token with appropriate permissions:

1. **Generate API Token:**
   - Log in to Jenkins
   - Navigate to: Your Username (top right) → Configure
   - Under "API Token", click "Add new Token"
   - Give it a name (e.g., "SecretZero")
   - Click "Generate"
   - Copy the generated token immediately (it won't be shown again)

2. **Required Permissions:**
   - **Overall/Administer** - For global credentials
   - **Credentials/Create** - To create new credentials
   - **Credentials/Update** - To update existing credentials
   - **Credentials/Delete** - To remove/replace credentials
   - **Job/Configure** - For folder-scoped credentials

!!! tip "Jenkins RBAC"
    Use Jenkins' Role-Based Access Control (RBAC) plugin to create a dedicated service account with minimal required permissions for SecretZero.

## Authentication

SecretZero authenticates with Jenkins using a username and API token.

**Provider Configuration:**
```yaml
providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: ${JENKINS_USERNAME}
        token: ${JENKINS_TOKEN}
```

**Configuration Options:**

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `url` | string | Yes | Jenkins base URL (e.g., https://jenkins.example.com) |
| `username` | string | Yes | Jenkins username |
| `token` | string | Yes | Jenkins API token |

**Environment Variables:**
```bash
export JENKINS_USERNAME="admin"
export JENKINS_TOKEN="11abc123def456789abc123def456789ab"
```

## Target Configuration

### Basic Configuration

Store secrets as Jenkins credentials with minimal configuration.

```yaml
targets:
  - provider: jenkins
    kind: jenkins_credential
    config:
      credential_id: my-secret
      credential_type: string
      description: My API Key
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `credential_id` | string | Yes | - | Unique identifier for the credential (used in pipelines) |
| `credential_type` | string | No | `string` | Type of credential: `string` or `username_password` |
| `description` | string | No | Secret name | Human-readable description of the credential |
| `username` | string | Conditional | - | Username (required if `credential_type` is `username_password`) |
| `domain` | string | No | `_` | Credential domain (default is `_` for global domain) |
| `folder` | string | No | - | Jenkins folder path for folder-scoped credentials |

## Credential Types

### String Credentials

String credentials store simple text values like API keys, tokens, or passwords.

**XML Format:**
```xml
<org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>
  <scope>GLOBAL</scope>
  <id>api-key-prod</id>
  <description>Production API Key</description>
  <secret>your-secret-value-here</secret>
</org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>
```

**Configuration Example:**
```yaml
targets:
  - provider: jenkins
    kind: jenkins_credential
    config:
      credential_id: api-key-prod
      credential_type: string
      description: Production API Key
```

**Use Cases:**
- API keys and tokens
- Single passwords or passphrases
- SSH private keys
- License keys
- Certificate content

### Username/Password Credentials

Username/password credentials store authentication pairs for services requiring both username and password.

**XML Format:**
```xml
<com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
  <scope>GLOBAL</scope>
  <id>db-credentials</id>
  <description>Database Credentials</description>
  <username>dbuser</username>
  <password>your-password-here</password>
</com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
```

**Configuration Example:**
```yaml
targets:
  - provider: jenkins
    kind: jenkins_credential
    config:
      credential_id: db-credentials
      credential_type: username_password
      username: dbuser
      description: Database Login
```

**Use Cases:**
- Database connections
- Service authentication
- Docker registry login
- Git repository access
- API basic authentication

## Advanced Features

### Groovy Script Fallback

If the XML-based REST API fails (due to permissions, plugin versions, or configuration), SecretZero automatically falls back to using Groovy script execution through Jenkins' script console.

**String Credential Script:**
```groovy
import com.cloudbees.plugins.credentials.*
import org.jenkinsci.plugins.plaincredentials.impl.*
import com.cloudbees.plugins.credentials.domains.*
import hudson.util.Secret

def domain = Domain.global()
def store = SystemCredentialsProvider.getInstance().getStore()

def credentials = new StringCredentialsImpl(
    CredentialsScope.GLOBAL,
    "credential-id",
    "Description",
    Secret.fromString("secret-value")
)

// Remove existing credential if it exists
def existing = store.getCredentials(domain).find { it.id == "credential-id" }
if (existing) {
    store.removeCredentials(domain, existing)
}

store.addCredentials(domain, credentials)
```

**Username/Password Credential Script:**
```groovy
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.impl.*
import com.cloudbees.plugins.credentials.domains.*

def domain = Domain.global()
def store = SystemCredentialsProvider.getInstance().getStore()

def credentials = new UsernamePasswordCredentialsImpl(
    CredentialsScope.GLOBAL,
    "credential-id",
    "Description",
    "username",
    "password"
)

// Remove existing credential if it exists
def existing = store.getCredentials(domain).find { it.id == "credential-id" }
if (existing) {
    store.removeCredentials(domain, existing)
}

store.addCredentials(domain, credentials)
```

!!! info "Script Console Access"
    Groovy script execution requires "Overall/RunScripts" permission and may be restricted by Jenkins security policies. If both methods fail, check Jenkins permissions and security settings.

### Credential Domains

Jenkins organizes credentials into domains for better access control. The default domain `_` is used for global credentials.

**Default Domain (Global):**
```yaml
config:
  credential_id: my-secret
  domain: _  # or omit, as '_' is the default
```

**Custom Domain:**
```yaml
config:
  credential_id: my-secret
  domain: my-custom-domain
```

### Folder-Scoped Credentials

Store credentials within specific Jenkins folders to limit scope and improve security.

**Configuration:**
```yaml
config:
  credential_id: dev-api-key
  folder: development/backend
  description: Development Backend API Key
```

**Path Structure:**
```
Jenkins Root
├── Folder: development
│   └── Folder: backend
│       └── Credentials
│           └── dev-api-key
```

## Complete Examples

### Example 1: String Credentials (API Keys)

Store API keys and tokens as string credentials.

```yaml
version: '1.0'

variables:
  jenkins_url: https://jenkins.example.com
  jenkins_username: admin

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: ${jenkins_url}
        username: ${jenkins_username}
        token: ${JENKINS_TOKEN}

secrets:
  # Production API key
  - name: api_key_prod
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-prod
          credential_type: string
          description: Production API Key

  # AWS Secret Access Key
  - name: aws_secret_key
    kind: random_string
    config:
      length: 40
      charset: alphanumeric
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: aws-secret-access-key
          credential_type: string
          description: AWS Secret Access Key

  # GitHub Personal Access Token
  - name: github_token
    kind: static
    config:
      default: ${GITHUB_PAT}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: github-pat
          credential_type: string
          description: GitHub Personal Access Token
```

### Example 2: Username/Password Credentials

Store authentication pairs for databases and services.

```yaml
version: '1.0'

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: ${JENKINS_URL}
        username: ${JENKINS_USERNAME}
        token: ${JENKINS_TOKEN}

secrets:
  # Database credentials
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: db-credentials
          credential_type: username_password
          username: dbuser
          description: Production Database Credentials

  # Docker Hub credentials
  - name: dockerhub_password
    kind: static
    config:
      default: ${DOCKERHUB_PASSWORD}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: dockerhub-creds
          credential_type: username_password
          username: mycompany
          description: Docker Hub Login

  # LDAP Service Account
  - name: ldap_password
    kind: random_password
    config:
      length: 24
      special: true
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: ldap-service-account
          credential_type: username_password
          username: CN=jenkins,OU=ServiceAccounts,DC=example,DC=com
          description: LDAP Service Account
```

### Example 3: Folder-Scoped Credentials

Organize credentials by folder for better access control.

```yaml
version: '1.0'

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: ${JENKINS_URL}
        username: ${JENKINS_USERNAME}
        token: ${JENKINS_TOKEN}

secrets:
  # Development environment credentials (folder: development)
  - name: dev_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key
          credential_type: string
          folder: development
          description: Development API Key

  # Production environment credentials (folder: production)
  - name: prod_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key
          credential_type: string
          folder: production
          description: Production API Key

  # Staging database credentials (folder: staging)
  - name: staging_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: db-credentials
          credential_type: username_password
          username: staginguser
          folder: staging
          description: Staging Database Credentials
```

### Example 4: Multi-Jenkins Deployment

Manage credentials across multiple Jenkins instances.

```yaml
version: '1.0'

providers:
  jenkins_prod:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins-prod.example.com
        username: ${JENKINS_PROD_USERNAME}
        token: ${JENKINS_PROD_TOKEN}

  jenkins_staging:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins-staging.example.com
        username: ${JENKINS_STAGING_USERNAME}
        token: ${JENKINS_STAGING_TOKEN}

secrets:
  # Shared secret across multiple Jenkins instances
  - name: shared_api_key
    kind: random_string
    config:
      length: 32
    targets:
      # Store in production Jenkins
      - provider: jenkins_prod
        kind: jenkins_credential
        config:
          credential_id: shared-api-key
          credential_type: string
          description: Shared API Key (Production)
      
      # Store in staging Jenkins
      - provider: jenkins_staging
        kind: jenkins_credential
        config:
          credential_id: shared-api-key
          credential_type: string
          description: Shared API Key (Staging)

  # Environment-specific credentials
  - name: prod_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: jenkins_prod
        kind: jenkins_credential
        config:
          credential_id: db-credentials
          credential_type: username_password
          username: prod_dbuser
          description: Production Database

  - name: staging_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: jenkins_staging
        kind: jenkins_credential
        config:
          credential_id: db-credentials
          credential_type: username_password
          username: staging_dbuser
          description: Staging Database
```

## Using Credentials in Jenkins

### Declarative Pipeline

Reference credentials in declarative pipelines using the `credentials()` helper or `withCredentials` step.

**String Credentials:**
```groovy
pipeline {
    agent any
    
    environment {
        // Simple credential binding
        API_KEY = credentials('api-key-prod')
    }
    
    stages {
        stage('Deploy') {
            steps {
                sh '''
                    echo "Deploying with API key: $API_KEY"
                    curl -H "Authorization: Bearer $API_KEY" https://api.example.com/deploy
                '''
            }
        }
    }
}
```

**Username/Password Credentials:**
```groovy
pipeline {
    agent any
    
    stages {
        stage('Database Migration') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'db-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASS'
                    )
                ]) {
                    sh '''
                        echo "Running migrations as $DB_USER"
                        ./migrate.sh --user "$DB_USER" --password "$DB_PASS"
                    '''
                }
            }
        }
    }
}
```

**Multiple Credentials:**
```groovy
pipeline {
    agent any
    
    environment {
        API_KEY = credentials('api-key-prod')
    }
    
    stages {
        stage('Deploy') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'db-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASS'
                    ),
                    string(
                        credentialsId: 'aws-secret-access-key',
                        variable: 'AWS_SECRET'
                    )
                ]) {
                    sh '''
                        echo "API Key: $API_KEY"
                        echo "DB User: $DB_USER"
                        echo "AWS Secret: $AWS_SECRET"
                        ./deploy.sh
                    '''
                }
            }
        }
    }
}
```

### Scripted Pipeline

Use credentials in scripted pipelines with the `withCredentials` block.

```groovy
node {
    stage('Build') {
        // String credential
        withCredentials([string(credentialsId: 'api-key-prod', variable: 'API_KEY')]) {
            sh "echo 'Building with API key: $API_KEY'"
        }
    }
    
    stage('Test') {
        // Username/Password credential
        withCredentials([
            usernamePassword(
                credentialsId: 'db-credentials',
                usernameVariable: 'USER',
                passwordVariable: 'PASS'
            )
        ]) {
            sh """
                echo 'Testing with user: $USER'
                ./run-tests.sh --db-user \$USER --db-pass \$PASS
            """
        }
    }
    
    stage('Deploy') {
        // Multiple credentials
        withCredentials([
            string(credentialsId: 'api-key-prod', variable: 'API_KEY'),
            usernamePassword(
                credentialsId: 'dockerhub-creds',
                usernameVariable: 'DOCKER_USER',
                passwordVariable: 'DOCKER_PASS'
            )
        ]) {
            sh '''
                docker login -u $DOCKER_USER -p $DOCKER_PASS
                docker push myimage:latest
                curl -H "Authorization: Bearer $API_KEY" https://api.example.com/deploy
            '''
        }
    }
}
```

### Freestyle Jobs

Use credentials in freestyle jobs through the build environment configuration.

1. **Configure Job:**
   - Open job configuration
   - Under "Build Environment", check "Use secret text(s) or file(s)"

2. **Add Bindings:**
   - **Secret text:** For string credentials
     - Variable: `API_KEY`
     - Credentials: Select `api-key-prod`
   - **Username and password:** For username/password credentials
     - Username Variable: `DB_USER`
     - Password Variable: `DB_PASS`
     - Credentials: Select `db-credentials`

3. **Use in Build Steps:**
   ```bash
   echo "API Key: $API_KEY"
   echo "Database User: $DB_USER"
   ./deploy.sh --api-key "$API_KEY" --db-user "$DB_USER" --db-pass "$DB_PASS"
   ```

## Best Practices

### Credential ID Naming

Use consistent, descriptive naming conventions for credential IDs:

```yaml
# Good practices
credential_id: api-key-prod          # Environment-specific
credential_id: db-credentials-mysql  # Service-specific
credential_id: github-deploy-token   # Purpose-specific
credential_id: aws-secret-us-east-1  # Region-specific

# Avoid
credential_id: secret1               # Non-descriptive
credential_id: mykey                 # Too vague
credential_id: prod-secret           # Ambiguous
```

### Folder Organization

Organize credentials using Jenkins folders:

```yaml
# Environment-based folders
folder: production
folder: staging
folder: development

# Team-based folders
folder: backend-team
folder: frontend-team
folder: devops-team

# Project-based folders
folder: project-alpha
folder: project-beta

# Nested folders
folder: production/backend
folder: staging/frontend
```

### Domain Usage

Use domains to further organize credentials:

```yaml
# Default global domain (most common)
domain: _

# Custom domains for specific use cases
domain: dev-environment
domain: cloud-providers
domain: external-services
```

### Credential Rotation

Implement regular credential rotation:

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    rotation_period: 90d  # Rotate every 90 days
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-prod
```

**Rotation Workflow:**
```bash
# Check current credential status
secretzero status -f Secretfile.yml

# Rotate credentials approaching expiration
secretzero rotate -f Secretfile.yml

# Update Jenkins credentials
secretzero sync -f Secretfile.yml
```

### Access Control

Limit credential access using Jenkins security features:

1. **Folder Permissions:**
   - Configure folder-level permissions
   - Grant minimal required access
   - Use folder credentials for better isolation

2. **Credential Domains:**
   - Separate credentials by domain
   - Apply domain-specific access policies

3. **Role-Based Access:**
   - Use Jenkins RBAC plugin
   - Create dedicated service accounts
   - Limit credential view/use permissions

### Version Control

Track credential configurations without exposing values:

```yaml
# Secretfile.yml - Safe to commit
secrets:
  - name: api_key
    kind: random_string
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-prod

# .env - DO NOT COMMIT
JENKINS_TOKEN=your-token-here
JENKINS_USERNAME=admin
```

**.gitignore:**
```
.env
.secretzero.lock
*.secret
```

## Security Considerations

### Credential Encryption

Jenkins automatically encrypts stored credentials:

- **At Rest:** Credentials are encrypted using Jenkins' master key
- **In Transit:** Use HTTPS for Jenkins API communication
- **In Use:** Credentials are masked in build logs by default

**Enable secure communication:**
```yaml
providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com  # Always use HTTPS
        username: ${JENKINS_USERNAME}
        token: ${JENKINS_TOKEN}
```

### Access Control

Implement defense-in-depth:

1. **Jenkins Level:**
   - Enable Jenkins security
   - Use authentication (LDAP, Active Directory, SSO)
   - Implement authorization strategy (Matrix-based, Role-based)

2. **Credential Level:**
   - Limit credential scope to specific folders
   - Use domains for additional isolation
   - Regularly review credential access logs

3. **API Level:**
   - Use API tokens instead of passwords
   - Rotate API tokens regularly
   - Limit token scope to required permissions

### Audit Logging

Enable and monitor Jenkins audit logs:

```groovy
// Configure audit logging in Jenkins
import jenkins.security.ApiTokenProperty
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy

// Enable audit trail plugin
def auditTrail = Jenkins.instance.getExtensionList('hudson.plugins.audit_trail.AuditTrailPlugin')[0]
auditTrail.configure()
```

**Monitor for:**
- Credential creation/updates
- Credential access patterns
- Failed authentication attempts
- Unusual API activity

### Secret Masking

Jenkins automatically masks credentials in build logs:

```groovy
// Credentials are automatically masked
withCredentials([string(credentialsId: 'api-key', variable: 'KEY')]) {
    sh 'echo $KEY'  // Output: ****
}

// Warning: Shell features may bypass masking
withCredentials([string(credentialsId: 'api-key', variable: 'KEY')]) {
    sh 'echo $KEY | base64'  // May expose the credential!
}
```

**Best practices:**
- Avoid passing credentials through pipes or shell substitutions
- Use direct credential bindings
- Test credential masking in build logs
- Regularly review build logs for exposed secrets

### Network Security

Secure Jenkins network communication:

```yaml
# Use HTTPS
url: https://jenkins.example.com

# For internal networks, consider VPN or private network
url: https://jenkins.internal.corp

# Avoid
url: http://jenkins.example.com  # Insecure!
```

**Additional security:**
- Enable Jenkins CSRF protection
- Configure Content Security Policy
- Use reverse proxy with additional security headers
- Implement rate limiting

## Troubleshooting

### Authentication Issues

**Problem:** Authentication failed or connection refused.

**Solutions:**
```bash
# Verify Jenkins URL is accessible
curl -I https://jenkins.example.com

# Check credentials
export JENKINS_USERNAME="admin"
export JENKINS_TOKEN="your-token-here"

# Test authentication
curl -u $JENKINS_USERNAME:$JENKINS_TOKEN https://jenkins.example.com/api/json

# Verify token permissions
# Login to Jenkins → Configure → API Token → Check token exists
```

### Permission Denied

**Problem:** User doesn't have permission to create/update credentials.

**Required Permissions:**
- Overall/Administer (for global credentials)
- Credentials/Create
- Credentials/Update
- Credentials/Delete

**Check permissions:**
1. Navigate to: Jenkins → Manage Jenkins → Configure Global Security
2. Check Authorization Strategy
3. Verify user has required permissions
4. For folder credentials, check folder-level permissions

**Solutions:**
```groovy
// Grant permissions to user (run as admin)
import jenkins.model.Jenkins
import hudson.security.*

def jenkins = Jenkins.instance
def strategy = jenkins.getAuthorizationStrategy()

// Add permissions for your user
// This depends on your authorization strategy (Matrix, Role-based, etc.)
```

### Credential Not Found

**Problem:** Credential doesn't appear in Jenkins UI or pipelines.

**Check:**
```bash
# Verify credential was created
secretzero sync -f Secretfile.yml --dry-run

# Check Jenkins UI
# Navigate to: Manage Jenkins → Manage Credentials

# Verify credential ID matches
# Pipeline: credentials('api-key-prod')
# Config: credential_id: api-key-prod
```

**Common issues:**
- Credential created in wrong folder
- Credential in different domain
- Typo in credential ID
- Insufficient permissions to view credential

### Groovy Script Execution Failed

**Problem:** XML API failed and Groovy fallback also failed.

**Solutions:**

1. **Enable Script Security:**
   - Navigate to: Manage Jenkins → Configure Global Security
   - Under "CSRF Protection", ensure "Enable script security for Job DSL scripts" is configured
   - Check "Script Security" plugin is installed

2. **Approve Script:**
   - Navigate to: Manage Jenkins → In-process Script Approval
   - Approve any pending script signatures

3. **Check Permissions:**
   ```groovy
   // Verify script console access (run as admin in script console)
   import jenkins.model.Jenkins
   println("Script console is accessible")
   ```

4. **Plugin Requirements:**
   - Ensure "Plain Credentials Plugin" is installed (for string credentials)
   - Ensure "Credentials Binding Plugin" is installed
   - Update plugins to latest versions

### Credential Update Not Reflected

**Problem:** Updated credential value not reflected in builds.

**Solutions:**
```bash
# Force sync
secretzero sync -f Secretfile.yml --force

# Verify credential was updated
# Check Jenkins UI for updated timestamp

# Clear pipeline cache
# May need to run pipeline to refresh credential binding
```

**Note:** Jenkins caches credentials during pipeline execution. Restart running jobs to pick up updated credentials.

### XML API Errors

**Problem:** `Failed to store credential in Jenkins: <error message>`

**Common causes:**
- Invalid XML format
- Missing required plugins
- Jenkins API version incompatibility
- Network issues

**Solutions:**
```bash
# Enable debug logging
export SECRETZERO_DEBUG=1
secretzero sync -f Secretfile.yml

# Test XML API directly
curl -X POST -u $JENKINS_USERNAME:$JENKINS_TOKEN \
  -H "Content-Type: application/xml" \
  -d '<credentials>...</credentials>' \
  https://jenkins.example.com/credentials/store/system/domain/_/createCredentials

# Check Jenkins version
curl -u $JENKINS_USERNAME:$JENKINS_TOKEN \
  https://jenkins.example.com/api/json?tree=version

# Verify plugins
curl -u $JENKINS_USERNAME:$JENKINS_TOKEN \
  https://jenkins.example.com/pluginManager/api/json?depth=1
```

### Folder Not Found

**Problem:** Credential not created in specified folder.

**Solutions:**
```bash
# Verify folder exists
# Navigate to Jenkins UI → Check folder hierarchy

# Create folder first
# Either manually in UI or via Jenkins Job DSL

# Check folder path format
# Correct: folder: production/backend
# Incorrect: folder: /production/backend/
```

**Create folder via API:**
```bash
curl -X POST -u $JENKINS_USERNAME:$JENKINS_TOKEN \
  -H "Content-Type: application/xml" \
  -d '<com.cloudbees.hudson.plugins.folder.Folder/>' \
  https://jenkins.example.com/createItem?name=production
```

## Integration Examples

### Docker Hub Credentials

Store Docker Hub credentials for image publishing:

```yaml
secrets:
  - name: dockerhub_password
    kind: static
    config:
      default: ${DOCKERHUB_PASSWORD}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: dockerhub
          credential_type: username_password
          username: ${DOCKERHUB_USERNAME}
          description: Docker Hub Credentials
```

**Pipeline usage:**
```groovy
pipeline {
    agent any
    stages {
        stage('Push Image') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )
                ]) {
                    sh '''
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        docker push mycompany/myapp:latest
                    '''
                }
            }
        }
    }
}
```

### AWS Credentials

Store AWS access credentials:

```yaml
secrets:
  - name: aws_access_key
    kind: static
    config:
      default: ${AWS_ACCESS_KEY_ID}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: aws-credentials
          credential_type: username_password
          username: ${AWS_ACCESS_KEY_ID}
          description: AWS Credentials

  - name: aws_secret_key
    kind: static
    config:
      default: ${AWS_SECRET_ACCESS_KEY}
    # Note: AWS secret is stored as password in username/password credential
```

**Pipeline usage:**
```groovy
pipeline {
    agent any
    stages {
        stage('Deploy to AWS') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'aws-credentials',
                        usernameVariable: 'AWS_ACCESS_KEY_ID',
                        passwordVariable: 'AWS_SECRET_ACCESS_KEY'
                    )
                ]) {
                    sh '''
                        aws s3 sync ./build s3://my-bucket/
                        aws cloudformation deploy --template-file template.yml
                    '''
                }
            }
        }
    }
}
```

### Kubernetes Secrets

Generate and store Kubernetes secrets:

```yaml
secrets:
  - name: k8s_token
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: k8s-token
          credential_type: string
          description: Kubernetes Service Account Token
```

**Pipeline usage:**
```groovy
pipeline {
    agent any
    stages {
        stage('Deploy to K8s') {
            steps {
                withCredentials([string(credentialsId: 'k8s-token', variable: 'K8S_TOKEN')]) {
                    sh '''
                        kubectl config set-credentials jenkins --token="$K8S_TOKEN"
                        kubectl apply -f deployment.yml
                    '''
                }
            }
        }
    }
}
```

### Git Repository Access

Store Git credentials for repository access:

```yaml
secrets:
  - name: git_password
    kind: static
    config:
      default: ${GIT_PASSWORD}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: git-credentials
          credential_type: username_password
          username: ${GIT_USERNAME}
          description: Git Repository Credentials
```

**Pipeline usage:**
```groovy
pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                git credentialsId: 'git-credentials',
                    url: 'https://git.example.com/myrepo.git',
                    branch: 'main'
            }
        }
    }
}
```

## Additional Resources

- [Jenkins Credentials Plugin Documentation](https://plugins.jenkins.io/credentials/)
- [Jenkins Pipeline Syntax Reference](https://www.jenkins.io/doc/book/pipeline/syntax/#credentials)
- [python-jenkins Library Documentation](https://python-jenkins.readthedocs.io/)
- [SecretZero Jenkins Example](../../examples/jenkins-credentials.md)

## Summary

Jenkins credentials targets in SecretZero provide:

- ✅ Automated credential creation and updates
- ✅ Support for string and username/password credential types
- ✅ Folder-scoped credentials for better organization
- ✅ Multiple deployment strategies (XML API and Groovy scripts)
- ✅ Seamless integration with Jenkins pipelines and jobs
- ✅ Jenkins-managed credential encryption at rest
- ✅ Multi-Jenkins instance support

For additional help or examples, refer to the [examples directory](../../examples/index.md) or [open an issue](https://github.com/zloeber/SecretZero/issues).
