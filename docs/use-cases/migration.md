# Migration Guide

## Problem Statement

Migrating from existing secret management tools to SecretZero presents several challenges:

- Secrets scattered across multiple legacy systems (environment variables, config files, Jenkins credentials, etc.)
- No downtime tolerance for production systems during migration
- Risk of secret loss or exposure during transition
- Different secret formats and structures across tools
- Need to maintain backward compatibility during migration
- Auditing requirements for tracking secret migration
- Team training and adoption challenges
- Rollback procedures if migration fails

**SecretZero solves this** by providing a phased migration approach with zero downtime, comprehensive import tools, validation at each step, and support for parallel operation during transition.

## Prerequisites

- SecretZero installed: `pip install secretzero`
- Access to existing secret management systems
- Backup of all current secrets (encrypted)
- Migration plan with rollback procedures
- Target secret storage providers configured
- Test environment for validation
- Communication plan for teams

## Migration Strategies

### Strategy 1: Direct Migration (Recommended for Small Projects)

Best for projects with <50 secrets and short maintenance windows:

1. **Inventory** - Document all existing secrets
2. **Create** - Define Secretfile.yml configuration
3. **Sync** - Deploy secrets with SecretZero
4. **Validate** - Verify all secrets work
5. **Cutover** - Switch applications to new secrets
6. **Decommission** - Remove old secret storage

### Strategy 2: Parallel Operation (Recommended for Large Projects)

Best for projects with >50 secrets or zero downtime requirements:

1. **Inventory** - Document all existing secrets
2. **Deploy** - Add new SecretZero-managed secrets alongside existing
3. **Gradual Migration** - Move services one by one
4. **Validation** - Verify each service before moving next
5. **Monitoring** - Track usage of old vs new secrets
6. **Cutover** - Remove old secrets after all services migrated

### Strategy 3: Phased Migration (Recommended for Enterprise)

Best for large organizations with multiple teams and compliance requirements:

1. **Pilot** - Start with non-critical service
2. **Learn** - Document lessons and best practices
3. **Expand** - Gradually add more services
4. **Standardize** - Create templates and patterns
5. **Scale** - Roll out across organization
6. **Complete** - Decommission legacy systems

## Migrating from Common Tools

### From Environment Variables

Current state:

```bash
# .env file
DATABASE_URL=postgresql://user:password@localhost:5432/myapp
API_KEY=sk_live_abc123xyz789
JWT_SECRET=super-secret-key-12345
REDIS_PASSWORD=redis-password-here
```

Migration steps:

```bash
# 1. Create import script
cat > import-env.sh << 'EOF'
#!/bin/bash
set -e

# Read current .env file
source .env

# Create Secretfile.yml
cat > Secretfile.yml << YAML
version: '1.0'

metadata:
  project: myapp
  owner: engineering-team
  migrated_from: environment-variables
  migration_date: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

variables:
  environment: production

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1
  
  local:
    kind: local

secrets:
  # Migrated from .env
  - name: database_url
    kind: static
    rotation_period: 90d
    config:
      default: "${DATABASE_URL}"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/myapp/database-url
          description: Migrated from .env
          tags:
            MigratedFrom: environment-variables
            MigrationDate: "$(date -u +%Y-%m-%d)"
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  - name: api_key
    kind: static
    rotation_period: 90d
    config:
      default: "${API_KEY}"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/myapp/api-key
          description: Migrated from .env
          tags:
            MigratedFrom: environment-variables
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  - name: jwt_secret
    kind: static
    rotation_period: 90d
    config:
      default: "${JWT_SECRET}"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/myapp/jwt-secret
          description: Migrated from .env
          tags:
            MigratedFrom: environment-variables
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  - name: redis_password
    kind: static
    rotation_period: 90d
    config:
      default: "${REDIS_PASSWORD}"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/myapp/redis-password
          description: Migrated from .env
          tags:
            MigratedFrom: environment-variables
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
YAML

echo "Secretfile.yml created successfully"
EOF

chmod +x import-env.sh

# 2. Run import
./import-env.sh

# 3. Validate
secretzero validate

# 4. Backup original .env
cp .env .env.backup.$(date +%Y%m%d)

# 5. Sync to new providers
secretzero sync

# 6. Verify secrets
secretzero list

# 7. Test application with new secrets
# (Application should still work as .env is maintained)

# 8. Monitor for 24-48 hours

# 9. Update to generate secrets automatically (Phase 2)
# Change from 'static' to 'random_password' or 'random_string'
```

### From HashiCorp Vault

Current state:

```bash
# Secrets stored in Vault KV v2
vault kv get secret/production/myapp/database
vault kv get secret/production/myapp/api-keys
vault kv get secret/production/myapp/service-account
```

Migration steps:

```bash
# 1. Export secrets from Vault
cat > export-vault.sh << 'EOF'
#!/bin/bash
set -e

export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=${VAULT_TOKEN}

# Create export directory
mkdir -p vault-export

# Export secrets (encrypted)
echo "Exporting secrets from Vault..."

# Database credentials
vault kv get -format=json secret/production/myapp/database \
  > vault-export/database.json

# API keys
vault kv get -format=json secret/production/myapp/api-keys \
  > vault-export/api-keys.json

# Service account
vault kv get -format=json secret/production/myapp/service-account \
  > vault-export/service-account.json

echo "Export complete. Files saved to vault-export/"
EOF

chmod +x export-vault.sh
./export-vault.sh

# 2. Create Secretfile.yml from exports
cat > import-vault.py << 'PYTHON'
#!/usr/bin/env python3
import json
import yaml
from pathlib import Path

def load_vault_export(filename):
    with open(f'vault-export/{filename}') as f:
        data = json.load(f)
        return data['data']['data']

# Load exported secrets
database = load_vault_export('database.json')
api_keys = load_vault_export('api-keys.json')
service_account = load_vault_export('service-account.json')

# Create Secretfile configuration
config = {
    'version': '1.0',
    'metadata': {
        'project': 'myapp',
        'owner': 'engineering-team',
        'migrated_from': 'hashicorp-vault',
        'migration_date': '2024-01-15T10:00:00Z'
    },
    'variables': {
        'environment': 'production',
        'app_name': 'myapp'
    },
    'providers': {
        'aws': {
            'kind': 'aws',
            'auth': {
                'kind': 'ambient',
                'config': {
                    'region': 'us-east-1'
                }
            }
        },
        'vault': {
            'kind': 'vault',
            'auth': {
                'kind': 'token',
                'config': {
                    'token': '${VAULT_TOKEN}',
                    'url': '${VAULT_ADDR}'
                }
            }
        }
    },
    'secrets': []
}

# Database password
config['secrets'].append({
    'name': 'database_password',
    'kind': 'static',
    'rotation_period': '90d',
    'config': {
        'default': database.get('password', '')
    },
    'targets': [
        {
            'provider': 'aws',
            'kind': 'secrets_manager',
            'config': {
                'name': 'production/myapp/database/password',
                'description': 'Migrated from Vault',
                'tags': {
                    'MigratedFrom': 'vault',
                    'OriginalPath': 'secret/production/myapp/database'
                }
            }
        },
        {
            'provider': 'vault',
            'kind': 'kv',
            'config': {
                'path': 'production/myapp/database/password',
                'mount_point': 'secret',
                'version': 2
            }
        }
    ]
})

# API keys (template with multiple fields)
config['secrets'].append({
    'name': 'api_keys',
    'kind': 'templates.api_keys_migrated'
})

config['templates'] = {
    'api_keys_migrated': {
        'description': 'API keys migrated from Vault',
        'fields': {}
    }
}

# Add all API key fields
for key, value in api_keys.items():
    config['templates']['api_keys_migrated']['fields'][key] = {
        'generator': {
            'kind': 'static',
            'config': {
                'default': value
            }
        }
    }

config['templates']['api_keys_migrated']['targets'] = [
    {
        'provider': 'aws',
        'kind': 'secrets_manager',
        'config': {
            'name': 'production/myapp/api-keys',
            'description': 'Migrated from Vault',
            'tags': {
                'MigratedFrom': 'vault'
            }
        }
    },
    {
        'provider': 'vault',
        'kind': 'kv',
        'config': {
            'path': 'production/myapp/api-keys',
            'mount_point': 'secret',
            'version': 2
        }
    }
]

# Write Secretfile.yml
with open('Secretfile.yml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print("Secretfile.yml created successfully")
PYTHON

chmod +x import-vault.py
python3 import-vault.py

# 3. Validate configuration
secretzero validate

# 4. Sync to both Vault and AWS (parallel operation)
secretzero sync

# 5. Verify in both systems
# Vault
vault kv get secret/production/myapp/database/password

# AWS
aws secretsmanager get-secret-value \
  --secret-id production/myapp/database/password

# 6. Update applications gradually to use AWS Secrets Manager

# 7. After all apps migrated, remove Vault targets from Secretfile.yml
```

### From AWS Systems Manager Parameter Store

Current state:

```bash
# Parameters stored in SSM
/production/myapp/database/host
/production/myapp/database/password
/production/myapp/api/key
/production/myapp/jwt/secret
```

Migration steps:

```bash
# 1. Export SSM parameters
cat > export-ssm.sh << 'EOF'
#!/bin/bash
set -e

# Get all parameters with prefix
aws ssm get-parameters-by-path \
  --path /production/myapp \
  --recursive \
  --with-decryption \
  --query 'Parameters[*].[Name,Value,Type]' \
  --output json \
  > ssm-export.json

echo "SSM parameters exported to ssm-export.json"
EOF

chmod +x export-ssm.sh
./export-ssm.sh

# 2. Generate Secretfile.yml from SSM export
cat > import-ssm.py << 'PYTHON'
#!/usr/bin/env python3
import json
import yaml

# Load SSM export
with open('ssm-export.json') as f:
    parameters = json.load(f)

config = {
    'version': '1.0',
    'metadata': {
        'project': 'myapp',
        'owner': 'engineering-team',
        'migrated_from': 'aws-ssm',
        'migration_date': '2024-01-15'
    },
    'variables': {
        'environment': 'production'
    },
    'providers': {
        'aws': {
            'kind': 'aws',
            'auth': {
                'kind': 'ambient',
                'config': {
                    'region': 'us-east-1'
                }
            }
        }
    },
    'secrets': []
}

# Convert parameters to secrets
for param in parameters:
    name, value, param_type = param
    
    # Extract secret name from parameter path
    # /production/myapp/database/password -> database_password
    secret_name = name.replace('/production/myapp/', '').replace('/', '_')
    
    secret = {
        'name': secret_name,
        'kind': 'static',
        'rotation_period': '90d',
        'config': {
            'default': value
        },
        'targets': [
            {
                'provider': 'aws',
                'kind': 'secrets_manager',  # Migrate to Secrets Manager
                'config': {
                    'name': name.replace('/production/myapp/', 'production/myapp/'),
                    'description': f'Migrated from SSM: {name}',
                    'tags': {
                        'MigratedFrom': 'ssm',
                        'OriginalPath': name,
                        'OriginalType': param_type
                    }
                }
            },
            {
                'provider': 'aws',
                'kind': 'ssm_parameter',  # Keep in SSM for backward compatibility
                'config': {
                    'name': name,
                    'type': param_type,
                    'description': f'Maintained for compatibility',
                    'tags': {
                        'ManagedBy': 'secretzero'
                    }
                }
            }
        ]
    }
    
    config['secrets'].append(secret)

# Write Secretfile.yml
with open('Secretfile.yml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print(f"Generated Secretfile.yml with {len(parameters)} secrets")
PYTHON

chmod +x import-ssm.py
python3 import-ssm.py

# 3. Validate and sync
secretzero validate
secretzero sync

# 4. Verify secrets in both locations
aws ssm get-parameter --name /production/myapp/database/password --with-decryption
aws secretsmanager get-secret-value --secret-id production/myapp/database/password

# 5. Update applications to use Secrets Manager

# 6. After migration complete, remove SSM targets
```

### From Jenkins Credentials

Current state:

- Username/password credentials
- Secret text credentials
- SSH keys
- Certificates

Migration steps:

```bash
# 1. Export Jenkins credentials
# Manual export required - Jenkins doesn't have bulk export API
# Document each credential:
cat > jenkins-credentials-inventory.csv << 'CSV'
ID,Type,Description,Scope
db-password,UsernamePassword,Database credentials,Global
api-key,SecretText,External API key,Global
deploy-key,SSHUserPrivateKey,Deployment SSH key,Global
github-token,SecretText,GitHub PAT,Global
CSV

# 2. Create Secretfile.yml for Jenkins credentials
cat > Secretfile.yml << 'YAML'
version: '1.0'

metadata:
  project: jenkins-migration
  owner: devops-team
  migrated_from: jenkins-credentials
  migration_date: "2024-01-15"

variables:
  environment: production

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1
  
  # Keep secrets in Jenkins during transition
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: ${JENKINS_USER}
        token: ${JENKINS_TOKEN}

secrets:
  # Database credentials (username/password)
  - name: database_credentials
    kind: templates.db_creds_jenkins

  # API key (secret text)
  - name: api_key
    kind: static
    rotation_period: 90d
    config:
      # Manually copy from Jenkins during migration
      default: ${API_KEY}
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/api-key
          tags:
            MigratedFrom: jenkins
            JenkinsCredentialID: api-key
      - provider: jenkins
        kind: jenkins_secret_text
        config:
          credential_id: api-key
          description: Managed by SecretZero

  # Deploy SSH key
  - name: deploy_ssh_key
    kind: templates.ssh_key_jenkins

  # GitHub token
  - name: github_token
    kind: static
    rotation_period: 90d
    config:
      default: ${GITHUB_TOKEN}
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/github-token
          tags:
            MigratedFrom: jenkins
      - provider: jenkins
        kind: jenkins_secret_text
        config:
          credential_id: github-token
          description: Managed by SecretZero

templates:
  db_creds_jenkins:
    description: Database credentials
    fields:
      username:
        generator:
          kind: static
          config:
            default: ${DB_USERNAME}
      password:
        generator:
          kind: static
          config:
            default: ${DB_PASSWORD}
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/database-credentials
          tags:
            MigratedFrom: jenkins
      - provider: jenkins
        kind: jenkins_username_password
        config:
          credential_id: db-password
          description: Managed by SecretZero

  ssh_key_jenkins:
    description: Deployment SSH key
    fields:
      private_key:
        generator:
          kind: static
          config:
            default: ${SSH_PRIVATE_KEY}
      public_key:
        generator:
          kind: static
          config:
            default: ${SSH_PUBLIC_KEY}
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/deploy-ssh-key
          tags:
            MigratedFrom: jenkins
      - provider: jenkins
        kind: jenkins_ssh_key
        config:
          credential_id: deploy-key
          username: deploy
          description: Managed by SecretZero
YAML

# 3. Export Jenkins credentials manually
# For each credential in jenkins-credentials-inventory.csv:
# 1. Open Jenkins web UI
# 2. Navigate to Credentials
# 3. Copy secret values
# 4. Set as environment variables

export DB_USERNAME="myapp_user"
export DB_PASSWORD="current_password_from_jenkins"
export API_KEY="current_api_key_from_jenkins"
export GITHUB_TOKEN="current_github_token_from_jenkins"
export SSH_PRIVATE_KEY="$(cat ~/.ssh/deploy_key)"
export SSH_PUBLIC_KEY="$(cat ~/.ssh/deploy_key.pub)"

# 5. Validate and sync
secretzero validate
secretzero sync

# 6. Verify in both systems
# Jenkins
curl -u $JENKINS_USER:$JENKINS_TOKEN \
  https://jenkins.example.com/credentials/api/json

# AWS
aws secretsmanager list-secrets

# 7. Update Jenkinsfile to use new secrets
# Before:
# withCredentials([usernamePassword(credentialsId: 'db-password', ...)]) { }
# 
# After:
# withAWS(credentials: 'aws-credentials') {
#   script {
#     def secret = sh(
#       script: 'aws secretsmanager get-secret-value --secret-id production/database-credentials --query SecretString --output text',
#       returnStdout: true
#     ).trim()
#   }
# }

# 8. Test Jenkins pipelines with new approach

# 9. After validation, remove Jenkins targets from Secretfile.yml
```

### From Kubernetes Secrets

Current state:

```bash
# Secrets stored in Kubernetes
kubectl get secrets -n production
```

Migration steps:

```bash
# 1. Export Kubernetes secrets
cat > export-k8s-secrets.sh << 'EOF'
#!/bin/bash
set -e

NAMESPACE=production
OUTPUT_DIR=k8s-secrets-export

mkdir -p $OUTPUT_DIR

# Get all secrets
kubectl get secrets -n $NAMESPACE -o json | \
  jq -r '.items[] | select(.type == "Opaque") | .metadata.name' | \
  while read secret_name; do
    echo "Exporting secret: $secret_name"
    kubectl get secret $secret_name -n $NAMESPACE -o yaml > $OUTPUT_DIR/${secret_name}.yaml
  done

echo "Secrets exported to $OUTPUT_DIR/"
EOF

chmod +x export-k8s-secrets.sh
./export-k8s-secrets.sh

# 2. Generate Secretfile.yml from K8s exports
cat > import-k8s.py << 'PYTHON'
#!/usr/bin/env python3
import yaml
import base64
from pathlib import Path

def decode_secret_data(data):
    """Decode base64-encoded secret data"""
    decoded = {}
    for key, value in data.items():
        decoded[key] = base64.b64decode(value).decode('utf-8')
    return decoded

# Load all exported secrets
secret_files = Path('k8s-secrets-export').glob('*.yaml')

config = {
    'version': '1.0',
    'metadata': {
        'project': 'myapp',
        'owner': 'platform-team',
        'migrated_from': 'kubernetes-secrets',
        'migration_date': '2024-01-15'
    },
    'variables': {
        'namespace': 'production'
    },
    'providers': {
        'aws': {
            'kind': 'aws',
            'auth': {
                'kind': 'ambient',
                'config': {
                    'region': 'us-east-1'
                }
            }
        },
        'kubernetes': {
            'kind': 'kubernetes',
            'auth': {
                'kind': 'ambient',
                'config': {}
            }
        }
    },
    'secrets': [],
    'templates': {}
}

for secret_file in secret_files:
    with open(secret_file) as f:
        k8s_secret = yaml.safe_load(f)
    
    secret_name = k8s_secret['metadata']['name']
    secret_data = decode_secret_data(k8s_secret.get('data', {}))
    
    # Skip system secrets
    if secret_name.startswith('default-token-'):
        continue
    
    # Create template for multi-field secrets
    if len(secret_data) > 1:
        template_name = f"{secret_name}_template"
        
        config['templates'][template_name] = {
            'description': f'Migrated from K8s secret: {secret_name}',
            'fields': {}
        }
        
        for key, value in secret_data.items():
            config['templates'][template_name]['fields'][key] = {
                'generator': {
                    'kind': 'static',
                    'config': {
                        'default': value
                    }
                }
            }
        
        config['templates'][template_name]['targets'] = [
            {
                'provider': 'aws',
                'kind': 'secrets_manager',
                'config': {
                    'name': f'production/k8s/{secret_name}',
                    'description': f'Migrated from K8s secret: {secret_name}',
                    'tags': {
                        'MigratedFrom': 'kubernetes',
                        'OriginalName': secret_name,
                        'OriginalNamespace': 'production'
                    }
                }
            },
            {
                'provider': 'kubernetes',
                'kind': 'kubernetes_secret',
                'config': {
                    'namespace': '{{ var.namespace }}',
                    'secret_name': secret_name,
                    'secret_type': 'Opaque',
                    'labels': {
                        'managed-by': 'secretzero'
                    }
                }
            }
        ]
        
        config['secrets'].append({
            'name': secret_name,
            'kind': f'templates.{template_name}',
            'rotation_period': '90d'
        })
    
    # Single-field secrets
    else:
        key = list(secret_data.keys())[0]
        value = secret_data[key]
        
        config['secrets'].append({
            'name': secret_name,
            'kind': 'static',
            'rotation_period': '90d',
            'config': {
                'default': value
            },
            'targets': [
                {
                    'provider': 'aws',
                    'kind': 'secrets_manager',
                    'config': {
                        'name': f'production/k8s/{secret_name}',
                        'description': f'Migrated from K8s secret: {secret_name}',
                        'tags': {
                            'MigratedFrom': 'kubernetes'
                        }
                    }
                },
                {
                    'provider': 'kubernetes',
                    'kind': 'kubernetes_secret',
                    'config': {
                        'namespace': '{{ var.namespace }}',
                        'secret_name': secret_name,
                        'data_key': key,
                        'secret_type': 'Opaque',
                        'labels': {
                            'managed-by': 'secretzero'
                        }
                    }
                }
            ]
        })

with open('Secretfile.yml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print(f"Generated Secretfile.yml with {len(config['secrets'])} secrets")
PYTHON

chmod +x import-k8s.py
python3 import-k8s.py

# 3. Validate and sync
secretzero validate
secretzero sync

# 4. Verify secrets in both systems
# Kubernetes
kubectl get secrets -n production

# AWS
aws secretsmanager list-secrets --query 'SecretList[?starts_with(Name, `production/k8s/`)].Name'

# 5. No application changes needed - secrets remain in K8s

# 6. After validation, optionally remove K8s targets to migrate fully to cloud
```

## Step-by-Step Migration Process

### Phase 1: Discovery and Planning

```bash
# 1. Inventory all secrets
cat > inventory-secrets.sh << 'EOF'
#!/bin/bash
set -e

echo "SECRET INVENTORY REPORT"
echo "======================="
echo ""

# Environment variables
echo "Environment Variables (.env files):"
find . -name ".env*" -not -path "*/node_modules/*" | while read file; do
  echo "  - $file ($(grep -c "=" "$file" 2>/dev/null || echo 0) secrets)"
done
echo ""

# AWS SSM
echo "AWS SSM Parameters:"
aws ssm describe-parameters --query 'Parameters | length(@)' 2>/dev/null || echo "  Not accessible"
echo ""

# AWS Secrets Manager
echo "AWS Secrets Manager:"
aws secretsmanager list-secrets --query 'SecretList | length(@)' 2>/dev/null || echo "  Not accessible"
echo ""

# Kubernetes secrets
echo "Kubernetes Secrets:"
kubectl get secrets --all-namespaces --field-selector type=Opaque 2>/dev/null | wc -l || echo "  Not accessible"
echo ""

# Vault secrets
echo "HashiCorp Vault:"
vault kv list -format=json secret/ 2>/dev/null | jq 'length' || echo "  Not accessible"
echo ""

echo "Total estimated secrets: $(expr $ENV_COUNT + $SSM_COUNT + $SM_COUNT + $K8S_COUNT + $VAULT_COUNT 2>/dev/null || echo 'Unknown')"
EOF

chmod +x inventory-secrets.sh
./inventory-secrets.sh > secret-inventory.txt

# 2. Classify secrets by criticality
cat > classify-secrets.sh << 'EOF'
#!/bin/bash

cat > secret-classification.csv << 'CSV'
Secret Name,Criticality,Rotation Period,Migration Priority,Owner
database_master_password,CRITICAL,60d,High,database-team
api_key_production,HIGH,90d,High,api-team
jwt_secret,HIGH,90d,Medium,auth-team
redis_password,MEDIUM,90d,Medium,cache-team
developer_tokens,LOW,180d,Low,dev-team
CSV

echo "Secret classification saved to secret-classification.csv"
EOF

chmod +x classify-secrets.sh
./classify-secrets.sh

# 3. Create migration plan
cat > migration-plan.md << 'EOF'
# SecretZero Migration Plan

## Timeline
- Week 1: Discovery and planning
- Week 2: Pilot migration (non-critical service)
- Week 3-4: Production services migration
- Week 5: Validation and monitoring
- Week 6: Decommission old systems

## Risk Mitigation
1. Backup all secrets before migration
2. Test in staging environment first
3. Migrate during low-traffic windows
4. Maintain parallel operation for 1 week
5. Rollback procedures documented

## Success Criteria
- All secrets migrated successfully
- Zero downtime during migration
- All applications functioning normally
- Audit trail complete
- Old systems decommissioned

## Rollback Plan
If migration fails:
1. Restore from backup
2. Revert application configurations
3. Document issues
4. Schedule retry

## Communication Plan
- Notify teams 1 week before migration
- Daily updates during migration
- Post-migration report
EOF

# 4. Create backup
cat > backup-secrets.sh << 'EOF'
#!/bin/bash
set -e

BACKUP_DIR="secrets-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Backing up all secrets to $BACKUP_DIR..."

# Environment files
find . -name ".env*" -not -path "*/node_modules/*" -exec cp {} "$BACKUP_DIR/" \;

# AWS SSM
aws ssm get-parameters-by-path --path / --recursive --with-decryption \
  > "$BACKUP_DIR/aws-ssm-backup.json" 2>/dev/null || true

# AWS Secrets Manager
aws secretsmanager list-secrets | jq -r '.SecretList[].Name' | while read secret; do
  aws secretsmanager get-secret-value --secret-id "$secret" \
    > "$BACKUP_DIR/aws-sm-${secret//\//-}.json" 2>/dev/null || true
done

# Kubernetes
kubectl get secrets --all-namespaces -o yaml \
  > "$BACKUP_DIR/kubernetes-secrets-backup.yaml" 2>/dev/null || true

# Vault
vault kv list -format=json secret/ | jq -r '.[]' | while read path; do
  vault kv get -format=json "secret/$path" \
    > "$BACKUP_DIR/vault-${path//\//-}.json" 2>/dev/null || true
done

# Encrypt backup
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
gpg --symmetric --cipher-algo AES256 "$BACKUP_DIR.tar.gz"
rm -rf "$BACKUP_DIR" "$BACKUP_DIR.tar.gz"

echo "Backup complete: $BACKUP_DIR.tar.gz.gpg"
echo "Store this backup securely!"
EOF

chmod +x backup-secrets.sh
./backup-secrets.sh
```

