# Your First Complete Project

This tutorial walks you through building a complete SecretZero project from scratch. You'll create multiple secrets with different generators, manage them across various targets, and learn best practices for production use.

## What You'll Build

By the end of this guide, you'll have:

- A multi-secret configuration managing database credentials, API keys, and SSH keys
- Secrets synchronized to local files and cloud providers
- Rotation policies for compliance
- A lockfile tracking all secret state

## Prerequisites

Before starting, make sure you have:

- SecretZero installed (see [Installation Guide](installation.md))
- Basic understanding of YAML syntax
- (Optional) AWS credentials for cloud storage examples

## Project Structure

We'll build a project with this structure:

```
my-project/
├── Secretfile.yml         # Secret definitions
├── .gitsecrets.lock       # Lockfile (auto-generated)
├── .env                   # Local development secrets
├── config/
│   ├── database.json      # Database configuration
│   └── ssh-keys/          # SSH key storage
└── .gitignore             # Exclude sensitive files
```

## Step 1: Initialize Your Project

Create a new directory and initialize:

```bash
mkdir my-project
cd my-project
secretzero create
```

This creates a basic `Secretfile.yml`. We'll replace it with our complete configuration.

## Step 2: Define Project Metadata

Start by adding metadata to track your project:

```yaml
version: "1.0"

metadata:
  name: my-app
  description: Production secrets for My Application
  owner: platform-team
  environments:
    - development
    - staging
    - production
  compliance:
    - soc2
```

!!! info "Compliance Tracking"
    Adding compliance standards (SOC2, ISO27001) automatically enables policy checks for those frameworks.

## Step 3: Configure Variables

Variables allow dynamic configuration across environments:

```yaml
variables:
  environment: development
  aws_region: us-east-1
  db_host: localhost
  db_port: "5432"
```

These can be overridden at runtime:

```bash
export ENVIRONMENT=production
export DB_HOST=prod-db.example.com
secretzero sync
```

## Step 4: Configure Providers

Define where secrets will be stored:

```yaml
providers:
  # Local provider (always available)
  local:
    kind: local

  # AWS provider for cloud storage
  aws:
    kind: aws
    auth:
      kind: ambient  # Uses IAM roles/credentials
      config:
        region: "{{var.aws_region}}"
```

Test provider connectivity:

```bash
secretzero test
```

Expected output:

```
Testing Provider Connectivity:

  • local: ✓ Local provider (always available)
  • aws: ✓ Connected to AWS (Account: 123456789012)

All provider tests passed!
```

## Step 5: Create Database Credentials

Let's create a complex secret with multiple fields:

```yaml
secrets:
  database_credentials:
    template:
      type: database
      fields:
        - name: username
          generator:
            type: static
            value: myapp_user
        
        - name: password
          generator:
            type: random-password
            length: 32
            include_symbols: true
            include_upper: true
            include_lower: true
            include_numbers: true
        
        - name: host
          generator:
            type: static
            value: "{{var.db_host}}"
        
        - name: port
          generator:
            type: static
            value: "{{var.db_port}}"
        
        - name: database
          generator:
            type: static
            value: myapp_db
    
    rotation:
      period: 90d  # Rotate every 90 days
    
    targets:
      # Local .env file for development
      - type: local-file
        path: .env
        format: dotenv
        merge: true
      
      # JSON config file
      - type: local-file
        path: config/database.json
        format: json
      
      # AWS Secrets Manager
      - type: aws-secretsmanager
        provider: aws
        name: /myapp/database/credentials
        description: Database credentials for My App
```

### Key Features

- **Multiple Fields**: Username, password, host, port, database all in one secret
- **Mixed Generators**: Static values and random password generation
- **Variable Interpolation**: `{{var.db_host}}` pulls from variables
- **Multiple Targets**: Same secret stored in 3 locations
- **Rotation Policy**: Automatic 90-day rotation

## Step 6: Add API Keys

Create API keys for external services:

