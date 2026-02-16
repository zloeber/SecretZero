# Jenkins Credentials Integration Example

This example demonstrates how to use SecretZero to manage Jenkins credentials.

## Configuration

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
  # Simple string credential (API key)
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      # Store in local .env for development
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
      
      # Store as Jenkins string credential
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: api-key-prod
          description: Production API Key
          credential_type: string

  # Username/Password credential for database
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

  # Secret for AWS credentials
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
          description: AWS Secret Access Key
          credential_type: string

  # SSH key (stored as string credential)
  - name: deploy_key
    kind: static
    config:
      default: ${DEPLOY_SSH_KEY}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: deploy-ssh-key
          description: Deployment SSH Key
          credential_type: string
```

## Setup

1. **Generate a Jenkins API Token**:
   - Go to Jenkins → Your Username → Configure
   - Add New Token → Generate
   - Copy the generated token
   
2. **Export required environment variables**:
   ```bash
   export JENKINS_TOKEN=your_jenkins_token_here
   export JENKINS_USERNAME=admin
   ```

3. **Test provider connectivity**:
   ```bash
   secretzero test -f examples/jenkins-credentials.yml
   ```

4. **Sync secrets (dry-run first)**:
   ```bash
   secretzero sync -f examples/jenkins-credentials.yml --dry-run
   ```

5. **Sync secrets for real**:
   ```bash
   secretzero sync -f examples/jenkins-credentials.yml
   ```

## Credential Types

### String Credentials
Store simple text secrets (API keys, tokens):

```yaml
config:
  credential_id: my-secret
  credential_type: string
  description: My API Key
```

### Username/Password Credentials
Store username and password pairs:

```yaml
config:
  credential_id: db-creds
  credential_type: username_password
  username: dbuser
  description: Database Login
```

## Credential Scopes

### Global Credentials
Available to all Jenkins jobs (default):

```yaml
config:
  credential_id: my-secret
  # No domain specified = global scope
```

### Folder-Specific Credentials
Scoped to a specific Jenkins folder:

```yaml
config:
  credential_id: my-secret
  folder: my-folder-name
  domain: _  # Default domain
```

## Using Credentials in Jenkins

Once synced, credentials can be used in Jenkins pipelines:

### Declarative Pipeline

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
                    )
                ]) {
                    sh '''
                        echo "Deploying with API key: $API_KEY"
                        echo "DB User: $DB_USER"
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
    withCredentials([string(credentialsId: 'api-key-prod', variable: 'API_KEY')]) {
        sh 'echo "API Key: $API_KEY"'
    }
    
    withCredentials([
        usernamePassword(
            credentialsId: 'db-credentials',
            usernameVariable: 'USER',
            passwordVariable: 'PASS'
        )
    ]) {
        sh 'echo "User: $USER"'
    }
}
```

### Freestyle Jobs

1. Go to job configuration
2. Under "Build Environment", check "Use secret text(s) or file(s)"
3. Add binding for your credential
4. Use the credential in build steps via environment variable

## Advanced Examples

### Multiple Environment Credentials

Manage credentials for different environments:

```yaml
secrets:
  # Development API Key
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

  # Production API Key
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
```

### Structured Configuration

For complex secrets, use JSON or YAML:

```yaml
secrets:
  - name: service_config
    kind: static
    config:
      default: |
        {
          "service": "api",
          "endpoint": "https://api.example.com",
          "timeout": 30
        }
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: service-config
          credential_type: string
```

## Credential Management

### List Credentials

View all credentials via Jenkins UI:
1. Jenkins → Manage Jenkins → Manage Credentials
2. Click on domain to see credentials
3. Credentials created by SecretZero will have the specified ID and description

### Update Credentials

SecretZero automatically updates existing credentials:
```bash
# Modify Secretfile.yml
# Run sync to update
secretzero sync -f examples/jenkins-credentials.yml
```

### Credential Rotation

Use SecretZero's rotation features:

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

## Security Best Practices

1. **Use credential IDs consistently** across pipelines
2. **Limit credential scope** to specific folders when possible
3. **Rotate credentials regularly** using SecretZero
4. **Use the lockfile** to track credential creation and updates
5. **Never commit** JENKINS_TOKEN to your repository
6. **Use Jenkins RBAC** to control credential access
7. **Audit credential usage** through Jenkins logs
8. **Use username/password credentials** instead of string credentials for login pairs

## Troubleshooting

### Authentication Failed
- Verify your JENKINS_TOKEN is valid
- Ensure your username matches the token owner
- Check Jenkins is accessible at the specified URL

### Permission Denied
- Ensure your user has "Credentials" → "Create" permission
- For global credentials, need "Overall" → "Administer" permission
- For folder credentials, need folder-level permissions

### Credential Not Appearing
- Check Jenkins → Manage Credentials → (global) or specific folder
- Verify the credential_id matches what you're using in pipelines
- Credentials may be in a different domain or folder

### Groovy Script Execution Failed
- Ensure "Script Security" plugin is installed
- Check Jenkins → Manage Jenkins → Script Approval
- Some Jenkins instances disable groovy script execution
- If groovy fails, the tool will use XML API as fallback

## Integration with Plugins

### AWS Credentials Plugin
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
          # password will be secret key
```

### SSH Credentials Plugin
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
          credential_type: string
```

### Docker Credentials
```yaml
secrets:
  - name: docker_password
    kind: static
    config:
      default: ${DOCKER_PASSWORD}
    targets:
      - provider: jenkins
        kind: jenkins_credential
        config:
          credential_id: dockerhub
          credential_type: username_password
          username: ${DOCKER_USERNAME}
```