### Phase 2: Pilot Migration

```bash
# 1. Select pilot service (non-critical)
cat > pilot-service-config.yml << 'YAML'
version: '1.0'

metadata:
  project: pilot-service
  owner: platform-team
  migration_phase: pilot
  description: Non-critical service for testing migration

variables:
  environment: staging

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
  
  local:
    kind: local

secrets:
  - name: pilot_api_key
    kind: static
    rotation_period: 90d
    config:
      default: ${PILOT_API_KEY}
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: staging/pilot-service/api-key
          tags:
            MigrationPhase: pilot
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  - name: pilot_database_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: staging/pilot-service/database-password
          tags:
            MigrationPhase: pilot
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
YAML

# 2. Test pilot migration
cd pilot-service/
cp ../pilot-service-config.yml Secretfile.yml

# Validate
secretzero validate

# Dry run
secretzero sync --dry-run

# Actual migration
secretzero sync

# 3. Monitor pilot service
cat > monitor-pilot.sh << 'EOF'
#!/bin/bash

echo "Monitoring pilot service for 24 hours..."
START_TIME=$(date +%s)
END_TIME=$((START_TIME + 86400))  # 24 hours

while [ $(date +%s) -lt $END_TIME ]; do
  echo "=== $(date) ==="
  
  # Check service health
  curl -f http://pilot-service/health || echo "ALERT: Health check failed!"
  
  # Check error logs
  ERROR_COUNT=$(journalctl -u pilot-service --since "1 minute ago" | grep -c ERROR || echo 0)
  echo "Errors in last minute: $ERROR_COUNT"
  
  # Check secret access
  aws cloudwatch get-metric-statistics \
    --namespace AWS/SecretsManager \
    --metric-name SecretAccessed \
    --dimensions Name=SecretName,Value=staging/pilot-service/api-key \
    --start-time $(date -u -d '1 minute ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 60 \
    --statistics Sum
  
  sleep 300  # Check every 5 minutes
done

echo "24-hour monitoring complete!"
EOF

chmod +x monitor-pilot.sh
./monitor-pilot.sh &

# 4. Document lessons learned
cat > pilot-lessons-learned.md << 'EOF'
# Pilot Migration Lessons Learned

## What Went Well
- Secret sync completed successfully
- No application downtime
- Monitoring showed no issues

## Challenges
- Initial permission issues with AWS IAM
- Need to update documentation for team
- Some environment variables had special characters

## Improvements for Production
- Pre-configure IAM roles
- Create runbook for team
- Add validation for special characters
- Increase monitoring window to 48 hours

## Recommendations
- Proceed with production migration
- Use phased approach for high-traffic services
- Schedule migrations during low-traffic periods
EOF
```

### Phase 3: Production Migration

```bash
# 1. Create production migration schedule
cat > production-migration-schedule.md << 'EOF'
# Production Migration Schedule

## Week 1: Low-Traffic Services
- Monday: Background job service
- Tuesday: Monitoring service
- Wednesday: Internal API
- Thursday: Validation and monitoring
- Friday: Buffer day

## Week 2: Medium-Traffic Services
- Monday: Customer API (read-only)
- Tuesday: Validation
- Wednesday: Reporting service
- Thursday: Analytics service
- Friday: Validation and monitoring

## Week 3: High-Traffic Services
- Monday: Main API (phased rollout 25%)
- Tuesday: Main API (phased rollout 50%)
- Wednesday: Main API (phased rollout 75%)
- Thursday: Main API (phased rollout 100%)
- Friday: Final validation

## Week 4: Cleanup
- Remove old secret management systems
- Update documentation
- Team training
- Post-migration review
EOF

# 2. Production migration script
cat > migrate-production.sh << 'EOF'
#!/bin/bash
set -e

SERVICE_NAME=$1
if [ -z "$SERVICE_NAME" ]; then
  echo "Usage: ./migrate-production.sh <service-name>"
  exit 1
fi

echo "Migrating service: $SERVICE_NAME"
echo "================================"

# Pre-migration checks
echo "1. Pre-migration checks..."
secretzero validate -f "$SERVICE_NAME/Secretfile.yml"
secretzero test

# Backup current state
echo "2. Creating backup..."
./backup-secrets.sh

# Dry run
echo "3. Dry run..."
cd "$SERVICE_NAME"
secretzero sync --dry-run

# Wait for confirmation
read -p "Proceed with migration? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Migration cancelled"
  exit 1
fi

# Execute migration
echo "4. Executing migration..."
secretzero sync

# Verify
echo "5. Verifying secrets..."
secretzero list

# Health check
echo "6. Running health check..."
curl -f "http://$SERVICE_NAME/health" || {
  echo "ERROR: Health check failed!"
  echo "Rolling back..."
  # Rollback procedure here
  exit 1
}

# Monitor
echo "7. Monitoring service (5 minutes)..."
for i in {1..10}; do
  sleep 30
  curl -f "http://$SERVICE_NAME/health" || echo "Warning: Health check failed at $(date)"
done

echo "Migration complete for $SERVICE_NAME"
echo "Continue monitoring for 24 hours"
EOF

chmod +x migrate-production.sh

# 3. Migrate services one by one
./migrate-production.sh background-jobs
./migrate-production.sh monitoring-service
./migrate-production.sh internal-api
# ... continue for all services

# 4. Final validation
cat > validate-migration.sh << 'EOF'
#!/bin/bash
set -e

echo "Validating complete migration..."

# Check all services
SERVICES=("background-jobs" "monitoring-service" "internal-api" "main-api")

for service in "${SERVICES[@]}"; do
  echo "Checking $service..."
  
  # Health check
  curl -f "http://$service/health" || echo "ERROR: $service health check failed!"
  
  # Verify secrets in AWS
  aws secretsmanager get-secret-value --secret-id "production/$service/config" >/dev/null || \
    echo "ERROR: Secrets not found for $service"
  
  # Check error logs
  ERROR_COUNT=$(journalctl -u "$service" --since "1 hour ago" | grep -c ERROR || echo 0)
  echo "  Errors in last hour: $ERROR_COUNT"
  
  echo "  $service: OK"
done

echo "All services validated!"
EOF

chmod +x validate-migration.sh
./validate-migration.sh
```