```yaml
  github_api_token:
    template:
      type: api_key
      fields:
        - name: value
          generator:
            type: random-string
            length: 40
            charset: hex
    
    rotation:
      period: 180d  # Rotate twice a year
    
    targets:
      - type: local-file
        path: .env
        format: dotenv
        key: GITHUB_API_TOKEN
        merge: true
      
      - type: aws-ssm-parameter
        provider: aws
        name: /myapp/github/api_token
        type: SecureString

  slack_webhook:
    template:
      type: webhook
      fields:
        - name: url
          generator:
            type: static
            value: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
    
    one_time: true  # Generate once, don't rotate
    
    targets:
      - type: local-file
        path: .env
        format: dotenv
        key: SLACK_WEBHOOK_URL
        merge: true
```

!!! warning "One-Time Secrets"
    The `one_time: true` flag means the secret is generated once and never rotated. Use for secrets managed externally.

## Step 7: Add SSH Keys

For deployment or git operations:

```yaml
  deployment_ssh_key:
    template:
      type: ssh_key
      fields:
        - name: private_key
          generator:
            type: script
            command: ssh-keygen
            args:
              - -t
              - rsa
              - -b
              - "4096"
              - -f
              - /dev/stdout
              - -N
              - ""
        
        - name: public_key
          generator:
            type: script
            command: ssh-keygen
            args:
              - -y
              - -f
              - config/ssh-keys/id_rsa
    
    rotation:
      period: 365d  # Rotate annually
    
    targets:
      - type: local-file
        path: config/ssh-keys/id_rsa
        format: raw
        key: private_key
      
      - type: local-file
        path: config/ssh-keys/id_rsa.pub
        format: raw
        key: public_key
```

!!! tip "Script Generators"
    The `script` generator type runs external commands to generate secrets. Perfect for SSH keys, certificates, etc.

## Step 8: Configure Policies

Add policies to enforce security standards:

```yaml
policies:
  require_rotation:
    type: rotation
    config:
      require_rotation_period: true
      max_age: 90d
      severity: warning
  
  soc2_compliance:
    type: compliance
    config:
      standard: soc2
      severity: error
  
  cloud_only_production:
    type: access
    config:
      allowed_targets:
        - aws-secretsmanager
        - aws-ssm-parameter
      denied_targets:
        - local-file
      severity: warning
```

## Step 9: Complete Configuration

Here's the complete `Secretfile.yml`:

??? example "Complete Secretfile.yml"
    ```yaml
    version: "1.0"

    metadata:
      name: my-app
      description: Production secrets for My Application
      owner: platform-team
      environments:
        - development
        - staging
        - production
      compliance:
        - soc2

    variables:
      environment: development
      aws_region: us-east-1
      db_host: localhost
      db_port: "5432"

    providers:
      local:
        kind: local
      
      aws:
        kind: aws
        auth:
          kind: ambient
          config:
            region: "{{var.aws_region}}"

    secrets:
      database_credentials:
        template:
          type: database
          fields:
            - name: username
              generator:
                type: static
                value: myapp_user
            - name: password
              generator:
                type: random-password
                length: 32
                include_symbols: true
            - name: host
              generator:
                type: static
                value: "{{var.db_host}}"
            - name: port
              generator:
                type: static
                value: "{{var.db_port}}"
            - name: database
              generator:
                type: static
                value: myapp_db
        rotation:
          period: 90d
        targets:
          - type: local-file
            path: .env
            format: dotenv
            merge: true
          - type: local-file
            path: config/database.json
            format: json
          - type: aws-secretsmanager
            provider: aws
            name: /myapp/database/credentials

      github_api_token:
        template:
          type: api_key
          fields:
            - name: value
              generator:
                type: random-string
                length: 40
                charset: hex
        rotation:
          period: 180d
        targets:
          - type: local-file
            path: .env
            format: dotenv
            key: GITHUB_API_TOKEN
            merge: true
          - type: aws-ssm-parameter
            provider: aws
            name: /myapp/github/api_token
            type: SecureString

      slack_webhook:
        template:
          type: webhook
          fields:
            - name: url
              generator:
                type: static
                value: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
        one_time: true
        targets:
          - type: local-file
            path: .env
            format: dotenv
            key: SLACK_WEBHOOK_URL
            merge: true

    policies:
      require_rotation:
        type: rotation
        config:
          require_rotation_period: true
          max_age: 90d
          severity: warning
      
      soc2_compliance:
        type: compliance
        config:
          standard: soc2
          severity: error
    ```

