# Local Development with SecretZero

## Problem Statement

Developers often struggle with setting up local development environments due to:

- Manual copying of `.env` files from teammates
- Unclear which secrets are needed for the project
- Inconsistent secret values between team members
- Secrets committed accidentally to version control
- Time-consuming onboarding for new developers

**SecretZero solves this** by providing a declarative configuration that generates all necessary secrets automatically, creating production-like local environments in seconds.

## Prerequisites

- SecretZero installed (`pip install secretzero`)
- A project directory
- No cloud provider accounts needed for this use case

## Configuration

Create a `Secretfile.yml` in your project root:

```yaml
version: '1.0'

metadata:
  project: my-application
  owner: development-team
  description: Local development secrets

variables:
  environment: local
  app_name: myapp

secrets:
  # Database password
  - name: database_password
    kind: random_password
    config:
      length: 16
      special: false  # Easier for local development
      upper: true
      lower: true
      number: true
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # API key for external service
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: hex
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # JWT secret for authentication
  - name: jwt_secret
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # Application settings as JSON
  - name: app_config
    kind: templates.app_settings

templates:
  app_settings:
    description: Application configuration
    fields:
      database_url:
        generator:
          kind: static
          config:
            default: postgresql://user:${database_password}@localhost:5432/myapp_dev
      redis_url:
        generator:
          kind: static
          config:
            default: redis://localhost:6379/0
      debug:
        generator:
          kind: static
          config:
            default: "true"
      log_level:
        generator:
          kind: static
          config:
            default: DEBUG
    targets:
      - provider: local
        kind: file
        config:
          path: config.json
          format: json
```

## Step-by-Step Instructions

### 1. Initialize Your Project

Create the `Secretfile.yml` in your project root:

```bash
# Option 1: Create from template
secretzero create --template-type basic

# Option 2: Create from scratch using the configuration above
```

### 2. Validate Configuration

Ensure your configuration is valid:

```bash
secretzero validate

# Expected output:
# ✓ Configuration is valid
# ✓ Found 4 secrets
# ✓ All providers configured correctly
```

### 3. Preview Secret Generation

See what will be created without making changes:

```bash
secretzero sync --dry-run

# Expected output:
# [DRY RUN] Would create:
#   - database_password → .env (DATABASE_PASSWORD)
#   - api_key → .env (API_KEY)
#   - jwt_secret → .env (JWT_SECRET)
#   - app_config → config.json
```

### 4. Generate Secrets

Create the secrets and files:

```bash
secretzero sync

# Expected output:
# ✓ Generated database_password
# ✓ Wrote to .env (DATABASE_PASSWORD)
# ✓ Generated api_key
# ✓ Wrote to .env (API_KEY)
# ✓ Generated jwt_secret
# ✓ Wrote to .env (JWT_SECRET)
# ✓ Generated app_config
# ✓ Wrote to config.json
# ✓ Updated .gitsecrets.lock
```

### 5. Verify Generated Files

Check the created files:

```bash
# View .env file
cat .env

# Expected content:
# DATABASE_PASSWORD=Abc123XyzDefGhi4
# API_KEY=a3f5d8c9e2b4f7a1c8e5d2b9f4a7c3e1
# JWT_SECRET=K8pL2mN9qR5tV3xZ7bD4fG8hJ1kM6nP0

# View config.json
cat config.json

# Expected JSON structure with database_url, redis_url, debug, log_level
```

### 6. Add to .gitignore

Protect your secrets from accidental commits:

```bash
cat >> .gitignore << EOF
# SecretZero generated files
.env
config.json

# Keep the lockfile for tracking
# .gitsecrets.lock should be committed
EOF
```

### 7. Share with Team

Commit the `Secretfile.yml` and `.gitsecrets.lock`:

```bash
git add Secretfile.yml .gitsecrets.lock .gitignore
git commit -m "Add SecretZero configuration for local development"
git push
```

### 8. Team Member Onboarding

New team members can now set up their environment:

```bash
# Clone repository
git clone <repository-url>
cd <project>

# Install SecretZero
pip install secretzero

# Generate local secrets
secretzero sync

# Start developing!
```

## Advanced Usage

### Multiple Environment Files

Support different environments:

```yaml
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 16
    targets:
      # Development environment
      - provider: local
        kind: file
        config:
          path: .env.development
          format: dotenv
          merge: true
      
      # Testing environment
      - provider: local
        kind: file
        config:
          path: .env.test
          format: dotenv
          merge: true
```

### Manual Secret Input

For secrets that can't be generated (like third-party API keys):

```yaml
secrets:
  - name: stripe_api_key
    kind: static
    config:
      # Prompt user for input if not in environment
      default: ${STRIPE_API_KEY}
      prompt: true
      prompt_message: "Enter Stripe API Key (from https://dashboard.stripe.com/apikeys)"
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
```

Usage:

```bash
# SecretZero will prompt for the value
secretzero sync

# Or provide via environment variable
export STRIPE_API_KEY=sk_test_...
secretzero sync
```

### Docker Compose Integration

Generate `.env` file for Docker Compose:

