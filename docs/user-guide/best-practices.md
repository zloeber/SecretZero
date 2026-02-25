# Best Practices

Practical guidance for keeping SecretZero configurations secure, reliable, and maintainable.

## Security

- **Avoid logging or printing secret values** - Use masked representations when debugging
- **Prefer provider-backed storage** for production environments
- **Use least-privilege credentials** for providers and targets
- **Never commit secrets** to version control - use `.env` files and targets instead
- **Rotate secrets regularly** - Set appropriate rotation policies based on sensitivity
- **Audit secret access** - Monitor and log who accesses secrets and when

## AI-Assisted Discovery & Privacy

When using the `discover` command to identify secrets in your project:

### Use Local Models (Recommended)

✅ **Best Practice**: Use local AI models via Ollama for all analysis

```bash
# Default behavior - all processing is local
secretzero discover

# Explicitly ensure local-only processing
secretzero discover --local-only
```

**Benefits of local models:**
- 🔒 Zero data leaves your machine
- 🔒 Protected intellectual property
- 🔒 No API costs
- 🔒 Works offline
- 🔒 Faster analysis once model is downloaded

### Setup Local AI (Ollama)

```bash
# Install Ollama (https://ollama.ai)
# Then:

# Start Ollama server
ollama serve

# In another terminal, download a model
ollama pull llama3.2:3b

# Now discovery works locally
secretzero discover
```

### Avoid Remote APIs Unless Necessary

❌ **Avoid using remote LLM providers** unless you:
- Explicitly need their superior accuracy
- Understand their data retention policies
- Have approved sending project structure/patterns to external services
- Are in a non-sensitive environment

```bash
# Only use if you've made an informed decision
secretzero discover --provider openai --model gpt-4
```

### When You Must Use Remote APIs

If you choose to use OpenAI, Anthropic, or other remote providers:

1. **Review their privacy policies** - Understand data usage and retention
2. **Sanitize patterns** - Manually review generated `Secretfile.detect.yml` for sensitive details
3. **Use minimal configuration** - Don't scan unnecessary files
4. **Limit scope** - Use `--exclude-patterns` to reduce data sent
5. **Approval workflow** - Require team approval before using remote providers in CI/CD

## Configuration Hygiene

- **Keep Secretfiles small and modular** - One per environment or service
- **Use variables for environment differences** - Avoid duplication
- **Validate configurations with CI** - Run `secretzero validate` in your CI/CD pipeline
- **Use `.gitignore` properly** - Exclude `.env`, lockfiles, and sensitive files
- **Document secret usage** - Add comments explaining what each secret is for
- **Version your Secretfiles** - Treat them like code in version control (as encrypted/redacted only)

## Operations

- **Schedule regular rotation** - Set appropriate rotation periods based on risk assessment
- **Monitor drift and remediate** - Run `secretzero drift` regularly to catch unauthorized changes
- **Track changes via lockfile** - Git diff the lockfile to understand what changed
- **Test in non-prod first** - Always test secret generation in a dev environment before production
- **Have a rotation playbook** - Document the procedure for rotating compromised secrets
- **Audit secret generation** - Log who generated what and when

## Workflow Recommendations

### Initial Project Setup

```bash
# 1. Discover existing secrets (local analysis)
secretzero discover

# 2. Review and refine discovery results
# Edit Secretfile.detect.yml manually

# 3. Validate the configuration
secretzero validate -f Secretfile.detect.yml

# 4. Test with a dry run
secretzero sync --dry-run

# 5. Deploy to targets
secretzero sync

# 6. Commit lockfile to version control (redacted)
git add .gitsecrets.lock
git commit -m "Initial secrets lockfile"
```

### Regular Maintenance

```bash
# Daily/Weekly: Check for drift
secretzero drift

# Monthly: Review rotation status
secretzero status

# Quarterly: Rotate all secrets
secretzero rotate --dry-run
secretzero rotate

# Before deployment: Validate everything
secretzero validate
secretzero test
```

## Multi-Environment Management

- **Separate Secretfiles** per environment (dev, staging, prod)
- **Use variable files** (`.szvar`) for environment-specific values
- **Avoid sharing credentials** between environments
- **Test rotation** in non-prod before production
- **Document environment differences** in comments

Example structure:

```
.
├── Secretfile.yml              # Shared configuration
├── Secretfile.dev.yml          # Dev overrides
├── Secretfile.prod.yml         # Prod overrides
├── variables.dev.szvar         # Dev variables
├── variables.prod.szvar        # Prod variables
└── .gitsecrets.lock            # Shared lockfile
```

## CI/CD Integration

- **Validate in CI** - Make secret validation a required CI check
- **Never auto-sync** in CI - Require manual approval for secret changes
- **Use service accounts** - Dedicated credentials for CI/CD with minimal permissions
- **Audit credentials** - Log all credential access and changes
- **Rotate CI credentials regularly** - At least quarterly

## Troubleshooting & Debugging

- **Enable verbose mode** - Use `-v` flag for detailed output
- **Check configuration** - Run `secretzero validate` first
- **Test providers** - Run `secretzero test` to verify connectivity
- **Check lockfile** - Understand the lockfile format for debugging
- **Review logs** - Check provider/target logs for specific errors

## Next Steps

- Read [Discover Command Guide](./cli/discover.md) for secret discovery
- Review [Rotation Policies](rotation.md) for automated secret rotation
- See [Use Cases](../use-cases/index.md) for real-world examples
- Explore [Advanced Configuration](configuration/index.md)