## Step 10: Validate Configuration

Before generating secrets, validate your configuration:

```bash
secretzero validate
```

Expected output:

```
✓ Configuration is valid
✓ Found 3 secret(s)
✓ Found 2 provider(s)
✓ Found 2 policy(ies)
```

## Step 11: Preview Changes (Dry Run)

Always preview before making changes:

```bash
secretzero sync --dry-run
```

Expected output:

```
[Dry Run] Would generate secret: database_credentials
  ✓ Would generate field: username (static)
  ✓ Would generate field: password (random-password, length=32)
  ✓ Would generate field: host (static)
  ✓ Would generate field: port (static)
  ✓ Would generate field: database (static)
  ✓ Would write to: .env (dotenv format)
  ✓ Would write to: config/database.json (json format)
  ✓ Would write to: AWS Secrets Manager (/myapp/database/credentials)

[Dry Run] Would generate secret: github_api_token
  ✓ Would generate field: value (random-string, length=40)
  ✓ Would write to: .env (dotenv format)
  ✓ Would write to: AWS SSM Parameter (/myapp/github/api_token)

[Dry Run] Would generate secret: slack_webhook
  ✓ Would generate field: url (static)
  ✓ Would write to: .env (dotenv format)

[Dry Run] Summary:
  Secrets to generate: 3
  Secrets to skip: 0
  Targets to update: 7
```

## Step 12: Generate Secrets

Generate and sync all secrets:

```bash
secretzero sync
```

Expected output:

```
✓ Generated secret: database_credentials
  ✓ Generated 5 fields
  ✓ Wrote to: .env
  ✓ Wrote to: config/database.json
  ✓ Wrote to: AWS Secrets Manager

✓ Generated secret: github_api_token
  ✓ Generated field: value
  ✓ Wrote to: .env
  ✓ Wrote to: AWS SSM Parameter

✓ Generated secret: slack_webhook
  ✓ Generated field: url
  ✓ Wrote to: .env

✓ Updated lockfile: .gitsecrets.lock

Summary:
  Generated: 3
  Skipped: 0
  Failed: 0
  Targets updated: 7
```

## Step 13: Verify Generated Secrets

Check the generated files:

```bash
# View .env file
cat .env
```

Output:

```bash
DATABASE_USERNAME=myapp_user
DATABASE_PASSWORD=xK9mP2vL8nQ4tR7wY3sF6hJ1dG5aZ0cE
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_DATABASE=myapp_db
GITHUB_API_TOKEN=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

```bash
# View database config
cat config/database.json
```

Output:

```json
{
  "username": "myapp_user",
  "password": "xK9mP2vL8nQ4tR7wY3sF6hJ1dG5aZ0cE",
  "host": "localhost",
  "port": "5432",
  "database": "myapp_db"
}
```

## Step 14: Check Secret Status

View detailed information about a secret:

```bash
secretzero show database_credentials
```

Output:

```
Secret: database_credentials

 Kind             database                          
 Rotation Period  90d                               
 Generated        Yes                               
 Created          2026-02-16T12:00:00.000000+00:00 
 Updated          2026-02-16T12:00:00.000000+00:00 
 Hash             a1b2c3d4e5f6g7h8...              

Fields:
  username (static): Generated
  password (random-password): Generated
  host (static): Generated
  port (static): Generated
  database (static): Generated

Targets:
  • local / file (.env)
  • local / file (config/database.json)
  • aws / secretsmanager (/myapp/database/credentials)
```

## Step 15: Check Policies

Verify compliance with security policies:

```bash
secretzero policy
```

Expected output:

```
Checking policy compliance...

✓ All secrets pass policy checks

Summary:
  Errors: 0
  Warnings: 0
  Info: 0
```

## Step 16: Check Rotation Status

See which secrets need rotation:

```bash
secretzero rotate --dry-run
```

Output:

```
Checking secrets for rotation...
  ✓  database_credentials: Rotation due in 90 days
  ✓  github_api_token: Rotation due in 180 days
  ℹ️  slack_webhook: one_time secret (rotation disabled)

