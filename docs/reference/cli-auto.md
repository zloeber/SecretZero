# CLI Command Reference (Auto-Generated)

This page demonstrates auto-generated CLI documentation using the `mkdocs-click` plugin.

## Complete CLI Reference

::: mkdocs-click
    :module: secretzero.cli
    :command: main
    :prog_name: secretzero
    :depth: 2
    :style: table

## Individual Command Documentation

### sync command

::: mkdocs-click
    :module: secretzero.cli
    :command: main
    :prog_name: secretzero
    :depth: 1
    :list_subcommands: False

### validate command

Full details for the `validate` subcommand:

::: mkdocs-click
    :module: secretzero.cli
    :command: validate
    :prog_name: secretzero validate
    :depth: 0

### rotate command

Full details for the `rotate` subcommand:

::: mkdocs-click
    :module: secretzero.cli
    :command: rotate
    :prog_name: secretzero rotate
    :depth: 0

## Usage Notes

The documentation above is automatically generated from the Click command definitions in `src/secretzero/cli.py`. Any changes to the CLI commands, options, or help text will automatically be reflected here.

### Customization Options

The `mkdocs-click` plugin supports several options:

- **`:depth:`** - How many subcommand levels to include (0 = command only, 1 = command + subcommands, 2 = all levels)
- **`:style:`** - Display style (`plain`, `table`, or custom)
- **`:list_subcommands:`** - Whether to list subcommands (default: True)
- **`:prog_name:`** - The program name to display in usage examples

### Integration Examples

#### Embed in Existing Pages

You can embed auto-generated CLI docs within your existing documentation:

```markdown
# Sync Command

Some introductory text about the sync command...

## Command Reference

::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0

## Additional Notes

Your custom notes and examples here...
```

#### Create Command-Specific Pages

For each command, create a dedicated page with:

1. High-level overview
2. Auto-generated reference
3. Detailed examples
4. Best practices

#### Table-Style Output

Use `:style: table` for a clean, scannable reference:

```markdown
::: mkdocs-click
    :module: secretzero.cli
    :command: main
    :prog_name: secretzero
    :depth: 2
    :style: table
```

## Benefits

- ✅ **Always up-to-date**: Docs sync automatically with code changes
- ✅ **Consistent**: Same format across all commands
- ✅ **Complete**: All options, arguments, and help text included
- ✅ **Maintainable**: Single source of truth (your Click commands)
- ✅ **Searchable**: Full-text search works on auto-generated content
