# Quick Start

Get started with SecretZero in 5 minutes! This guide will walk you through creating your first secret.

## Prerequisites

Make sure you have SecretZero installed:

```bash
pip install secretzero
```

See the [Installation Guide](installation.md) for more options.

## Step 1: Initialize a Project

Create a new Secretfile in your project directory:

```bash
secretzero create
```

This creates a `Secretfile.yml` with example configuration:

```yaml
version: "1.0"
metadata:
  name: my-project
  description: My first SecretZero project

secrets:
  api_key:
    template:
      type: api_key
      fields:
        - name: value
          generator:
            type: random-string
            length: 32
    targets:
      - type: local-file
        path: .env
        format: dotenv
```

## Step 2: Validate Configuration

Validate your Secretfile:

```bash
secretzero validate
```

Expected output:

```
✓ Configuration is valid
✓ Found 1 secret(s)
✓ Found 1 target(s)
```

## Step 3: Preview Secret Generation

See what would be generated without making changes:

```bash
secretzero sync --dry-run
```

Expected output:

```
[Dry Run] Would generate secret: api_key
  ✓ Would generate field: value (random-string, length=32)
  ✓ Would write to: .env (dotenv format)

[Dry Run] Summary:
  Secrets to generate: 1
  Secrets to skip: 0
  Targets to update: 1
```

## Step 4: Generate the Secret

Generate and sync the secret:

```bash
secretzero sync
```

Expected output:

```
✓ Generated secret: api_key
  ✓ Generated field: value
  ✓ Wrote to: .env
  
✓ Updated lockfile: .gitsecrets.lock

Summary:
  Generated: 1
  Skipped: 0
  Failed: 0
```

## Step 5: Verify the Results

Check the generated secret in your `.env` file:

```bash
cat .env
```

Output:

```bash
API_KEY=abcd1234efgh5678ijkl9012mnop3456
```

Check the lockfile:

```bash
cat .gitsecrets.lock
```

The lockfile contains hashed values and metadata:

```json
{
  "version": "1.0",
  "secrets": {
    "api_key": {
      "fields": {
        "value": {
          "hash": "sha256:a1b2c3d4...",
          "generated_at": "2026-02-16T12:00:00Z",
          "algorithm": "random-string"
        }
      },
      "targets": [".env"],
      "last_modified": "2026-02-16T12:00:00Z"
    }
  }
}
```

## Step 6: View Secret Status

Check the status of your secret:

```bash
secretzero show api_key
```

Output:

```
Secret: api_key
Type: api_key
Status: ✓ Generated

Fields:
  value:
    Algorithm: random-string
    Generated: 2026-02-16 12:00:00 UTC
    Hash: sha256:a1b2c3d4...

Targets:
  ✓ .env (dotenv format)

Last Modified: 2026-02-16 12:00:00 UTC
```

## 🎉 Congratulations!

You've successfully:

✅ Created a Secretfile  
✅ Validated the configuration  
✅ Generated a secret  
✅ Synced it to a local file  
✅ Tracked it in a lockfile

## What's Next?

Now that you understand the basics, explore more features:

### Add More Secrets

Edit your `Secretfile.yml` to add more secrets:

```yaml
secrets:
  api_key:
    # ... existing configuration ...
  
  database_password:
    template:
      type: password
      fields:
        - name: value
          generator:
            type: random-password
            length: 32
            include_symbols: true
    targets:
      - type: local-file
        path: .env
        format: dotenv
```

Then sync again:

```bash
secretzero sync
```

### Use Different Targets

Store secrets in multiple locations:

```yaml
secrets:
  api_key:
    template:
      type: api_key
      fields:
        - name: value
          generator:
            type: random-string
            length: 32
    targets:
      - type: local-file
        path: .env
        format: dotenv
      - type: local-file
        path: config.json
        format: json
      - type: local-file
        path: config.yml
        format: yaml
```

### Add Cloud Providers

Store secrets in AWS Secrets Manager:

```yaml
providers:
  aws:
    type: aws
    auth:
      type: ambient  # Uses IAM roles/profiles

secrets:
  api_key:
    template:
      type: api_key
      fields:
        - name: value
          generator:
            type: random-string
            length: 32
    targets:
      - type: aws-secretsmanager
        provider: aws
        name: /prod/api_key
      - type: local-file
        path: .env
        format: dotenv
```

First install AWS support:

```bash
pip install secretzero[aws]
```

Then sync:

```bash
secretzero sync
```

### Test Provider Connectivity

Before syncing to cloud providers, test connectivity:

```bash
secretzero test
```

This verifies that:

- Provider authentication is working
- Required permissions are available
- Network connectivity is OK

### Add Rotation Policies

Automatically rotate secrets based on time:

```yaml
secrets:
  api_key:
    template:
      type: api_key
      fields:
        - name: value
          generator:
            type: random-string
            length: 32
    rotation:
      period: 90d  # Rotate every 90 days
    targets:
      - type: local-file
        path: .env
        format: dotenv
```

Check rotation status:

```bash
secretzero rotate --dry-run
```

Execute rotation:

```bash
secretzero rotate
```

## Common Use Cases

Here are some quick examples for common scenarios:

### Database Credentials

```yaml
secrets:
  db_password:
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
        - name: host
          generator:
            type: static
            value: db.example.com
        - name: port
          generator:
            type: static
            value: "5432"
    targets:
      - type: local-file
        path: .env
        format: dotenv
```

### API Tokens

```yaml
secrets:
  github_token:
    template:
      type: token
      fields:
        - name: value
          generator:
            type: random-string
            length: 40
            charset: hex
    targets:
      - type: local-file
        path: .env
        format: dotenv
        key: GITHUB_TOKEN
```

### Multi-Field Secrets

```yaml
secrets:
  oauth_credentials:
    template:
      type: oauth
      fields:
        - name: client_id
          generator:
            type: random-string
            length: 32
        - name: client_secret
          generator:
            type: random-password
            length: 64
    targets:
      - type: local-file
        path: oauth.json
        format: json
```

## Tips and Best Practices

!!! tip "Use Dry Run First"
    Always use `--dry-run` to preview changes before applying them:
    ```bash
    secretzero sync --dry-run
    ```

!!! warning "Protect Your Secrets"
    Add secret files to `.gitignore`:
    ```
    .env
    .env.local
    .gitsecrets.lock
    ```

!!! info "Environment Variables"
    You can override generated values with environment variables:
    ```bash
    export API_KEY_VALUE="my-existing-key"
    secretzero sync  # Will use the environment variable
    ```

!!! success "Lockfile Benefits"
    The lockfile (`.gitsecrets.lock`):
    
    - Tracks secret history
    - Prevents unnecessary regeneration
    - Enables drift detection
    - Supports compliance audits

## Next Steps

Ready to learn more?

1. **[First Project →](first-project.md)** - Build a complete multi-secret project
2. **[Basic Concepts →](concepts.md)** - Understand the architecture
3. **[User Guide →](../user-guide/index.md)** - Detailed documentation
4. **[Examples →](../examples/index.md)** - Real-world examples

## Getting Help

Need assistance?

- [FAQ](../reference/faq.md) - Common questions
- [Troubleshooting](../reference/troubleshooting.md) - Solutions to common issues
- [GitHub Issues](https://github.com/zloeber/SecretZero/issues) - Report bugs
- [Discussions](https://github.com/zloeber/SecretZero/discussions) - Ask questions
