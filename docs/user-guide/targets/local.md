# Local File Targets

Local file targets store secrets in files on the local filesystem, making them ideal for development environments, testing, and applications that read configuration from files.

## Overview

The file target supports multiple formats commonly used for configuration:

- **`.env` (dotenv)** - Environment variable format
- **JSON** - JavaScript Object Notation
- **YAML** - YAML Ain't Markup Language
- **TOML** - Tom's Obvious Minimal Language

## Use Cases

- **Local development** - Store secrets for development environments
- **Container configuration** - Mount secret files in Docker containers
- **Legacy applications** - Support apps that read from config files
- **Backup** - Create local copies of cloud-managed secrets
- **Testing** - Generate test fixtures with realistic secret data

## Configuration

### Basic Example

```yaml
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | string | Yes | `.env` | File path to store secrets (relative or absolute) |
| `format` | string | Yes | `dotenv` | File format: `dotenv`, `json`, `yaml`, `toml` |
| `merge` | boolean | No | `true` | Whether to merge with existing content or overwrite |

## Format Specifications

### Dotenv Format

Standard environment variable format used by many frameworks.

**Configuration:**
```yaml
targets:
  - provider: local
    kind: file
    config:
      path: .env
      format: dotenv
      merge: true
```

**Output (.env):**
```bash
DATABASE_PASSWORD=supersecret123
API_KEY=abcdef123456
JWT_SECRET=random-jwt-token-here
```

**Features:**
- Simple key=value pairs
- Comments supported (lines starting with `#`)
- Automatic quoting for values with spaces or special characters
- Preserves existing variables when `merge: true`

**Example with multiple secrets:**
```yaml
secrets:
  - name: DB_HOST
    kind: static
    config:
      value: localhost
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv

  - name: DB_PASSWORD
    kind: random_password
    config:
      length: 24
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true  # Merge with DB_HOST
```

### JSON Format

Structured format for programmatic access.

**Configuration:**
```yaml
targets:
  - provider: local
    kind: file
    config:
      path: secrets.json
      format: json
      merge: true
```

**Output (secrets.json):**
```json
{
  "database_password": "supersecret123",
  "api_key": "abcdef123456",
  "jwt_secret": "random-jwt-token-here"
}
```

**Features:**
- Structured key-value storage
- Easy to parse in any language
- Pretty-printed with 2-space indentation
- Supports merging with existing JSON objects

**Example with nested structure:**
```yaml
secrets:
  - name: app_config
    kind: templates.application_config

templates:
  application_config:
    fields:
      database:
        generator:
          kind: static
          config:
            default: '{"host": "localhost", "port": 5432}'
      api_key:
        generator:
          kind: random_string
          config:
            length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: config.json
          format: json
```

### YAML Format

Human-readable format popular in configuration files.

**Configuration:**
```yaml
targets:
  - provider: local
    kind: file
    config:
      path: secrets.yaml
      format: yaml
      merge: true
```

**Output (secrets.yaml):**
```yaml
database_password: supersecret123
api_key: abcdef123456
jwt_secret: random-jwt-token-here
```

**Features:**
- Clean, readable format
- Preserves key order
- No flow style (uses block style)
- Merges with existing YAML structures

**Example configuration:**
```yaml
secrets:
  - name: database_url
    kind: static
    config:
      value: postgresql://user:pass@localhost/db
    targets:
      - provider: local
        kind: file
        config:
          path: config.yaml
          format: yaml

  - name: redis_url
    kind: static
    config:
      value: redis://localhost:6379
    targets:
      - provider: local
        kind: file
        config:
          path: config.yaml
          format: yaml
          merge: true
```

### TOML Format

Configuration format used by Rust, Python, and other ecosystems.

**Configuration:**
```yaml
targets:
  - provider: local
    kind: file
    config:
      path: secrets.toml
      format: toml
      merge: true
```

**Output (secrets.toml):**
```toml
database_password = "supersecret123"
api_key = "abcdef123456"
jwt_secret = "random-jwt-token-here"
```

**Features:**
- Clear, unambiguous format
- Type-safe
- Good for nested configurations
- Popular in Rust and Python projects

**Dependencies:**
TOML support requires additional packages:
```bash
pip install secretzero[toml]
# or
pip install tomli tomli-w
```

## Complete Examples

### Development Environment Setup

