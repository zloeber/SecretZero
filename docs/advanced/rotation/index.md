# Secret Rotation

Rotation reduces exposure risk by periodically regenerating secrets and updating
all targets.

## Core Concepts

- Define `rotation_period` on secrets
- Rotation state is tracked in the lockfile
- Policies can enforce rotation windows

## Related

- [Rotation Policies](policies.md)
- [Automated Rotation](automation.md)
- [Best Practices](best-practices.md)
- [CLI Rotate](../../user-guide/cli/rotate.md)
