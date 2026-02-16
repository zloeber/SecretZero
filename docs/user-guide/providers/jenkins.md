# Jenkins Provider

The Jenkins provider enables SecretZero to store and manage credentials in Jenkins. It supports API token authentication for managing various Jenkins credential types including secret text, username/password pairs, and secret files.

## Overview

The Jenkins provider is ideal for:

- **CI/CD pipelines** using Jenkins for build and deployment automation
- **Multi-job deployments** requiring consistent credentials across Jenkins jobs
- **Folder-scoped credentials** for team-based access control and organization
- **Jenkins Multibranch pipelines** needing dynamic credential management
- **Organizations standardized on Jenkins** for automation and orchestration
- **Hybrid cloud deployments** where Jenkins acts as the central automation hub

### Supported Target Types

| Target Type | Description | Use Case |
|-------------|-------------|----------|
| `jenkins_credential` | Jenkins credentials (string, username/password, secret file) | API keys, database credentials, deployment tokens, SSH keys, service account credentials |

## Authentication

### API Token Authentication

The Jenkins provider uses Jenkins API tokens for authentication. API tokens are more secure than passwords and can be revoked independently.

```yaml
providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: admin
        token: ${JENKINS_TOKEN}
```

**When to use**: All scenarios with Jenkins credential management. API tokens are recommended over passwords for security.

### Creating a Jenkins API Token

1. **Navigate to User Configuration**:
   - Log in to Jenkins
   - Click your username in the top-right corner
   - Select "Configure" from the dropdown

2. **Generate API Token**:
   - Scroll to the "API Token" section
   - Click "Add new Token"
   - Give it a descriptive name (e.g., "SecretZero Token")
   - Click "Generate"