Create a complete `.env` file for local development:

```yaml
version: '1.0'

secrets:
  # Database configuration
  - name: DB_HOST
    kind: static
    config:
      value: localhost
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv

  - name: DB_PORT
    kind: static
    config:
      value: "5432"
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  - name: DB_NAME
    kind: static
    config:
      value: myapp_dev
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  - name: DB_PASSWORD
    kind: random_password
    config:
      length: 24
      special: false
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # Application secrets
  - name: SECRET_KEY
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

  - name: JWT_SECRET
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

  # External API keys
  - name: STRIPE_API_KEY
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
```

**Result (.env):**
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp_dev
DB_PASSWORD=randompassword123456789012
SECRET_KEY=base64encodedsecretkey...
JWT_SECRET=abcdef1234567890abcdef1234567890
STRIPE_API_KEY=sk_test_abc123def456ghi789jkl
```

### Multi-Format Configuration

Store secrets in multiple formats simultaneously:

```yaml
version: '1.0'

secrets:
  - name: api_credentials
    kind: templates.api_config

templates:
  api_config:
    description: API configuration
    fields:
      api_key:
        generator:
          kind: random_string
          config:
            length: 32
            charset: alphanumeric
      api_secret:
        generator:
          kind: random_string
          config:
            length: 64
            charset: base64
      endpoint:
        generator:
          kind: static
          config:
            default: https://api.example.com
    targets:
      # Dotenv for Docker Compose
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
      
      # JSON for Node.js apps
      - provider: local
        kind: file
        config:
          path: config/secrets.json
          format: json
      
      # YAML for Python apps
      - provider: local
        kind: file
        config:
          path: config/secrets.yaml
          format: yaml
```

### Docker Container Secrets

Generate secrets for Docker containers:

```yaml
version: '1.0'

secrets:
  - name: POSTGRES_PASSWORD
    kind: random_password
    config:
      length: 32
      special: false
    targets:
      - provider: local
        kind: file
        config:
          path: docker/.env
          format: dotenv

  - name: REDIS_PASSWORD
    kind: random_password
    config:
      length: 24
      special: false
    targets:
      - provider: local
        kind: file
        config:
          path: docker/.env
          format: dotenv
          merge: true

  - name: APP_SECRET_KEY
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: local
        kind: file
        config:
          path: docker/.env
          format: dotenv
          merge: true
```

**Use with Docker Compose:**
```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    env_file:
      - docker/.env
    environment:
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

  redis:
    image: redis:7
    command: redis-server --requirepass ${REDIS_PASSWORD}
    env_file:
      - docker/.env

  app:
    build: .
    env_file:
      - docker/.env
    environment:
      - SECRET_KEY=${APP_SECRET_KEY}
```

## Best Practices

### 1. Use `.gitignore`

Always exclude secret files from version control:

```gitignore
# Secret files
.env
.env.local
.env.*.local
secrets.json
secrets.yaml
secrets.toml
config/secrets.*

# Keep templates
!.env.example
```

### 2. Provide Example Files

Create example files with dummy values:

```bash
# .env.example
DB_HOST=localhost
DB_PORT=5432
DB_PASSWORD=changeme
API_KEY=your-api-key-here
```

### 3. Use Merge Mode Carefully

When `merge: true`:
- Existing keys are preserved
- New secrets are added
- Updated secrets overwrite old values

When `merge: false`:
- File is completely overwritten
- Only current secrets are included
- Previous content is lost

```yaml
# Safe for multiple secrets in same file
targets:
  - provider: local
    kind: file
    config:
      path: .env
      format: dotenv
      merge: true  # Add to existing file

# Use for single-secret files
targets:
  - provider: local
    kind: file
    config:
      path: secrets/api_key.txt
      format: dotenv
      merge: false  # Overwrite completely
```

### 4. Organize by Environment

Structure files by environment:

```yaml
variables:
  environment: dev

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: .env.{{var.environment}}
          format: dotenv
```

Results in: `.env.dev`, `.env.staging`, `.env.prod`

### 5. Set Appropriate Permissions

Protect secret files with proper permissions:

```bash
# Restrict access to owner only
chmod 600 .env
chmod 600 secrets.json

