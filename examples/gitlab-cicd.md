# GitLab CI/CD Integration Example

This example demonstrates how to use SecretZero to manage GitLab CI/CD variables.

## Configuration

```yaml
version: '1.0'

variables:
  gitlab_project: mygroup/myproject
  gitlab_group: mygroup
  environment_scope: production

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}
        # Optional: custom GitLab instance URL
        # url: https://gitlab.mycompany.com

secrets:
  # API Key for external service
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
      
      # Store as GitLab project variable
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          masked: true  # Hide in job logs
          protected: false  # Available to all branches
          environment_scope: ${environment_scope}
          variable_type: env_var

  # Database credentials
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      # Store as protected GitLab variable (only available on protected branches)
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          masked: true
          protected: true
          environment_scope: production

  # Shared secret across multiple projects
  - name: shared_secret
    kind: random_string
    config:
      length: 64
    targets:
      # Store as group-level variable
      - provider: gitlab
        kind: gitlab_variable
        config:
          group: ${gitlab_group}
          masked: true
          protected: false
          environment_scope: "*"  # All environments

  # File-type variable for configuration
  - name: service_account_key
    kind: static
    config:
      default: |
        {
          "type": "service_account",
          "project_id": "my-project"
        }
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_type: file  # Creates a file in the CI job
          masked: false  # JSON cannot be masked
```

## Setup

1. **Generate a GitLab Personal Access Token**:
   - Go to GitLab → User Settings → Access Tokens
   - Create a token with the following scopes:
     - `api` (required for reading/writing variables)
   
2. **Export the token as an environment variable**:
   ```bash
   export GITLAB_TOKEN=glpat-your_token_here
   ```

3. **Test provider connectivity**:
   ```bash
   secretzero test -f examples/gitlab-cicd.yml
   ```

4. **Sync secrets (dry-run first)**:
   ```bash
   secretzero sync -f examples/gitlab-cicd.yml --dry-run
   ```

5. **Sync secrets for real**:
   ```bash
   secretzero sync -f examples/gitlab-cicd.yml
   ```

## Features

- **Project Variables**: Variables scoped to a specific project
- **Group Variables**: Variables shared across all projects in a group
- **Environment Scoping**: Restrict variables to specific environments
- **Protected Variables**: Only available on protected branches/tags
- **Masked Variables**: Hidden in job logs
- **File Variables**: Variables written to temporary files (useful for credentials)

## Using Variables in GitLab CI/CD

Once synced, your variables are available in `.gitlab-ci.yml`:

```yaml
deploy:
  stage: deploy
  environment:
    name: production
  script:
    - echo "Using API_KEY: $API_KEY"
    - echo "Database password: $DATABASE_PASSWORD"
    # File variables are available as paths
    - cat $SERVICE_ACCOUNT_KEY
  only:
    - main
```

## Variable Types

### Environment Variables (`env_var`)
Standard environment variables accessible via `$VARIABLE_NAME`:

```yaml
config:
  variable_type: env_var
```

### File Variables (`file`)
Variables written to temporary files, useful for credentials:

```yaml
config:
  variable_type: file  # Creates file at path in $VARIABLE_NAME
```

## Environment Scoping

Restrict variables to specific environments:

```yaml
config:
  environment_scope: production  # Only in production
  # environment_scope: staging    # Only in staging
  # environment_scope: "*"        # All environments (default)
```

## Protection Levels

### Protected Variables
Only available on protected branches and tags:

```yaml
config:
  protected: true  # Only on protected branches
```

### Masked Variables
Hidden in job logs (must meet regex pattern):

```yaml
config:
  masked: true  # Hidden in logs
```

**Note**: Masked variables must:
- Be at least 8 characters
- Not have spaces
- Not have special regex characters

## Group vs Project Variables

### Project Variables
Scoped to a single project:

```yaml
targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      project: mygroup/myproject
```

### Group Variables
Available to all projects in a group:

```yaml
targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      group: mygroup
```

## Advanced: Multiple Environments

Manage secrets for different environments:

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      # Development environment
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          environment_scope: development
          protected: false
      
      # Staging environment
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          environment_scope: staging
          protected: true
      
      # Production environment
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          environment_scope: production
          protected: true
```

## Security Best Practices

1. **Use masked variables** for all sensitive data
2. **Use protected variables** for production secrets
3. **Scope variables to environments** to prevent accidental exposure
4. **Use group variables** for shared secrets across projects
5. **Rotate secrets regularly** using SecretZero
6. **Audit variable access** through GitLab's audit events
7. **Never commit** the GITLAB_TOKEN to your repository

## Troubleshooting

### Authentication Failed
- Verify your GITLAB_TOKEN is valid and not expired
- Ensure your token has the `api` scope
- For self-hosted GitLab, ensure the `url` is correct

### Permission Denied
- Project variables require at least Maintainer role
- Group variables require at least Owner role
- Check your access level in project/group settings

### Variable Not Appearing in Jobs
- Verify the environment scope matches your job environment
- Protected variables only work on protected branches
- Check project/group settings → CI/CD → Variables

### Masked Variable Rejected
- Ensure the value is at least 8 characters
- Remove spaces or special characters
- Consider using file variables for complex formats
