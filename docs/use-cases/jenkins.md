# Jenkins Integration

## Problem Statement

Managing credentials in Jenkins presents unique challenges:

- Manual credential creation through Jenkins UI is time-consuming
- Difficult to track which credentials exist and their purpose
- No standardized approach to credential lifecycle management
- Synchronizing credentials across Jenkins instances requires manual work
- Lack of audit trail for credential creation and rotation

**SecretZero solves this** by automating Jenkins credential provisioning with declarative configuration, supporting various credential types (string, username/password, SSH keys, certificates).

## Prerequisites

- SecretZero installed with Jenkins support: `pip install secretzero[cicd]`
- Jenkins API Token
- Jenkins credentials plugin installed (typically included by default)
- Admin or credentials create/update permissions

## Authentication Setup

### 1. Generate Jenkins API Token

1. Log in to Jenkins
2. Click your username (top right) → Configure
3. Scroll to "API Token" section
4. Click "Add new Token" → Generate
5. Copy the generated token

### 2. Configure Environment

```bash
export JENKINS_URL=https://jenkins.example.com
export JENKINS_USERNAME=admin
export JENKINS_TOKEN=your_jenkins_api_token_here
```

## Configuration

### Basic Credentials

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: my-application
  owner: devops-team

variables:
  jenkins_url: ${JENKINS_URL}
  jenkins_user: ${JENKINS_USERNAME}

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: ${jenkins_url}
        username: ${jenkins_user}
        token: ${JENKINS_TOKEN}

secrets:
  # String credential (API key)
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      # Local development
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
      
      # Jenkins string credential
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-prod
          description: Production API Key
          credential_type: string

  # Username/Password credential
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
          description: Database Credentials
          credential_type: username_password
          username: dbuser

  # Secret text (similar to string)
  - name: jwt_secret
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: jwt-secret
          description: JWT Signing Secret
          credential_type: secret_text
```

### SSH Key Credentials

```yaml
secrets:
  - name: deploy_ssh_key
    kind: ssh_keypair
    config:
      key_type: rsa
      key_size: 4096
    targets:
      # Store private key in Jenkins
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: deploy-ssh-key
          description: Deployment SSH Key
          credential_type: ssh_username_private_key
          username: deploy
          passphrase: ""  # Optional passphrase
      
      # Store public key locally
      - provider: local
        kind: file
        config:
          path: deploy_key.pub
          format: raw
          extract_field: public_key
```

### Certificate Credentials

```yaml
secrets:
  - name: client_certificate
    kind: certificate
    config:
      cert_type: client
      key_size: 2048
      common_name: client.example.com
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: client-cert
          description: Client Certificate
          credential_type: certificate
          password: ${CERT_PASSWORD}
```

## Step-by-Step Instructions

### 1. Validate Configuration

```bash
secretzero validate

# Expected output:
# ✓ Configuration is valid
# ✓ Found 3 secrets
# ✓ Jenkins provider configured correctly
```

### 2. Test Provider Connectivity

```bash
secretzero test

# Expected output:
# ✓ Testing Jenkins provider...
# ✓ Authentication successful
# ✓ Jenkins version: 2.401.1
# ✓ Credentials plugin available
# ✓ All providers ready
```

### 3. Preview Changes

```bash
secretzero sync --dry-run

# Expected output:
# [DRY RUN] Would create:
#   ✓ api_key → Jenkins Credential (api-key-prod) [string]
#   ✓ database_password → Jenkins Credential (db-credentials) [username_password]
#   ✓ jwt_secret → Jenkins Credential (jwt-secret) [secret_text]
```

### 4. Sync Credentials to Jenkins

```bash
secretzero sync