# Or use SecretZero to set permissions
secretzero sync -f Secretfile.yml --file-mode 0600
```

### 6. Use Separate Files for Different Purposes

Organize secrets logically:

```yaml
secrets:
  # Database secrets → database.env
  - name: DB_PASSWORD
    targets:
      - provider: local
        kind: file
        config:
          path: secrets/database.env
          format: dotenv

  # API keys → api.env
  - name: API_KEY
    targets:
      - provider: local
        kind: file
        config:
          path: secrets/api.env
          format: dotenv

  # Application config → app.json
  - name: app_config
    targets:
      - provider: local
        kind: file
        config:
          path: config/app.json
          format: json
```

## Troubleshooting

### File Not Created

**Problem:** Secret file doesn't exist after running sync.

**Solutions:**
1. Check parent directory exists (SecretZero creates missing directories)
2. Verify path is correct (relative to working directory)
3. Check file permissions on parent directory
4. Review logs for error messages

```bash
# Test with absolute path
secretzero sync -f Secretfile.yml --log-level debug
```

### Merge Not Working

**Problem:** New secrets overwrite existing ones.

**Solutions:**
1. Ensure `merge: true` is set
2. Check file format matches existing file
3. Verify file is readable
4. Use different files if formats conflict

### Format Not Supported

**Problem:** Error about unsupported format.

**Solutions:**
1. For TOML: Install dependencies
   ```bash
   pip install tomli tomli-w
   ```
2. Check format spelling: `dotenv`, `json`, `yaml`, `toml` (lowercase)
3. Verify file extension matches format

### Special Characters in Dotenv

**Problem:** Values with spaces or special characters break parsing.

**Solution:** SecretZero automatically quotes values with special characters:

```bash
# Automatically quoted
PASSWORD="p@ss w0rd!"
API_KEY="key-with-dashes"

# No quotes needed
SIMPLE_KEY=abc123
```

### File Encoding Issues

**Problem:** Non-ASCII characters cause errors.

**Solution:** All files are written in UTF-8. Ensure your editor uses UTF-8:

```yaml
secrets:
  - name: WELCOME_MESSAGE
    kind: static
    config:
      value: "Welcome! 你好! مرحبا!"
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
```

## Integration Examples

### Python Applications

```python
# Load secrets from .env
from dotenv import load_dotenv
import os

load_dotenv()

database_password = os.getenv('DATABASE_PASSWORD')
api_key = os.getenv('API_KEY')
```

### Node.js Applications

```javascript
// Load secrets from .env
require('dotenv').config();

const databasePassword = process.env.DATABASE_PASSWORD;
const apiKey = process.env.API_KEY;
```

### Go Applications

```go
// Load secrets from .env
import "github.com/joho/godotenv"

err := godotenv.Load()
if err != nil {
    log.Fatal("Error loading .env file")
}

databasePassword := os.Getenv("DATABASE_PASSWORD")
apiKey := os.Getenv("API_KEY")
```

### Ruby Applications

```ruby
# Load secrets from .env
require 'dotenv/load'

database_password = ENV['DATABASE_PASSWORD']
api_key = ENV['API_KEY']
```

## Security Considerations

### File Permissions

Local files are only as secure as their permissions:

```bash
# Secure file permissions
chmod 600 .env          # Owner read/write only
chmod 700 secrets/      # Owner access to directory

# Check permissions
ls -la .env
# Should show: -rw------- (600)
```

### Encryption at Rest

For sensitive data, consider encrypting files:

```bash
# Encrypt with GPG
gpg --symmetric --cipher-algo AES256 secrets.json

# Decrypt when needed
gpg --decrypt secrets.json.gpg > secrets.json
```

### Temporary Files

Clean up temporary secret files:

```yaml
# Generate temporary secrets
secrets:
  - name: temp_token
    kind: random_string
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: /tmp/temp_secret.txt
          format: dotenv
```

Then clean up:
```bash
# After use
rm -f /tmp/temp_secret.txt
```

### Backup Considerations

When backing up systems:
- Exclude secret files from backups
- Or use encrypted backups
- Rotate secrets after backup restoration

```bash
# Exclude from rsync backup
rsync -av --exclude='.env' --exclude='secrets/' /app/ /backup/
```

## Next Steps

- Explore [AWS targets](aws.md) for cloud storage
- Learn about [Kubernetes secrets](kubernetes.md) for containers
- Review [CI/CD targets](github.md) for automation
- Check [examples](../../examples/) for more patterns
