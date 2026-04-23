# Multi-Environment Best Practices

- Keep a shared base Secretfile
- Override only what must change per environment
- Use distinct target paths for isolation
- Validate in CI before promotion
- Use authentication policies to ensure secrets are seeded to the proper targets
- Use environments with mapped szvar files and target profiles to have the same secret definition for multiple environments 