# Expected output:
# ✓ Generated api_key
# ✓ Created Jenkins Credential: api-key-prod (string)
# ✓ Generated database_password
# ✓ Created Jenkins Credential: db-credentials (username_password)
# ✓ Generated jwt_secret
# ✓ Created Jenkins Credential: jwt-secret (secret_text)
# ✓ Updated .gitsecrets.lock
```

### 5. Verify in Jenkins

Navigate to Jenkins:
- Dashboard → Manage Jenkins → Manage Credentials
- Click on "(global)" domain
- Verify your credentials appear in the list

## Using Credentials in Jenkins Pipelines

### Declarative Pipeline

```groovy
pipeline {
    agent any
    
    environment {
        // Bind string credential to environment variable
        API_KEY = credentials('api-key-prod')
    }
    
    stages {
        stage('Deploy') {
            steps {
                // API_KEY is automatically available
                sh 'echo "API Key: $API_KEY"'
                
                // Username/Password credential
                withCredentials([
                    usernamePassword(
                        credentialsId: 'db-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASS'
                    )
                ]) {
                    sh '''
                        echo "Database User: $DB_USER"
                        ./deploy.sh
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
    stage('Deploy') {
        // String credential
        withCredentials([string(credentialsId: 'api-key-prod', variable: 'API_KEY')]) {
            sh "echo API Key: $API_KEY"
        }
        
        // Username/Password credential
        withCredentials([
            usernamePassword(
                credentialsId: 'db-credentials',
                usernameVariable: 'DB_USER',
                passwordVariable: 'DB_PASS'
            )
        ]) {
            sh './connect-database.sh $DB_USER $DB_PASS'
        }
        
        // SSH key credential
        withCredentials([
            sshUserPrivateKey(
                credentialsId: 'deploy-ssh-key',
                keyFileVariable: 'SSH_KEY',
                usernameVariable: 'SSH_USER'
            )
        ]) {
            sh 'ssh -i $SSH_KEY $SSH_USER@server.example.com "deploy.sh"'
        }
    }
}
```

### Freestyle Job Configuration

1. Configure job → Build Environment
2. Enable "Use secret text(s) or file(s)"
3. Add binding:
   - **Secret text**: Select credential → Variable name
   - **Username and password**: Select credential → Username/Password variables
4. Use in build steps via environment variables

## Advanced Scenarios

### Multi-Instance Setup

Sync credentials across multiple Jenkins instances:

```yaml
version: '1.0'

variables:
  jenkins_prod_url: https://jenkins-prod.example.com
  jenkins_staging_url: https://jenkins-staging.example.com

providers:
  jenkins_prod:
    kind: jenkins
    auth:
      kind: token
      config:
        url: ${jenkins_prod_url}
        username: ${JENKINS_USERNAME}
        token: ${JENKINS_PROD_TOKEN}
  
  jenkins_staging:
    kind: jenkins
    auth:
      kind: token
      config:
        url: ${jenkins_staging_url}
        username: ${JENKINS_USERNAME}
        token: ${JENKINS_STAGING_TOKEN}

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      # Production instance
      - provider: jenkins_prod
        kind: jenkins_credential
        config:
          credential_id: api-key
          description: API Key
          credential_type: string
      
      # Staging instance
      - provider: jenkins_staging
        kind: jenkins_credential
        config:
          credential_id: api-key
          description: API Key
          credential_type: string
```

### Folder-Scoped Credentials

Store credentials in specific Jenkins folders:

```yaml
secrets:
  - name: project_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key
          description: Project API Key
          credential_type: string
          folder: "MyProject/Production"  # Folder path
```

### Credential Rotation Pipeline

Automate credential rotation:

```groovy
// Jenkinsfile
pipeline {
    agent any
    
    triggers {
        // Run every 90 days
        cron('0 0 */90 * *')
    }
    
    stages {
        stage('Rotate Credentials') {
            steps {
                sh '''
                    pip install secretzero[cicd]
                    secretzero rotate --force
                    secretzero sync
                '''
            }
        }
        
        stage('Verify Rotation') {
            steps {
                sh 'secretzero show api_key'
            }
        }
        
        stage('Commit Lockfile') {
            steps {
                sh '''
                    git config user.name "Jenkins Bot"
                    git config user.email "jenkins@example.com"
                    git add .gitsecrets.lock
                    git commit -m "chore: rotate Jenkins credentials"
                    git push origin main
                '''
            }
        }
    }
}
```

### AWS Credentials

Manage AWS access keys in Jenkins:

```yaml
secrets:
  - name: aws_secret_key
    kind: random_string
    config:
      length: 40
      charset: alphanumeric
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: aws-credentials
          description: AWS Credentials
          credential_type: aws_credentials
          access_key: ${AWS_ACCESS_KEY_ID}
          # secret_key will be generated
```

## Best Practices

### 1. Use Descriptive Credential IDs

Follow naming conventions:

```yaml
config:
  credential_id: prod-api-key  # Clear and environment-specific
  description: Production API Key for External Service
```

### 2. Scope Credentials Appropriately

Use folder-scoped credentials for project isolation:

```yaml
config:
  folder: "Project/Environment"  # Restricts access
```

### 3. Rotate Credentials Regularly

Implement rotation policies:

```yaml
secrets:
  - name: api_key
    kind: random_string
    rotation_period: 90d
    config:
      length: 32
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key
```

### 4. Track Changes in Lockfile

Commit lockfile for audit trail:

```bash
git add .gitsecrets.lock
git commit -m "chore: update Jenkins credentials"
```

### 5. Use Appropriate Credential Types

Match credential type to use case:
- **String/Secret Text**: API keys, tokens
- **Username/Password**: Database credentials, service accounts
- **SSH Key**: SSH access, Git over SSH
- **Certificate**: TLS client certificates
- **File**: Configuration files, service account keys

## Troubleshooting

### Authentication Failed

**Problem**: `Error: Jenkins authentication failed`

**Solutions**:

```bash
# Verify environment variables
echo $JENKINS_URL
echo $JENKINS_USERNAME
echo $JENKINS_TOKEN

# Test authentication manually
curl -u "$JENKINS_USERNAME:$JENKINS_TOKEN" \
  "$JENKINS_URL/api/json"

# Regenerate API token
# Jenkins → User → Configure → API Token → Add new Token
```

### Permission Denied

**Problem**: `Error: You do not have permission to create credentials`

**Solutions**:

- Requires **Administer** or **Credentials → Create** permission
- Check permissions:
  - Manage Jenkins → Manage Users → [Your User] → Configure
- Or contact Jenkins administrator for permission grant

### Credential Not Appearing in Job

**Problem**: Job can't find the credential

**Solutions**:

```groovy
// 1. Verify credential ID matches exactly
withCredentials([string(credentialsId: 'api-key-prod', variable: 'KEY')]) {
    // Must match Jenkins credential ID
}

// 2. Check credential scope (global vs folder)
// Credentials in folders only available to jobs in that folder

// 3. Verify credential type matches usage
withCredentials([string(...)]) // For string/secret_text
withCredentials([usernamePassword(...)]) // For username_password
withCredentials([sshUserPrivateKey(...)]) // For SSH keys
```

### Credentials Plugin Not Found

**Problem**: `Error: Credentials plugin not available`

**Solutions**:

```bash
# Install credentials plugin
# Manage Jenkins → Manage Plugins → Available
# Search for "Credentials Plugin" and install

# Or use Jenkins CLI
java -jar jenkins-cli.jar -s $JENKINS_URL \
  install-plugin credentials \
  -username $JENKINS_USERNAME \
  -password $JENKINS_TOKEN
```

### Connection Timeout

**Problem**: `Error: Connection to Jenkins timed out`

**Solutions**:

```bash
# Check Jenkins URL is accessible
curl -I $JENKINS_URL

# For self-hosted Jenkins, verify network access
ping jenkins.example.com

# Check firewall rules allow access on Jenkins port (default 8080)

# For HTTPS, verify certificate
curl -v https://jenkins.example.com
```

## Complete Example

Full production-ready configuration:

```yaml
version: '1.0'

metadata:
  project: production-app
  owner: devops-team
  compliance:
    - soc2

variables:
  jenkins_url: https://jenkins.example.com

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: ${jenkins_url}
        username: ${JENKINS_USERNAME}
        token: ${JENKINS_TOKEN}

policies:
  credential_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true

secrets:
  # Database credentials
  - name: database_creds
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: prod-db-creds
          description: Production Database Credentials
          credential_type: username_password
          username: prod_user

  # API keys
  - name: stripe_api_key
    kind: static
    rotation_period: 90d
    config:
      default: ${STRIPE_API_KEY}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: stripe-api-key
          description: Stripe API Key
          credential_type: secret_text

  # SSH deployment key
  - name: deploy_key
    kind: ssh_keypair
    rotation_period: 180d
    config:
      key_type: ed25519
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: deploy-ssh-key
          description: Deployment SSH Key
          credential_type: ssh_username_private_key
          username: deploy

  # AWS credentials
  - name: aws_secret
    kind: random_string
    rotation_period: 90d
    config:
      length: 40
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: aws-credentials
          description: AWS Credentials
          credential_type: aws_credentials
          access_key: ${AWS_ACCESS_KEY_ID}
```

Deploy:

```bash
# Validate
secretzero validate

# Check compliance
secretzero policy

# Preview
secretzero sync --dry-run

# Deploy
secretzero sync

# Verify in Jenkins UI
# Manage Jenkins → Manage Credentials → (global)
```

## Next Steps

- **[GitHub Actions](github-actions.md)** - GitHub integration
- **[GitLab CI/CD](gitlab-cicd.md)** - GitLab integration
- **[Multi-Cloud Setup](multi-cloud.md)** - Sync to cloud providers