### Phase 4: Cleanup and Decommission

```bash
# 1. Remove old secret storage
cat > cleanup-old-secrets.sh << 'EOF'
#!/bin/bash
set -e

echo "Cleanup Plan - Review before execution!"
echo "======================================"

# List secrets to be removed
echo "1. Environment files to remove:"
find . -name ".env.old" -o -name ".env.backup*"

echo ""
echo "2. Old SSM parameters to remove:"
aws ssm describe-parameters \
  --query 'Parameters[?!contains(Tags[?Key==`ManagedBy`].Value, `secretzero`)].Name'

echo ""
echo "3. Old Kubernetes secrets to remove:"
kubectl get secrets --all-namespaces \
  -l '!managed-by' -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name

echo ""
read -p "Proceed with cleanup? This cannot be undone! (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Cleanup cancelled"
  exit 1
fi

# Remove old environment files
echo "Removing old environment files..."
find . -name ".env.old" -delete
find . -name ".env.backup*" -delete

# Archive (don't delete) old SSM parameters
echo "Archiving old SSM parameters..."
aws ssm describe-parameters \
  --query 'Parameters[?!contains(Tags[?Key==`ManagedBy`].Value, `secretzero`)].Name' \
  --output text | xargs -I {} aws ssm add-tags-to-resource \
    --resource-type Parameter \
    --resource-id {} \
    --tags Key=Archived,Value=true Key=ArchivedDate,Value=$(date -u +%Y-%m-%d)

# Label old Kubernetes secrets (don't delete immediately)
echo "Labeling old Kubernetes secrets..."
kubectl get secrets --all-namespaces -l '!managed-by' -o json | \
  jq -r '.items[] | "\(.metadata.namespace) \(.metadata.name)"' | \
  while read namespace name; do
    kubectl label secret "$name" -n "$namespace" migrated=true archived=true
  done

echo "Cleanup complete!"
echo "Old resources are archived, not deleted"
echo "Review for 30 days before permanent deletion"
EOF

chmod +x cleanup-old-secrets.sh

# 2. Update documentation
cat > update-documentation.sh << 'EOF'
#!/bin/bash

# Create new secret management documentation
cat > docs/SECRET_MANAGEMENT.md << 'DOC'
# Secret Management with SecretZero

## Overview
We use SecretZero for all secret management. Secrets are stored in AWS Secrets Manager
and synced to necessary locations.

## Adding New Secrets

```bash
# 1. Edit Secretfile.yml
vim Secretfile.yml

# 2. Add new secret
secrets:
  - name: new_api_key
    kind: random_string
    rotation_period: 90d
    config:
      length: 32
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/myapp/new-api-key

# 3. Validate and sync
secretzero validate
secretzero sync

# 4. Use in application
# The secret is now available in AWS Secrets Manager
```

## Rotating Secrets

```bash
# Check rotation status
secretzero rotate --dry-run

# Rotate due secrets
secretzero rotate
```

## Emergency Procedures

If a secret is compromised:

```bash
# 1. Force immediate rotation
secretzero rotate --force --secret compromised_secret

# 2. Update applications
# (Secrets are automatically updated in storage)

# 3. Document incident
echo "Secret compromised_secret rotated due to incident #123" >> SECRET_ROTATION_LOG.md
```

## Getting Help
Contact: platform-team@example.com
Docs: https://secretzero.readthedocs.io
DOC

echo "Documentation updated at docs/SECRET_MANAGEMENT.md"
EOF

chmod +x update-documentation.sh
./update-documentation.sh

# 3. Team training
cat > team-training-agenda.md << 'EOF'
# SecretZero Training Agenda

## Session 1: Overview (1 hour)
- What is SecretZero?
- Why we migrated
- Benefits and features
- Architecture overview

## Session 2: Daily Operations (1 hour)
- Adding new secrets
- Rotating secrets
- Troubleshooting common issues
- Where to get help

## Session 3: Advanced Topics (1 hour)
- Multi-cloud secret management
- Compliance and auditing
- Integration with CI/CD
- Best practices

## Hands-On Lab (1 hour)
- Create Secretfile.yml
- Add a new secret
- Rotate a secret
- Use secrets in application

## Resources
- Documentation: docs/SECRET_MANAGEMENT.md
- Example configurations: examples/
- Slack channel: #secretzero-support
EOF

# 4. Post-migration review
cat > post-migration-review.md << 'EOF'
# Post-Migration Review

## Metrics
- Total secrets migrated: X
- Migration duration: Y days
- Downtime: 0 minutes
- Issues encountered: Z

## Successes
- Zero downtime migration
- All secrets successfully migrated
- Team adopted new process
- Improved security posture

## Challenges
- Initial IAM permission issues
- Some secrets had special characters
- Jenkins integration required custom work

## Improvements for Future
- Better upfront planning for permissions
- Automated testing before migration
- More comprehensive documentation

## Recommendations
- Continue using SecretZero for all new secrets
- Schedule regular rotation audits
- Conduct quarterly training for new team members
- Implement automated compliance checks in CI/CD
EOF
```

## Best Practices

1. **Start Small, Scale Gradually** - Begin with a pilot migration of non-critical services to validate the process. Learn from the pilot experience before migrating production services. This reduces risk and builds team confidence.