No secrets need rotation at this time.
```

## Step 17: Setup Git Ignore

Protect your secrets from being committed:

```bash
cat > .gitignore << EOF
# SecretZero generated files
.env
.env.*
config/database.json
config/ssh-keys/

# SecretZero lockfile (contains hashes only - safe to commit)
# .gitsecrets.lock

# But exclude backup copies
.gitsecrets.lock.backup
*.lock.bak
EOF
```

!!! warning "Lockfile Safety"
    The `.gitsecrets.lock` file contains only SHA-256 hashes, not actual secrets. It's safe (and recommended) to commit it for tracking purposes.

## Step 18: Environment-Specific Secrets

Generate secrets for different environments:

```bash
# Development (default)
secretzero sync

# Staging
export ENVIRONMENT=staging
export DB_HOST=staging-db.example.com
secretzero sync --lockfile .gitsecrets-staging.lock

# Production
export ENVIRONMENT=production
export DB_HOST=prod-db.example.com
export AWS_REGION=us-west-2
secretzero sync --lockfile .gitsecrets-production.lock
```

## Common Operations

### Rotate a Specific Secret

```bash
secretzero rotate database_credentials --force
```

### Update an Existing Secret

Change the configuration in `Secretfile.yml`, then:

```bash
secretzero sync --force
```

### Detect Configuration Drift

Check if secrets have been modified outside SecretZero:

```bash
secretzero drift
```

### Override with Environment Variable

Temporarily use a different value:

```bash
export DATABASE_PASSWORD="my-custom-password"
secretzero sync
```

## Best Practices

### 1. Use Rotation Policies

Always specify rotation periods for sensitive secrets:

```yaml
rotation:
  period: 90d  # SOC2 recommends 90 days or less
```

### 2. Multiple Targets for Redundancy

Store critical secrets in multiple locations:

```yaml
targets:
  - type: local-file          # Local development
  - type: aws-secretsmanager  # Production
  - type: vault-kv            # Backup
```

### 3. Use Templates for Complex Secrets

Group related fields in templates:

```yaml
template:
  type: database
  fields:
    - name: username
    - name: password
    - name: host
    - name: port
```

### 4. Leverage Variables

Make configurations reusable across environments:

```yaml
variables:
  environment: "{{env.ENVIRONMENT or 'development'}}"
  db_host: "{{env.DB_HOST or 'localhost'}}"
```

### 5. Test Before Deploying

Always use dry-run mode first:

```bash
secretzero sync --dry-run
secretzero test
```

### 6. Document Your Secrets

Use metadata to track ownership and compliance:

```yaml
metadata:
  name: my-app
  owner: platform-team
  compliance:
    - soc2
    - iso27001
```

## Troubleshooting

### Secret Not Generated

**Issue**: Secret shows as "skipped"

**Solution**: Check if it's a one-time secret already in lockfile:

```bash
secretzero show <secret-name>
```

Use `--force` to regenerate:

```bash
secretzero sync --force
```

### Provider Connection Failed

**Issue**: `aws` provider test fails

**Solution**: Verify AWS credentials:

```bash
aws sts get-caller-identity
export AWS_PROFILE=your-profile
secretzero test
```

### Lockfile Conflicts

**Issue**: Lockfile shows different hash

**Solution**: Check for drift:

```bash
secretzero drift
```

Resync if needed:

```bash
secretzero sync --force
```

## Next Steps

Now that you've built a complete project:

1. **[Understand Core Concepts →](concepts.md)** - Deep dive into SecretZero architecture
2. **[Explore Use Cases →](../use-cases/index.md)** - Real-world examples
3. **[User Guide →](../user-guide/index.md)** - Comprehensive documentation
4. **[API Integration →](../user-guide/api/index.md)** - REST API for automation

## Additional Resources

- [Example Configurations](../examples/index.md)
- [CLI Reference](../reference/cli.md)
- [FAQ](../reference/faq.md)
- [Troubleshooting Guide](../reference/troubleshooting.md)
