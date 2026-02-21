# AWS Secrets Manager Target

SecretZero supports AWS Secrets Manager for centralized secret storage in AWS.
This target complements SSM Parameter Store by offering secret rotation and
versioning features.

## Configuration

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `name` | string | Yes | Secrets Manager secret name |
| `description` | string | No | Optional description |
| `kms_key_id` | string | No | Optional KMS key for encryption |

## Example

```yaml
targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: /prod/api/key
      description: API key for production
```

## Related

- [AWS Targets](aws.md)