2. **Maintain Parallel Operation** - Keep old and new secret systems running simultaneously during migration. Allow 1-2 weeks of parallel operation to ensure stability before decommissioning old systems. This provides a safety net for rollback if needed.

3. **Comprehensive Backups** - Create encrypted backups of all secrets before migration. Store backups securely offline. Test backup restoration procedures. Maintain backups for at least 90 days after migration completion.

4. **Document Everything** - Maintain detailed documentation of the migration process, including runbooks, rollback procedures, and team contacts. Update documentation as you learn from each migration phase. Share knowledge with the entire team.

5. **Gradual Cutover** - Use phased rollouts for high-traffic services (25% → 50% → 75% → 100%). Monitor metrics at each phase before proceeding. Be prepared to rollback if issues arise. Schedule migrations during low-traffic periods.

6. **Validation at Every Step** - Validate configuration before syncing. Verify secrets after creation. Test application functionality after migration. Monitor for 24-48 hours before proceeding to next service.

7. **Team Communication** - Notify all stakeholders before migration. Provide daily updates during migration. Hold post-migration retrospectives. Maintain a migration status dashboard.

8. **Migration Windows** - Schedule migrations during maintenance windows when possible. Have on-call team available during migration. Communicate expected duration and potential impact. Have rollback plan ready.

9. **Automated Testing** - Create automated tests to verify secret availability. Test application functionality with new secrets. Run smoke tests after each migration step. Monitor key metrics continuously.

10. **Post-Migration Monitoring** - Monitor application metrics for at least 1 week. Check secret access patterns. Review error logs daily. Set up alerts for anomalies. Document any issues and resolutions.

## Troubleshooting

### Migration Validation Failed

**Problem**: `secretzero validate` fails with configuration errors

**Solutions**:

```bash
# Check syntax errors
secretzero validate --verbose

# Common issues:
# 1. Invalid YAML syntax
yamllint Secretfile.yml

# 2. Missing required fields
secretzero validate --show-errors

# 3. Invalid provider configuration
secretzero test

# Fix configuration and retry
vim Secretfile.yml
secretzero validate
```

### Secrets Not Importing Correctly

**Problem**: Imported secrets have wrong values or format

**Solutions**:

```bash
# Verify source secrets
# AWS SSM
aws ssm get-parameter --name /production/myapp/secret --with-decryption

# Check imported values in SecretZero
secretzero list --show-values --secret secret_name

# Common issues:
# 1. Base64 encoding/decoding
# 2. Special characters in values
# 3. Multi-line secrets

# Re-import with correct handling
# For base64:
export SECRET_VALUE=$(echo $ENCODED_VALUE | base64 -d)

# For multi-line:
export SECRET_VALUE=$(cat secret-file.txt)
```

### Application Can't Find New Secrets

**Problem**: Applications fail after migration with secret not found errors

**Solutions**:

```bash
# Verify secret exists
aws secretsmanager get-secret-value --secret-id production/myapp/secret

# Check application configuration
# Old: DATABASE_URL from .env
# New: DATABASE_URL from AWS Secrets Manager

# Update application code:
# Before:
# database_url = os.environ['DATABASE_URL']
# 
# After:
# import boto3
# secrets_client = boto3.client('secretsmanager')
# response = secrets_client.get_secret_value(SecretId='production/myapp/database-url')
# database_url = response['SecretString']

# Or use SecretZero to maintain .env file:
targets:
  - provider: local
    kind: file
    config:
      path: .env
      format: dotenv
```

### Rollback Needed

**Problem**: Migration causes issues, need to rollback

**Solutions**:

```bash
# 1. Stop new secret sync
# Remove new targets from Secretfile.yml temporarily

# 2. Restore from backup
gpg -d secrets-backup-20240115.tar.gz.gpg | tar -xzf -

# 3. Restore old secrets
# AWS SSM
aws ssm put-parameter --name /production/myapp/secret \
  --value "$(jq -r '.Parameter.Value' backup/secret.json)" \
  --type SecureString --overwrite

# Kubernetes
kubectl apply -f backup/kubernetes-secrets.yaml

# 4. Update application to use old secrets
# Revert application code changes

# 5. Verify application works
curl http://myapp/health

# 6. Document rollback
cat >> MIGRATION_LOG.md << 'EOF'
## Rollback - $(date)
- Reason: <issue description>
- Services affected: <list>
- Secrets restored: <list>
- Action items: <next steps>
EOF
```

### Performance Issues After Migration

**Problem**: Applications slower after migrating to cloud secret storage

**Solutions**:

```bash
# Issue: API calls to Secrets Manager on every request

# Solution 1: Implement caching
pip install aws-secretsmanager-caching

# Python example:
from aws_secretsmanager_caching import SecretCache
cache = SecretCache()
secret = cache.get_secret_string('production/myapp/secret')

# Solution 2: Load secrets at startup
# Instead of loading on every request
def load_secrets_at_startup():
    global secrets
    secrets = {
        'database_url': get_secret('production/myapp/database-url'),
        'api_key': get_secret('production/myapp/api-key')
    }

# Solution 3: Use environment variables
# SecretZero can sync to .env file
targets:
  - provider: local
    kind: file
    config:
      path: .env
      format: dotenv
      merge: true

# Application loads from .env as before
```

### Compliance Issues After Migration

**Problem**: Auditors flag missing compliance controls

**Solutions**:

```bash
# Add compliance metadata to migrated secrets
secretzero policy --check-compliance

# Update Secretfile.yml with compliance requirements
metadata:
  compliance:
    - soc2
    - iso27001

policies:
  compliance_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true

# Add required tags
targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: production/myapp/secret
      tags:
        DataClassification: sensitive
        Owner: platform-team
        Compliance: soc2,iso27001
        RotationPeriod: 90d

# Generate compliance report
secretzero compliance-report --framework soc2
```

### Partial Migration State

**Problem**: Migration incomplete, some services on old system, some on new

**Solutions**:

