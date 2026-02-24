# Quick Start: Auto-Generated CLI Documentation

This guide gets you started with automatic CLI documentation generation in 5 minutes.

## Installation

```bash
# Install mkdocs-click
uv sync --extra docs

# Or with pip
pip install mkdocs-click
```

✅ Already configured in your `mkdocs.yml` and `pyproject.toml`!

## Usage

Add this to any markdown file in your docs:

```markdown
::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0
    :style: table
```

That's it! The CLI documentation will be auto-generated from your Click commands.

## Common Patterns

### Pattern 1: Full CLI Tree

Show all commands and subcommands:

```markdown
::: mkdocs-click
    :module: secretzero.cli
    :command: main
    :prog_name: secretzero
    :depth: 2
    :style: table
```

### Pattern 2: Single Command

Document one specific command:

```markdown
::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0
```

### Pattern 3: Hybrid (Manual + Auto)

Combine manual docs with auto-generated reference:

```markdown
# secretzero sync

Your manual introduction and examples here...

## Command Reference

::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0
    :style: table

## More Examples

Your additional examples and best practices...
```

## Test It

```bash
# Start local docs server
mkdocs serve

# Open browser to http://127.0.0.1:8000
# Navigate to your CLI documentation pages
```

## Configuration Quick Reference

| Option | Description | Example |
|--------|-------------|---------|
| `:module:` | Python module path | `secretzero.cli` |
| `:command:` | Command/group name | `sync` or `main` |
| `:prog_name:` | Display name | `secretzero sync` |
| `:depth:` | Subcommand levels (0-2) | `0` = command only<br>`1` = + subcommands<br>`2` = all levels |
| `:style:` | Output format | `table` or `plain` |

## Examples

See these pages for complete examples:

- [📄 Full Auto-Generated Reference](../reference/cli-auto.md)
- [📄 Integration Guide](../contributing/cli-docs-integration.md)
- [📄 Example: sync command](cli-docs-sync-example.md)

## Benefits

- ✅ Always up-to-date with your code
- ✅ No manual maintenance needed
- ✅ Consistent formatting
- ✅ Complete option coverage
- ✅ Searchable documentation

## Next Steps

1. **Review examples** in [`docs/reference/cli-auto.md`](../reference/cli-auto.md)
2. **Update existing pages** following patterns in [`docs/contributing/cli-docs-integration.md`](../contributing/cli-docs-integration.md)
3. **Test locally** with `mkdocs serve`
4. **Customize** styling and depth as needed

## Documentation

- [mkdocs-click plugin documentation](https://github.com/mkdocs/mkdocs-click)
- [MkDocs documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