3. **Save the token**:
   - Copy the generated token immediately (it won't be shown again)
   - Store securely or export as environment variable

4. **Set environment variable**:
   ```bash
   export JENKINS_TOKEN=11a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5
   export JENKINS_USERNAME=admin
   ```

### Required Permissions

Your Jenkins user must have the following permissions:

| Permission | Scope | Purpose |
|------------|-------|---------|
| `Overall/Read` | Global | Basic access to Jenkins |
| `Credentials/Create` | Global or Folder | Create new credentials |
| `Credentials/Update` | Global or Folder | Update existing credentials |
| `Credentials/View` | Global or Folder | View credential metadata |

**Note**: For global credentials, you may need `Overall/Administer` permission depending on your Jenkins security configuration.

## Configuration

### Basic Configuration

```yaml
version: '1.0'

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: admin
        token: ${JENKINS_TOKEN}

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-prod
          description: Production API Key
          credential_type: string
```

### Credential Types

Jenkins supports multiple credential types. Specify the `credential_type` in your configuration:

#### Secret Text (String)

Store simple text secrets like API keys, tokens, or passwords:

```yaml
targets:
  - provider: jenkins
    kind: jenkins_credential
    config:
      credential_id: api-key-prod
      description: Production API Key
      credential_type: string  # Default type
```

#### Username/Password

Store username and password pairs for database credentials, service accounts, etc.:

```yaml
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: db-credentials
          description: Database Credentials
          credential_type: username_password
          username: dbuser
```

#### Secret File

Store file contents as credentials (certificates, key files, etc.):

```yaml
secrets:
  - name: ssh_private_key
    kind: static
    config:
      default: ${SSH_PRIVATE_KEY}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: deployment-key
          description: Deployment SSH Key
          credential_type: secret_file
          filename: id_rsa
```

### Configuration Options

| Option | Required | Type | Description |
|--------|----------|------|-------------|
| `credential_id` | Yes | string | Unique identifier for the credential in Jenkins |
| `description` | No | string | Human-readable description of the credential |
| `credential_type` | No | string | Type of credential: `string` (default), `username_password`, `secret_file` |
| `username` | Conditional | string | Username for `username_password` type |
| `filename` | Conditional | string | Filename for `secret_file` type |
| `folder` | No | string | Jenkins folder path for scoped credentials |
| `domain` | No | string | Credential domain (default: `_` for global domain) |

## Complete Examples

### Example 1: Secret Text for API Keys

```yaml
version: '1.0'

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: ${JENKINS_USERNAME}
        token: ${JENKINS_TOKEN}

secrets:
  # GitHub API Token
  - name: github_token
    kind: static
    config:
      default: ${GITHUB_TOKEN}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: github-api-token
          description: GitHub API Token for CI/CD
          credential_type: string

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
          credential_id: aws-secret-key
          description: AWS Secret Access Key
          credential_type: string
```

### Example 2: Username/Password Credentials

```yaml
version: '1.0'

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: admin
        token: ${JENKINS_TOKEN}

secrets:
  # Database credentials
  - name: postgres_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: postgres-db-creds
          description: PostgreSQL Database Credentials
          credential_type: username_password
          username: postgres

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
          description: Docker Hub Registry Credentials
          credential_type: username_password
          username: ${DOCKERHUB_USERNAME}

  # Artifactory credentials
  - name: artifactory_password
    kind: random_password
    config:
      length: 24
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: artifactory-creds
          description: Artifactory Repository Credentials
          credential_type: username_password
          username: build-user
```

### Example 3: Secret File Credentials

```yaml
version: '1.0'

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: admin
        token: ${JENKINS_TOKEN}

secrets:
  # SSH Private Key
  - name: deploy_ssh_key
    kind: static
    config:
      default: ${DEPLOY_SSH_KEY}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: deployment-ssh-key
          description: SSH Key for Deployment Servers
          credential_type: secret_file
          filename: id_rsa

  # Kubernetes Config
  - name: kubeconfig
    kind: static
    config:
      default: ${KUBECONFIG_CONTENT}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: k8s-config
          description: Kubernetes Cluster Configuration
          credential_type: secret_file
          filename: kubeconfig.yaml

  # Service Account JSON
  - name: gcp_service_account
    kind: static
    config:
      default: ${GCP_SERVICE_ACCOUNT_JSON}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: gcp-service-account
          description: GCP Service Account Key
          credential_type: secret_file
          filename: service-account.json
```

### Example 4: Folder-Scoped Credentials

Scope credentials to specific Jenkins folders for better organization and access control:

```yaml
version: '1.0'

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: admin
        token: ${JENKINS_TOKEN}

secrets:
  # Production folder credentials
  - name: prod_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key
          description: Production API Key
          credential_type: string
          folder: production
          domain: _

  # Staging folder credentials
  - name: staging_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key
          description: Staging API Key
          credential_type: string
          folder: staging
          domain: _

  # Team-specific credentials
  - name: team_database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: db-credentials
          description: Team Database Credentials
          credential_type: username_password
          username: team_user
          folder: teams/backend-team
          domain: _
```

### Example 5: Multi-Environment Deployment

Manage credentials across multiple environments:

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
  # Development environment
  - name: api_key_dev
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-dev
          description: Development API Key
          credential_type: string

  # Staging environment
  - name: api_key_staging
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-staging
          description: Staging API Key
          credential_type: string

  # Production environment
  - name: api_key_prod
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-prod
          description: Production API Key
          credential_type: string

  # Shared database credentials
  - name: db_password_prod
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: db-prod-credentials
          description: Production Database Credentials
          credential_type: username_password
          username: prod_user
```

## Using Credentials in Jenkins Pipelines

Once synced to Jenkins, credentials can be used in various pipeline types.

### Declarative Pipeline

#### Secret Text

```groovy
pipeline {
    agent any
    
    environment {
        API_KEY = credentials('api-key-prod')
    }
    
    stages {
        stage('Deploy') {
            steps {
                sh '''
                    echo "Using API key: $API_KEY"
                    curl -H "Authorization: Bearer $API_KEY" \
                         https://api.example.com/deploy
                '''
            }
        }
    }
}
```

#### Username/Password

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
                        psql -h db.example.com \
                             -U $DB_USER \
                             -c "SELECT version();"
                    '''
                }
            }
        }
    }
}
```

#### Secret File

```groovy
pipeline {
    agent any
    
    stages {
        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([
                    file(
                        credentialsId: 'k8s-config',
                        variable: 'KUBECONFIG'
                    )
                ]) {
                    sh '''
                        kubectl --kubeconfig=$KUBECONFIG \
                                get pods
                        kubectl --kubeconfig=$KUBECONFIG \
                                apply -f deployment.yaml
                    '''
                }
            }
        }
    }
}
```

### Scripted Pipeline

```groovy
node {
    // String credential
    withCredentials([
        string(credentialsId: 'api-key-prod', variable: 'API_KEY')
    ]) {
        sh 'echo "API Key: $API_KEY"'
    }
    
    // Username/Password credential
    withCredentials([
        usernamePassword(
            credentialsId: 'db-credentials',
            usernameVariable: 'USER',
            passwordVariable: 'PASS'
        )
    ]) {
        sh '''
            echo "Database User: $USER"
            ./migrate.sh --user $USER --pass $PASS
        '''
    }
    
    // File credential
    withCredentials([
        file(credentialsId: 'deployment-ssh-key', variable: 'SSH_KEY')
    ]) {
        sh '''
            ssh -i $SSH_KEY user@server.example.com \
                './deploy.sh'
        '''
    }
}
```

### Multiple Credentials

```groovy
pipeline {
    agent any
    
    stages {
        stage('Deploy Application') {
            steps {
                withCredentials([
                    string(
                        credentialsId: 'api-key-prod',
                        variable: 'API_KEY'
                    ),
                    usernamePassword(
                        credentialsId: 'db-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASS'
                    ),
                    file(
                        credentialsId: 'k8s-config',
                        variable: 'KUBECONFIG'
                    )
                ]) {
                    sh '''
                        # Database setup
                        psql -h db.example.com -U $DB_USER -c "CREATE DATABASE app;"
                        
                        # Deploy to Kubernetes
                        kubectl --kubeconfig=$KUBECONFIG apply -f deployment.yaml
                        
                        # Configure application
                        curl -H "Authorization: Bearer $API_KEY" \
                             https://api.example.com/configure
                    '''
                }
            }
        }
    }
}
```

### Freestyle Jobs

For Freestyle jobs, use the "Bindings" feature:

1. **Configure Job**:
   - Go to your job → Configure
   - Check "Use secret text(s) or file(s)" under Build Environment

2. **Add Bindings**:
   - Click "Add" to add credential bindings
   - Select binding type (Secret text, Username and password, Secret file)
   - Choose credential from dropdown
   - Specify variable name

3. **Use in Build Steps**:
   - Reference credentials via environment variables in shell commands
   - Example: `echo $API_KEY` or `psql -U $DB_USER`

## Best Practices

### 1. Use API Tokens, Not Passwords

Always use Jenkins API tokens instead of passwords for authentication:

```yaml
# Good ✓
auth:
  kind: token
  config:
    token: ${JENKINS_TOKEN}

# Avoid ✗
auth:
  kind: token
  config:
    token: my_password_123
```

### 2. Scope Credentials to Folders

Use folder-scoped credentials for better access control and organization:

```yaml
secrets:
  - name: team_specific_secret
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: team-api-key
          folder: teams/backend-team  # Scope to folder
          domain: _
```

### 3. Use Appropriate Credential Types

Choose the correct credential type for your use case:

```yaml
# Use string for single values
credential_type: string

# Use username_password for login pairs
credential_type: username_password

# Use secret_file for certificates, keys, configs
credential_type: secret_file
```

### 4. Descriptive Credential IDs

Use clear, consistent naming conventions:

```yaml
# Good ✓
credential_id: api-key-prod
credential_id: db-staging-credentials
credential_id: k8s-prod-config

# Avoid ✗
credential_id: secret1
credential_id: creds
credential_id: key
```

### 5. Rotate Credentials Regularly

Use SecretZero's rotation capabilities or manually rotate:

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    # Set up rotation schedule
    rotation_period: 90d
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-prod
```

### 6. Use Environment Variables

Never hardcode credentials in configuration:

```yaml
# Good ✓
auth:
  config:
    token: ${JENKINS_TOKEN}

# Avoid ✗
auth:
  config:
    token: 11a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5
```

### 7. Exclude Special Characters

For passwords used in shell commands, exclude problematic characters:

```yaml
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`$'  # Exclude shell special chars
```

### 8. Add Descriptions

Always add meaningful descriptions:

```yaml
config:
  credential_id: db-credentials
  description: PostgreSQL Production Database Credentials  # Clear description
  credential_type: username_password
```

## Jenkins RBAC and Folder Structure

### Role-Based Access Control

Jenkins supports fine-grained access control for credentials:

1. **Global Credentials**:
   - Stored in the global domain
   - Accessible to all jobs (unless restricted)
   - Requires `Overall/Administer` or global `Credentials/Create` permission

2. **Folder Credentials**:
   - Scoped to specific folders
   - Only accessible to jobs within that folder hierarchy
   - Requires folder-level permissions

### Folder Hierarchy Example

```
Jenkins Root
├── production/               # Production folder
│   ├── credentials/          # Prod-only credentials
│   └── jobs/                 # Production jobs
├── staging/                  # Staging folder
│   ├── credentials/          # Staging-only credentials
│   └── jobs/                 # Staging jobs
└── teams/
    ├── backend-team/         # Team-specific folder
    │   ├── credentials/      # Team credentials
    │   └── jobs/             # Team jobs
    └── frontend-team/
        ├── credentials/
        └── jobs/
```

### Configuring Folder Credentials

```yaml
secrets:
  # Production credentials (production folder only)
  - name: prod_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: db-credentials
          folder: production
          domain: _

  # Team credentials (team folder only)
  - name: team_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key
          folder: teams/backend-team
          domain: _
```

### Setting Up Folder Permissions

1. **Install Folder Plugin**:
   - Ensure "Folders Plugin" is installed in Jenkins

2. **Configure Folder Authorization**:
   - Navigate to folder → Configure
   - Enable folder-level authorization
   - Assign permissions to users/groups

3. **Recommended Permissions**:
   - `Job/Read` - View jobs in folder
   - `Job/Build` - Execute jobs
   - `Credentials/View` - See credential metadata
   - `Credentials/Create` - Add credentials
   - `Credentials/Update` - Modify credentials

## Troubleshooting

### Authentication Failed

**Symptoms**: `Authentication failed` error during provider test or sync.

**Solutions**:

1. **Verify API token is valid**:
   ```bash
   curl -u admin:$JENKINS_TOKEN https://jenkins.example.com/api/json
   ```

2. **Check username matches token owner**:
   - Token must belong to the user specified in `username` field

3. **Verify Jenkins URL is correct**:
   ```yaml
   config:
     url: https://jenkins.example.com  # No trailing slash
   ```

4. **Check network connectivity**:
   ```bash
   curl -I https://jenkins.example.com
   ```

### Permission Denied

**Symptoms**: `Permission denied` or `403 Forbidden` errors when creating credentials.

**Solutions**:

1. **Check user permissions in Jenkins**:
   - Navigate to Manage Jenkins → Manage Users → [Your User] → Configure
   - Verify permissions include `Credentials/Create` and `Credentials/Update`

2. **For global credentials**:
   - May require `Overall/Administer` permission
   - Check global security settings

3. **For folder credentials**:
   - Ensure user has folder-level permissions
   - Navigate to folder → Configure → Permissions

4. **Verify security realm configuration**:
   - Check Manage Jenkins → Configure Global Security
   - Ensure authorization strategy allows credential management

### Credential Not Found in Job

**Symptoms**: Jenkins pipeline fails with "could not find credentials" error.

**Solutions**:

1. **Verify credential ID matches exactly**:
   ```groovy
   // Must match credential_id in Secretfile
   withCredentials([string(credentialsId: 'api-key-prod', variable: 'KEY')])
   ```

2. **Check credential scope**:
   - Global credentials are accessible to all jobs
   - Folder credentials only accessible within that folder

3. **Verify credential exists**:
   - Navigate to Manage Jenkins → Manage Credentials
   - Check appropriate domain and folder

4. **Check domain**:
   - Credentials in different domains are not accessible
   - Default domain is `_` (global)

### CSRF Protection Issues

**Symptoms**: `No valid crumb was included in the request` or CSRF-related errors.

**Solutions**:

1. **CSRF protection is enabled** (this is good):
   - SecretZero automatically handles CSRF tokens
   - No action needed if using python-jenkins library

2. **If errors persist**:
   - Check Jenkins CSRF configuration
   - Navigate to Manage Jenkins → Configure Global Security
   - Ensure "Prevent Cross Site Request Forgery exploits" is checked

3. **For older Jenkins versions**:
   - Upgrade to Jenkins 2.x or later
   - Install CSRF Protection Plugin

### Connection Timeout

**Symptoms**: Connection timeout or slow response from Jenkins.

**Solutions**:

1. **Check Jenkins load**:
   - High CPU/memory usage can slow API responses
   - Check Jenkins system information

2. **Increase timeout**:
   ```python
   # In custom script if needed
   client = jenkins.Jenkins(url, username, token, timeout=60)
   ```

3. **Check network latency**:
   ```bash
   ping jenkins.example.com
   curl -w "@curl-format.txt" -o /dev/null -s https://jenkins.example.com
   ```

### python-jenkins Not Installed

**Symptoms**: `python-jenkins not installed` error.

**Solutions**:

1. **Install python-jenkins**:
   ```bash
   pip install python-jenkins
   ```

2. **Verify installation**:
   ```bash
   python -c "import jenkins; print(jenkins.__version__)"
   ```

3. **Check requirements**:
   - Python 3.7 or later
   - python-jenkins 1.7.0 or later

### Credential Update Fails

**Symptoms**: Credential creation succeeds but updates fail.

**Solutions**:

1. **Verify `Credentials/Update` permission**:
   - User needs both Create and Update permissions

2. **Check credential ownership**:
   - Some Jenkins configurations restrict updates to credential owners

3. **Delete and recreate**:
   ```bash
   # If update fails, delete from Jenkins UI and re-sync
   secretzero sync -f Secretfile.yml
   ```

### Special Characters in Credentials

**Symptoms**: Credentials with special characters don't work in shell commands.

**Solutions**:

1. **Exclude problematic characters**:
   ```yaml
   config:
     length: 32
     special: true
     exclude_characters: '"@/\`$'
   ```

2. **Quote variables in shell**:
   ```groovy
   sh '''
       psql -h db.example.com -U "$DB_USER" -W "$DB_PASS"
   '''
   ```

3. **Use base64 encoding**:
   ```groovy
   sh '''
       echo "$PASSWORD" | base64 -d | command
   '''
   ```

## Advanced Integration

### Jenkins Plugins Integration

#### Credentials Binding Plugin

The standard way to use credentials in pipelines:

```groovy
withCredentials([
    string(credentialsId: 'api-key', variable: 'API_KEY')
]) {
    sh 'curl -H "Authorization: Bearer $API_KEY" api.example.com'
}
```

#### Plain Credentials Plugin

For generic credentials:

```groovy
withCredentials([
    usernamePassword(
        credentialsId: 'credentials-id',
        usernameVariable: 'USER',
        passwordVariable: 'PASS'
    )
]) {
    sh './deploy.sh --user $USER --pass $PASS'
}
```

#### SSH Agent Plugin

For SSH key credentials:

```groovy
sshagent(['deployment-ssh-key']) {
    sh '''
        ssh user@server.example.com './deploy.sh'
    '''
}
```

### Docker Integration

Using credentials for Docker registry authentication:

```groovy
pipeline {
    agent any
    
    stages {
        stage('Build and Push') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )
                ]) {
                    sh '''
                        echo $DOCKER_PASS | docker login -u $DOCKER_USER --password-stdin
                        docker build -t myapp:latest .
                        docker push myapp:latest
                    '''
                }
            }
        }
    }
}
```

### Kubernetes Integration

Using credentials for Kubernetes deployments:

```groovy
pipeline {
    agent any
    
    stages {
        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([
                    file(credentialsId: 'k8s-config', variable: 'KUBECONFIG')
                ]) {
                    sh '''
                        kubectl --kubeconfig=$KUBECONFIG apply -f deployment.yaml
                        kubectl --kubeconfig=$KUBECONFIG rollout status deployment/myapp
                    '''
                }
            }
        }
    }
}
```

### AWS Integration

Using credentials for AWS CLI:

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
                        aws cloudfront create-invalidation --distribution-id ID
                    '''
                }
            }
        }
    }
}
```

## Reference

### Complete Configuration Example

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
  # API Keys
  - name: github_token
    kind: static
    config:
      default: ${GITHUB_TOKEN}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: github-api-token
          description: GitHub API Token
          credential_type: string

  # Database Credentials
  - name: postgres_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: postgres-credentials
          description: PostgreSQL Database
          credential_type: username_password
          username: postgres

  # Secret Files
  - name: kubeconfig
    kind: static
    config:
      default: ${KUBECONFIG_CONTENT}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: k8s-config
          description: Kubernetes Configuration
          credential_type: secret_file
          filename: kubeconfig.yaml

  # Folder-Scoped
  - name: prod_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key
          description: Production API Key
          credential_type: string
          folder: production
          domain: _
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `JENKINS_TOKEN` | Jenkins API token for authentication | `11a1b2c3d4e5f6g7h8i9j0` |
| `JENKINS_USERNAME` | Jenkins username (token owner) | `admin` |
| `JENKINS_URL` | Jenkins server URL | `https://jenkins.example.com` |

### Supported Credential Types

| Type | Value | Description |
|------|-------|-------------|
| Secret Text | `string` | Single text value (API keys, tokens, passwords) |
| Username/Password | `username_password` | Username and password pair |
| Secret File | `secret_file` | File contents (certificates, keys, configs) |

### API Token Scopes

Jenkins API tokens have the same permissions as the user who created them:

- Full API access
- Same job permissions
- Same credential permissions
- Can be revoked independently

### Related Tools

- [python-jenkins](https://github.com/pycontribs/python-jenkins) - Python library for Jenkins API
- [jenkins-job-builder](https://docs.openstack.org/infra/jenkins-job-builder/) - Jenkins job configuration
- [jenkins-cli](https://www.jenkins.io/doc/book/managing/cli/) - Jenkins command-line interface
