# SecretZero AI Agent Features Implementation Prompt

You are implementing AI agent enhancement features for SecretZero. These features make SecretZero more useful for automated workflows and AI coding agents.

## Context

SecretZero is a secrets orchestration engine. We're enhancing it to be more agent-friendly by adding:
- Structured output (JSON) for easier parsing
- Better error signaling (exit codes)
- Query capabilities (list, inspect commands)
- Planning/preview modes
- Configuration helpers

Reference the [feature task list](../.github/feature-tasks.md) for complete feature specifications.

## Implementation Guidelines

### 1. JSON Output Format

When adding `--output json` to commands:

```python
@command()
@click.option(
    "--output",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def my_command(output: str):
    """Command description."""
    result = {"status": "success", "data": {...}}
    
    if output == "json":
        console.print(json.dumps(result, indent=2))
    else:
        # Pretty print for humans
        display_human_readable(result)
```

Define a schema for each command's JSON output:

```python
# schemas.py
class CommandOutput(BaseModel):
    status: str  # "success", "error", "warning"
    data: dict[str, Any]
    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
```

### 2. Exit Codes

Use consistent exit codes throughout:

```python
# Typical execution pattern
try:
    result = perform_operation()
    if result.success:
        sys.exit(0)
    elif result.has_drift:
        console.print("[warning]Drift detected[/warning]")
        sys.exit(4)
except ConfigValidationError:
    console.print("[red]Config error[/red]")
    sys.exit(1)
except MissingDependencyError:
    console.print("[red]Missing dependency[/red]")
    sys.exit(2)
except AuthenticationError:
    console.print("[red]Auth failed[/red]")
    sys.exit(3)
except Exception:
    console.print("[red]Unknown error[/red]")
    sys.exit(127)
```

### 3. Dry-Run / Plan Mode

Show what would happen:

```python
class OperationPlan(BaseModel):
    operations: list[Operation]
    summary: dict[str, int]  # created, updated, deleted, unchanged
    estimated_duration: float


class Operation(BaseModel):
    action: str  # "create", "update", "delete", "skip"
    resource_type: str
    resource_name: str
    details: dict[str, Any]
    affected_targets: list[str]
    risk_level: str  # "low", "medium", "high"
```

### 4. List Commands

Create consistent list command outputs:

```python
@main.command()
@click.argument("resource", type=click.Choice(["secrets", "providers", "targets", "variables"]))
@click.option("--output", type=click.Choice(["text", "json"]), default="text")
def list(resource: str, output: str):
    """List secrets, providers, targets, or variables."""
    config = load_config()

    if resource == "secrets":
        items = [
            {"name": s.name, "kind": s.kind, "targets": len(s.targets)} for s in config.secrets
        ]
    # ... etc

    if output == "json":
        console.print(json.dumps(items, indent=2))
    else:
        # Display as table
        table = Table()
        # ... populate table
        console.print(table)
```

### 5. Inspect Commands

Get detailed information about resources:

```python
@main.command()
@click.argument("resource_path")  # "secret:db_password" or "provider:aws" etc
@click.option("--output", type=click.Choice(["text", "json"]), default="text")
def inspect(resource_path: str, output: str):
    """Inspect secret, provider, target, or variable details."""
    # Parse resource_path to get type and name
    item = get_resource(resource_path)
    result = item.model_dump(mode="python", exclude_none=True)
    
    if output == "json":
        console.print(json.dumps(result, indent=2))
    else:
        display_details(item)
```

### 6. Testing

Add tests for new features:

```python
def test_command_json_output(temp_secretfile):
    runner = CliRunner()
    result = runner.invoke(cli, ["command_name", "--output", "json", "--file", temp_secretfile])

    assert result.exit_code == 0
    output_data = json.loads(result.output)
    assert output_data["status"] == "success"
    assert "data" in output_data


def test_exit_code_on_error():
    runner = CliRunner()
    result = runner.invoke(cli, ["command_name", "--file", "nonexistent.yml"])

    assert result.exit_code == 1  # validation error
```

### 7. Documentation

Document new features:

```markdown
## JSON Output

All commands support `--output json` for machine-readable results:

\`\`\`bash
secretzero validate --output json
\`\`\`

### Output Schema

\`\`\`json
{
  "status": "success|error|warning",
  "data": { ... },
  "errors": [ ... ],
  "warnings": [ ... ],
  "metadata": { ... }
}
\`\`\`

## Exit Codes

- `0`: Success
- `1`: Validation error
- `2`: Missing dependency
- `3`: Authentication failure
- `4`: Drift detected
- `127`: Unknown error
```

## Priority & Milestones

### Milestone 1: Foundation (1-2 weeks)
- [ ] JSON output for validate, status, sync, render
- [ ] Exit codes implementation
- [ ] Plan/dry-run mode for sync

### Milestone 2: Query (1-2 weeks)
- [ ] list secrets/providers/targets/variables
- [ ] inspect command
- [ ] JSON output for all

### Milestone 3: Advanced (2-3 weeks)
- [ ] Dependency/impact commands
- [ ] Config generation helpers
- [ ] Batch operations
- [ ] API enhancements

## Code Quality Standards

- All new code must have type hints
- Comprehensive docstrings for public functions
- Pydantic models for structured output
- >80% test coverage
- JSON output validated against schema
- Exit codes documented and tested

## Resources

- [Feature Task List](../.github/feature-tasks.md) - Detailed feature specifications
- [CLI Reference](../docs/reference/cli.md) - Current CLI documentation
- [Architecture](../docs/reference/architecture.md) - System design
- [Copilot Instructions](./copilot-instructions.md) - Project guidelines

## Questions to Ask Yourself

1. **Is the output parseable?** Can an agent extract data without regex?
2. **Are exit codes clear?** Can failures be categorized automatically?
3. **Is it documented?** Can users understand the JSON schema?
4. **Is it tested?** Do tests verify the output format?
5. **Is it backwards compatible?** Do existing commands still work?

## Success Criteria

✅ All commands support `--output json`
✅ Exit codes match specification
✅ Agents can preview changes with `--plan`
✅ Agents can list and inspect without full render
✅ >95% test coverage for new code
✅ Documentation is clear and complete