```yaml
secrets:
  - name: postgres_password
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
          key_name: POSTGRES_PASSWORD

  - name: postgres_user
    kind: static
    config:
      default: appuser
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
          key_name: POSTGRES_USER
```

Then use in `docker-compose.yml`:

```yaml
version: '3.8'
services:
  db:
    image: postgres:14
    env_file: .env
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

## Best Practices

### 1. Keep Secrets Out of Git

Always add generated files to `.gitignore`:

```gitignore
# SecretZero generated secrets
.env
.env.*
config.json
secrets.json

# But commit the lockfile for tracking
# .gitsecrets.lock
```

### 2. Use Idempotent Operations

SecretZero is idempotent by default. Running `sync` multiple times won't regenerate secrets:

```bash
# First run: generates secrets
secretzero sync

# Second run: uses existing secrets from lockfile
secretzero sync
# ✓ Skipped (already exists in lockfile)
```

### 3. Document Required Secrets

Use the metadata in your Secretfile:

```yaml
metadata:
  description: |
    Required secrets for local development:
    - database_password: PostgreSQL database password
    - api_key: External API authentication key
    - jwt_secret: JWT token signing secret
```

### 4. Use Secret Templates for Complex Configurations

Group related secrets:

```yaml
templates:
  database_config:
    description: Complete database configuration
    fields:
      host:
        generator:
          kind: static
          config:
            default: localhost
      port:
        generator:
          kind: static
          config:
            default: "5432"
      username:
        generator:
          kind: static
          config:
            default: appuser
      password:
        generator:
          kind: random_password
          config:
            length: 16
```

### 5. Merge with Existing .env Files

Use `merge: true` to preserve existing environment variables:

```yaml
targets:
  - provider: local
    kind: file
    config:
      path: .env
      format: dotenv
      merge: true  # Preserves existing variables
```

## Troubleshooting

### Secret Already Exists Error

**Problem**: SecretZero refuses to overwrite existing secrets.

**Solution**: This is intentional. To regenerate:

```bash
# Option 1: Use force flag
secretzero sync --force

# Option 2: Remove lockfile entry
secretzero show database_password --delete

# Option 3: Remove entire lockfile (regenerates everything)
rm .gitsecrets.lock
secretzero sync
```

### Permission Denied Writing to .env

**Problem**: Cannot write to `.env` file.

**Solution**:

```bash
# Check file permissions
ls -la .env

# Fix permissions
chmod 644 .env

# Or remove and regenerate
rm .env
secretzero sync
```

### Secrets Not Appearing in Application

**Problem**: Application doesn't see environment variables.

**Solution**:

```bash
# Ensure .env file exists
cat .env

# Check your application loads .env files
# Many frameworks require explicit configuration

# For Node.js
npm install dotenv
# Add to app: require('dotenv').config()

# For Python
pip install python-dotenv
# Add to app: from dotenv import load_dotenv; load_dotenv()
```

### Lockfile Merge Conflicts

**Problem**: Git merge conflicts in `.gitsecrets.lock`.

**Solution**:

```bash
# Accept either version of the lockfile
git checkout --theirs .gitsecrets.lock
# or
git checkout --ours .gitsecrets.lock

# Regenerate secrets to ensure consistency
secretzero sync

# Commit the result
git add .gitsecrets.lock
git commit -m "Resolve lockfile conflict"
```

## Real-World Example

Here's a complete example for a typical web application:

```yaml
version: '1.0'

metadata:
  project: webapp
  owner: backend-team

variables:
  db_host: localhost
  db_port: 5432
  db_name: webapp_dev

secrets:
  # Database credentials
  - name: db_password
    kind: random_password
    config:
      length: 16
      special: false
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
          key_name: DATABASE_PASSWORD

  # Redis password
  - name: redis_password
    kind: random_password
    config:
      length: 16
      special: false
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
          key_name: REDIS_PASSWORD

  # Session secret
  - name: session_secret
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
          key_name: SESSION_SECRET

  # JWT signing key
  - name: jwt_key
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
          key_name: JWT_SECRET_KEY

  # Complete application config
  - name: app_settings
    kind: templates.full_config

templates:
  full_config:
    description: Complete application configuration
    fields:
      database_url:
        generator:
          kind: static
          config:
            default: "postgresql://postgres:${db_password}@${db_host}:${db_port}/${db_name}"
      redis_url:
        generator:
          kind: static
          config:
            default: "redis://:${redis_password}@localhost:6379/0"
      allowed_hosts:
        generator:
          kind: static
          config:
            default: "localhost,127.0.0.1"
      debug:
        generator:
          kind: static
          config:
            default: "true"
    targets:
      - provider: local
        kind: file
        config:
          path: config/settings.json
          format: json
```

Run it:

```bash
secretzero sync
# Generates complete .env and config/settings.json
# Team members can immediately start developing
```

## Next Steps

- **[GitHub Actions](github-actions.md)** - Add CI/CD secret management
- **[Multi-Cloud Setup](multi-cloud.md)** - Sync secrets to cloud providers
- **[Kubernetes Deployment](kubernetes.md)** - Deploy secrets to Kubernetes clusters
