# Secret Generators

Secret generators define how SecretZero produces values. Each secret chooses a generator and
its configuration, then targets receive the generated result.

## Available Generators

- [Password Generator](password.md)
- [Random String](string.md)
- [Static Values](static.md)
- [Script Generator](script.md)

## Common Configuration

Generator configuration typically lives under `generator` or `generator_config` blocks:

```yaml
secrets:
  - name: api_key
    generator: random_string
    generator_config:
      length: 64
```

## Next Steps

- Review [Secretfile configuration](../configuration/secretfile.md)
- See [Best Practices](../best-practices.md)
