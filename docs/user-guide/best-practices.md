# Best Practices

Practical guidance for keeping SecretZero configurations secure, reliable, and
maintainable.

## Security

- Avoid logging or printing secret values.
- Prefer provider-backed storage for production environments.
- Use least-privilege credentials for providers and targets.

## Configuration Hygiene

- Keep Secretfiles small and modular.
- Use variables for environment differences.
- Validate configurations with `secretzero validate` in CI.

## Operations

- Schedule regular rotation using policies.
- Monitor drift and remediate promptly.
- Track changes through the lockfile.

## Next Steps

- Review [Rotation](rotation.md)
- See [Use Cases](../use-cases/index.md)