```bash
# Track migration status
cat > migration-status.sh << 'EOF'
#!/bin/bash

echo "Migration Status Report"
echo "======================"

# Check each service
SERVICES=("service-a" "service-b" "service-c")

for service in "${SERVICES[@]}"; do
  echo "$service:"
  
  # Check if using SecretZero
  if [ -f "$service/Secretfile.yml" ]; then
    echo "  ✓ SecretZero configured"
  else
    echo "  ✗ Not migrated"
  fi
  
  # Check secrets in cloud
  SECRET_COUNT=$(aws secretsmanager list-secrets \
    --filters Key=name,Values="production/$service" \
    --query 'SecretList | length(@)')
  echo "  Secrets in cloud: $SECRET_COUNT"
  
done
EOF

chmod +x migration-status.sh
./migration-status.sh

# Create migration priority list
# Focus on completing high-priority services first
```

### Secret Version Conflicts

**Problem**: Old application version tries to use rotated secret

**Solutions**:

```bash
# Enable versioning in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id production/myapp/secret \
  --secret-string "new-value"

# Old applications can still access previous version
aws secretsmanager get-secret-value \
  --secret-id production/myapp/secret \
  --version-stage AWSPREVIOUS

# In SecretZero, use one_time for critical secrets during migration
secrets:
  - name: critical_secret
    kind: static
    one_time: true  # Don't auto-rotate during migration
    rotation_period: 90d
    config:
      default: ${CURRENT_VALUE}

# After all apps migrated, remove one_time flag
```

## Complete Example

Full migration from environment variables to SecretZero:

```yaml
# Secretfile.yml - Complete Migration Example
version: '1.0'

metadata:
  project: production-app
  owner: platform-team
  migrated_from: environment-variables
  migration_date: "2024-01-15"
  migration_phase: complete
  description: |
    Complete migration from .env files to SecretZero with AWS Secrets Manager.
    Maintains backward compatibility during transition period.

variables:
  environment: production
  app_name: myapp
  aws_region: us-east-1

providers:
  # AWS Secrets Manager (primary)
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: ${aws_region}
  
  # Local files (backward compatibility)
  local:
    kind: local

secrets:
  # 1. Database credentials
  - name: database_credentials
    kind: templates.database_creds_migrated
    rotation_period: 90d

  # 2. API keys
  - name: external_api_keys
    kind: templates.api_keys_migrated
    rotation_period: 90d

  # 3. Application secrets
  - name: application_secrets
    kind: templates.app_secrets_migrated
    rotation_period: 90d

  # 4. Service accounts
  - name: service_account
    kind: templates.service_account_migrated
    rotation_period: 180d

templates:
  # Database credentials template
  database_creds_migrated:
    description: Database credentials migrated from .env
    fields:
      host:
        generator:
          kind: static
          config:
            default: ${DB_HOST}
      port:
        generator:
          kind: static
          config:
            default: ${DB_PORT}
      database:
        generator:
          kind: static
          config:
            default: ${DB_NAME}
      username:
        generator:
          kind: static
          config:
            default: ${DB_USERNAME}
      password:
        generator:
          kind: static
          config:
            default: ${DB_PASSWORD}
      url:
        generator:
          kind: static
          config:
            default: postgresql://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
    targets:
      # AWS Secrets Manager (primary)
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/database/credentials
          description: Database credentials (migrated from .env)
          kms_key_id: arn:aws:kms:${aws_region}:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            MigratedFrom: environment-variables
            MigrationDate: "2024-01-15"
            DataClassification: sensitive
            Owner: database-team
      
      # Local .env (backward compatibility)
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
          comment: "Managed by SecretZero - Do not edit manually"

  # API keys template
  api_keys_migrated:
    description: API keys migrated from .env
    fields:
      stripe_api_key:
        generator:
          kind: static
          config:
            default: ${STRIPE_API_KEY}
      sendgrid_api_key:
        generator:
          kind: static
          config:
            default: ${SENDGRID_API_KEY}
      twilio_auth_token:
        generator:
          kind: static
          config:
            default: ${TWILIO_AUTH_TOKEN}
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/api-keys
          description: Third-party API keys (migrated from .env)
          tags:
            MigratedFrom: environment-variables
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # Application secrets template
  app_secrets_migrated:
    description: Application secrets migrated from .env
    fields:
      secret_key:
        generator:
          kind: static
          config:
            default: ${SECRET_KEY}
      jwt_secret:
        generator:
          kind: static
          config:
            default: ${JWT_SECRET}
      encryption_key:
        generator:
          kind: static
          config:
            default: ${ENCRYPTION_KEY}
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/application-secrets
          description: Application runtime secrets (migrated from .env)
          tags:
            MigratedFrom: environment-variables
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # Service account template
  service_account_migrated:
    description: Service account migrated from .env
    fields:
      account_id:
        generator:
          kind: static
          config:
            default: ${SERVICE_ACCOUNT_ID}
      api_key:
        generator:
          kind: static
          config:
            default: ${SERVICE_ACCOUNT_API_KEY}
      api_secret:
        generator:
          kind: static
          config:
            default: ${SERVICE_ACCOUNT_API_SECRET}
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/service-account
          description: Service account credentials (migrated from .env)
          tags:
            MigratedFrom: environment-variables
      - provider: local
        kind: file
        config:
          path: .service-account.json
          format: json
```

Migration execution:

```bash
# 1. Set environment variables from current .env
set -a
source .env
set +a

# 2. Validate configuration
secretzero validate

# 3. Test provider connectivity
secretzero test

# 4. Backup current .env
cp .env .env.backup.$(date +%Y%m%d)

# 5. Dry run
secretzero sync --dry-run

# 6. Execute migration
secretzero sync

# 7. Verify secrets
# AWS
aws secretsmanager list-secrets \
  --query 'SecretList[?starts_with(Name, `production/myapp`)].Name'

# Local
cat .env
cat .service-account.json

# 8. Test application
curl http://localhost:8000/health

# 9. Monitor for 24 hours
./monitor-application.sh

# 10. Phase 2: Remove local file targets (after validation)
# Edit Secretfile.yml and remove local provider targets
# Update application to read from AWS Secrets Manager directly

# 11. Final sync
secretzero sync

# 12. Decommission .env files
rm .env .env.backup.*
```

## Next Steps

- **[Kubernetes Integration](kubernetes.md)** - Migrate Kubernetes secrets
- **[Multi-Cloud Setup](multi-cloud.md)** - Extend to multiple cloud providers
- **[Compliance Scenarios](compliance.md)** - Ensure compliance during migration
- **[GitHub Actions](github-actions.md)** - Integrate with CI/CD pipelines
