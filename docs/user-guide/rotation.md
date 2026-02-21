# Rotation

Rotation updates secrets on a schedule to reduce exposure risk. SecretZero tracks
rotation state in the lockfile and can enforce rotation policies.

## Basics

- Define `rotation_period` on secrets
- Use `secretzero rotate` to execute rotation
- Review policy output with `secretzero policy`

## Related

- [Advanced Rotation](../advanced/rotation/index.md)
- [CLI Rotate](cli/rotate.md)
