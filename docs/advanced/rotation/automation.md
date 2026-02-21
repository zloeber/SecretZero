# Automated Rotation

Automate rotation with scheduled jobs or CI/CD pipelines.

## Example Schedule

```bash
# Weekly rotation check
secretzero rotate --check
```

## Recommendations

- Run in a controlled environment with provider credentials
- Review changes in dry-run before forcing updates
- Notify downstream systems after rotation
