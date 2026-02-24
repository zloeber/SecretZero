# Integrating Auto-Generated CLI Documentation

This guide shows you how to integrate `mkdocs-click` auto-generated documentation into your existing CLI reference pages.

## Installation

The `mkdocs-click` plugin has been added to your dependencies. Install it with:

```bash
# Install docs dependencies
uv sync --extra docs

# Or if using pip
pip install mkdocs-click
```

## Basic Usage

### Full CLI Tree

To generate documentation for your entire CLI with all subcommands:

```markdown
::: mkdocs-click
    :module: secretzero.cli
    :command: main
    :prog_name: secretzero
    :depth: 2
```

### Single Command

To document a specific command:

```markdown
::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0
```

### With Table Style

For a cleaner, more readable format:

```markdown
::: mkdocs-click
    :module: secretzero.cli
    :command: main
    :prog_name: secretzero
    :depth: 2
    :style: table
```

## Integration Patterns

### Pattern 1: Hybrid Pages (Recommended)

Combine manual content with auto-generated reference:

```markdown
# secretzero sync

Generate and synchronize secrets to targets.

## Overview

The `sync` command is the workhorse of SecretZero. It reads your Secretfile,
generates secrets according to configured generators, and deploys them to
all specified targets.

### Key Features

- ✅ Idempotent - safe to run multiple times
- ✅ Dry-run mode for preview
- ✅ Selective sync with `--secret` flag
- ✅ Variable file support

## Command Reference

::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0
    :style: table

## Examples

### Basic Usage

\`\`\`bash
# Sync all secrets
secretzero sync

# Sync specific secrets only
secretzero sync --secret db_password --secret api_key
\`\`\`

### Advanced Usage

\`\`\`bash
# Sync with variable overrides
secretzero sync --var-file prod.szvar

# Preview changes
secretzero sync --dry-run

# Clean orphaned lockfile entries
secretzero sync --clean
\`\`\`

## Best Practices

1. **Always test with --dry-run first** in production
2. **Use --clean periodically** to remove orphaned lockfile entries
3. **Commit lockfiles** to version control for change tracking
4. **Use variable files** for environment-specific overrides

## Related Commands

    - [`secretzero validate`](../user-guide/cli/validate.md) - Validate before syncing
    - [`secretzero status`](../user-guide/cli/status.md) - Check sync status
    - [`secretzero rotate`](../user-guide/cli/rotate.md) - Rotate existing secrets
```

### Pattern 2: Separate Auto-Generated Section

Keep manual docs separate from auto-generated reference:

```markdown
# CLI Reference

## Manual Documentation

Browse detailed guides for each command:

    - [sync](../user-guide/cli/sync.md) - Generate and sync secrets
    - [validate](../user-guide/cli/validate.md) - Validate configuration
    - [rotate](../user-guide/cli/rotate.md) - Rotate secrets

## Complete Command Reference

Auto-generated reference for all commands:

::: mkdocs-click
    :module: secretzero.cli
    :command: main
    :prog_name: secretzero
    :depth: 2
    :style: table
```

### Pattern 3: Per-Command Auto Pages

Create individual auto-generated pages:

**docs/reference/cli/auto/sync.md:**

```markdown
# sync - Auto-Generated Reference

::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0
    :style: table

    [← Back to manual documentation](../user-guide/cli/sync.md)
```

## Updating Existing Pages

Here's how to update your current CLI documentation pages:

### Example: Update sync.md

Add this section after your examples:

```markdown
## Command Reference (Auto-Generated)

::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0
    :style: table

---

*This section is automatically generated from the source code.*
```

### Example: Update index.md

Add a section linking to auto-generated reference:

```markdown
## Quick Reference (Auto-Generated)

Complete auto-generated CLI reference with all options:

::: mkdocs-click
    :module: secretzero.cli
    :command: main
    :prog_name: secretzero
    :depth: 1
    :list_subcommands: True
```

## Configuration Options

### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `:module:` | Python module containing Click commands | Required |
| `:command:` | Click command/group name | Required |
| `:prog_name:` | Program name shown in usage | Command name |
| `:depth:` | Subcommand depth to include (0-2) | `0` |
| `:style:` | Output style (`plain` or `table`) | `plain` |
| `:list_subcommands:` | Show subcommand list | `True` |

### Style Comparison

**Plain style** (`:style: plain`):
- More detailed
- Includes full help text
- Better for single command pages

**Table style** (`:style: table`):
- More compact
- Easier to scan
- Better for command overviews

## Navigation Setup

Add the auto-generated page to your navigation in `mkdocs.yml`:

```yaml
nav:
  - Reference:
      - reference/index.md
      - CLI Reference (Manual): reference/cli.md
      - CLI Reference (Auto): reference/cli-auto.md
      - Architecture: reference/architecture.md
```

## Troubleshooting

### Import Errors

If you see "Module not found" errors:

1. Ensure `src` is in your Python path
2. Check the module path is correct
3. Verify the command name matches your Click commands

### Outdated Documentation

The documentation updates automatically when you:

1. Run `mkdocs build` or `mkdocs serve`
2. The plugin reads the current code

To force a refresh:

```bash
mkdocs build --clean
```

### Missing Commands

If commands don't appear:

1. Check the `:depth:` setting
2. Verify the command is defined in the specified module
3. Ensure it's a Click command/group

## Next Steps

1. ✅ **Install dependencies**: `uv sync --extra docs`
2. ✅ **Test locally**: `mkdocs serve`
3. ✅ **Update existing pages**: Add auto-generated sections
4. ✅ **Review output**: Ensure formatting looks good
5. ✅ **Commit changes**: Update your documentation

## Examples

See [reference/cli-auto.md](../reference/cli-auto.md) for a complete working example with multiple patterns.
