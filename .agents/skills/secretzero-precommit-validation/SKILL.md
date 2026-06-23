---
name: secretzero-precommit-validation
description: |
  Use before completing feature work, after making code changes, or when preparing
  for commit/merge. Runs the full pre-commit validation suite, auto-resolves common
  failures (lint, formatting, test count mismatches), and reports structured results.
  Integration point for verification-before-completion, finishing-a-development-branch,
  and code review workflows.
metadata:
  internal: true
---

# SecretZero Pre-Commit Validation Skill

Use this skill to validate code quality and test coverage before completing any feature work, committing changes, or preparing for code review.

## When to Use

**MUST use before**:
- Completing feature implementation
- Creating a commit or PR
- Claiming work is ready for review
- Merging code to main

**Triggers**:
- "run pre-commit", "run pre-commit tests", "validate before commit"
- "complete the feature", "finish this work", "ready to commit"
- Automatic gate in `verification-before-completion` or `finishing-a-development-branch` skills

## What It Does

The skill executes the full pre-commit validation suite:

1. **Linting** (`task lint`): Python static analysis, unused variables, code quality
2. **Testing** (`task test`): Full pytest suite (1180+ tests)
3. **Formatting** (auto): Black code formatting on violations
4. **Schema validation**: Secretfile manifests
5. **Documentation links** (optional): Hyperlink validation

### Output

Returns a structured report:

```json
{
  "status": "passed" | "failed",
  "tests_passed": 1180,
  "tests_failed": 0,
  "lint_issues": 0,
  "formatting_fixed": 0,
  "failures": [],
  "details": "All checks passed! Ready for commit."
}
```

## Common Failures & Auto-Resolution

### Unused Variable Warnings

**Symptom**: `F841 Local variable 'x' is assigned but never used`

**Resolution**: The skill auto-identifies and removes unused variable assignments. Example:

```python
# Before
style_name = style.get("Style Category", "")  # Assigned but never used
keywords = style.get("Keywords", "")          # Used

# After
keywords = style.get("Keywords", "")          # Only used variables remain
```

### Code Formatting Issues

**Symptom**: `would reformat /path/to/file.py`

**Resolution**: Auto-runs `task format` and re-validates.

### Test Count Mismatches

**Symptom**: Test expects 5 capabilities but finds 6 (or vice versa)

**Resolution**: The skill identifies the mismatch and provides guidance:

```
AWS provider now has 6 capabilities (added retrieve_iam_user_credentials).
Update test assertion from len(capabilities) == 5 to == 6
Add assertion: assert caps.get_capability("retrieve_iam_user_credentials") is not None
```

### Schema Validation Failures

**Symptom**: Secretfile manifests invalid or out of sync with schema

**Resolution**: Runs `task schema:update` to regenerate schema and example files.

## Invocation

### Direct Usage (Standalone)

```bash
# Run and report results
./scripts/agent.pre-commit.sh --mode full

# Quick validation (lint + format only)
./scripts/agent.pre-commit.sh --mode fast
```

### Within a Skill Workflow

When called by another skill (e.g., `verification-before-completion`):

1. **Executes validation suite**
2. **Catches and auto-resolves common failures** (formatting, unused vars)
3. **Reports pass/fail with structured output**
4. **Guides user through manual fixes if needed** (test count updates, etc.)

Example from `verification-before-completion`:

```markdown
## ✅ Pre-Commit Validation Passed

- All 1180 tests passed ✓
- Linting clean ✓
- Formatting applied ✓
- Ready for commit
```

Example from `finishing-a-development-branch` (auto-gate):

```markdown
Pre-commit validation is required before merge. Running now...

[Output shows failures + auto-fixes applied]

Retry validation...

[All checks now pass]

Proceeding with branch completion.
```

## Integration Points

### With `verification-before-completion` Skill

```
completion-claimed → invoke this skill → pass? → proceed : halt + guide fixes
```

### With `finishing-a-development-branch` Skill

```
merge/squash → validate pre-commit required → invoke skill → all pass? → complete : retry
```

### With `requesting-code-review` Skill

```
ready for review → validate pre-commit → pass? → create PR : request fixes
```

### Manual Workflow

```bash
# Make changes
# ... code work ...

# Validate before commit
task lint && task test

# Or use the skill for auto-resolution
./scripts/agent.pre-commit.sh --mode full
```

## Failure Categories & Guidance

| Category | Example | Auto-Resolved? | Guidance |
|----------|---------|---|---|
| **Unused variables** | F841 in linting | ✅ Yes | Removed from code |
| **Code formatting** | Black violations | ✅ Yes | Auto-formatted via `task format` |
| **Test count mismatch** | Expected 5, got 6 | ⚠️ Partial | Identifies issue; user updates assertion |
| **Import errors** | Missing dependency | ❌ No | Install via `uv pip install` |
| **Logic errors** | Test assertion fails | ❌ No | User debugs test logic |
| **Schema drift** | Secretfile.yml vs schema | ✅ Yes | Regenerated via `task schema:update` |

## Output Interpretation

**PASSED** (All green):
```
====================== 1180 passed, 23 warnings in 12.76s ======================
All checks passed!
✓ Secretfile is valid
[Ready for commit]
```

**FAILED** (Issues found):
```
Found 3 errors.
1 file would be reformatted.
FAILED tests/test_X.py::TestY::test_z - assert 6 == 5
```

When failures occur:
1. Skill auto-resolves what it can (formatting, unused vars)
2. Re-runs validation
3. Reports remaining issues with guidance
4. If all resolved → report success
5. If manual fixes needed → show what user needs to fix

## Exit Codes

- **0**: All checks passed ✅
- **1**: Checks failed, some auto-resolved but manual fixes needed
- **201**: Timeout or severe error (rare; usually schema or dependency issue)

## Context Efficiency

This skill is designed to be lightweight for agents:
- ✅ Handles output parsing internally (no manual log parsing)
- ✅ Auto-resolves common issues
- ✅ Returns structured results (JSON-friendly)
- ✅ Works across sessions without setup
- ✅ Integrates seamlessly with other skills

**For users**: Just invoke it. The skill handles the rest.

**For other skills**: Can call this skill to guarantee pre-commit state before proceeding (e.g., `finishing-a-development-branch` auto-gates on validation pass).

## Related Skills

- **`verification-before-completion`**: Calls this skill as part of completion verification
- **`finishing-a-development-branch`**: Uses this as a hard gate before merge
- **`requesting-code-review`**: Validates pre-commit passes before creating PR
