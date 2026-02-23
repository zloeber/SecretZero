# SecretZero AI Agent Enhancement Feature Tasks

Features to improve SecretZero's usefulness for AI coding agents and automated workflows.

## Priority 1: Foundation (High Impact, Straightforward)

### 1. Structured JSON Output Format
**Goal:** Add `--format json` flag to all major commands for machine-readable results

- [x] Add `--format` option to `validate` command
- [x] Add `--format` option to `status` command  
- [x] Add `--format` option to `sync` command
- [x] Add `--format` option to `rotate` command
- [x] Add `--format` option to `policy` command
- [x] Add `--format` option to `drift` command
- [x] Create standard output schema for each command
- [x] Add JSON tests for each command's output

**Why:** Makes it trivial for AI agents to parse results and extract data

---

### 2. Standardized Exit Codes
**Goal:** Use consistent exit codes for different error scenarios

Exit codes:
- `0` = success
- `1` = validation error
- `2` = missing dependency
- `3` = authentication failure
- `4` = drift detected
- `5` = configuration error
- `127` = unknown error

- [x] Implement exit code mapping for each command (EXIT_SUCCESS, EXIT_VALIDATION_ERROR, EXIT_MISSING_DEPENDENCY, EXIT_AUTH_FAILURE, EXIT_DRIFT_DETECTED, EXIT_CONFIG_ERROR, EXIT_UNKNOWN_ERROR)
- [x] Add tests for exit codes
- [ ] Document exit codes in CLI reference guide

**Why:** Enables agents to quickly categorize failures without parsing output

---

### 3. Better Dry-Run / Plan Mode
**Goal:** Show detailed execution plan with `--plan` flag

- [x] Add `--plan` flag to `sync` command
- [x] Implement plan output showing: created, updated, skipped
- [x] Add JSON output support for plans (`--plan --format json`)
- [x] Include affected targets and paths in plan
- [x] Add tests for plan generation

**Why:** Agents can preview changes before executing them

---

## Priority 2: Query & Inspection (Medium Impact, Moderate Effort)

### 4. Query/Inspect Commands
**Goal:** Allow targeted queries without full configuration rendering

- [x] Create `secretzero list` command:
  - [x] `list secrets` - show secret names, kinds, rotation periods
  - [x] `list providers` - show provider types and auth methods
  - [x] `list targets` - show all target destinations
  - [x] `list variables` - show all variables in config
  - [x] Add `--format json` support
  - [x] Add `--filter` search option for secrets and variables

- [ ] Create `secretzero inspect` command:
  - [ ] `inspect secret <name>` - detailed secret info
  - [ ] `inspect provider <name>` - provider config details
  - [ ] `inspect target <provider>/<kind>` - target details
  - [ ] Add `--output json` support

**Why:** Agents can get specific information without parsing full rendered config

---

### 5. Dependency Graph Export
**Goal:** Export configuration dependencies in machine-readable format

- [x] Add `--format json` to `graph` command
- [x] Export graph as JSON with nodes and edges
- [ ] Create `secretzero dependencies` command:
  - [ ] Show what a secret depends on
  - [ ] Show what depends on a variable
  - [ ] Transitive dependencies
- [ ] Add `secretzero impact` command:
  - [ ] Show what secrets change if variable changes
  - [ ] Show cascade effects

**Why:** Agents can understand impact of changes before executing

---

## Priority 3: Configuration Assistance (Medium Impact, Higher Effort)

### 6. Configuration Generation Helpers
**Goal:** Help agents generate or improve SecretZero configs

- [ ] Create `secretzero init` enhancements:
  - [ ] `--from-env` - generate from environment variables
  - [ ] `--from-file` - scan file and generate config
  - [ ] `--interactive` - guided setup wizard
  - [ ] Output to stdout with `--dry-run`

- [x] Create `secretzero detect` command:
  - [x] Scan directory for potential secrets
  - [x] Suggest secret definitions
  - [x] Output as partial Secretfile
  - [x] JSON output format support

- [ ] Create `secretzero suggest` command:
  - [ ] Suggest config improvements
  - [ ] Check for best practices
  - [ ] Recommend rotation periods
  - [ ] Detect missing error handling

**Why:** Agents can assist users in creating better configs

---

### 7. Auto-Environment Detection
**Goal:** Automatically select appropriate .szvar files

- [ ] Detect environment from:
  - [ ] Git branch name
  - [ ] CI/CD environment variables
  - [ ] Deployment context
  - [ ] Explicit `--env` flag
- [ ] Auto-apply matching .szvar files
- [ ] Document environment detection rules

**Why:** Reduces manual configuration in CI/CD and agent workflows

---

## Priority 4: API & Integration (Medium-High Impact, Higher Effort)

### 8. Batch Operations
**Goal:** Execute multiple operations atomically

- [ ] Create batch operation format (JSON)
- [ ] Implement `secretzero batch <file>` command
- [ ] Support operations: sync, rotate, validate, check-drift
- [ ] Atomic execution with rollback on failure
- [ ] Output detailed results per operation

**Why:** Agents can perform complex workflows in single call

---

### 9. Enhanced API Mode
**Goal:** Better integration with automation tools

- [ ] Add OpenAPI/Swagger spec generation
- [ ] Auto-generate API client libraries
- [ ] Add webhook/notification support
- [ ] Add streaming responses for long operations
- [ ] Add GraphQL endpoint option (optional)

**Why:** Standard API specifications enable auto-integration

---

### 10. Schema Export & Validation
**Goal:** Export configuration schema for validation

- [ ] Export schema as JSON Schema
- [ ] Export as GraphQL schema
- [ ] Create validator tool: `secretzero schema validate`
- [ ] Create schema documentation generator
- [ ] Support schema migration helpers

**Why:** Agents can validate configs before deployment

---

## Implementation Guide

### Start Here (Day 1-2)
1. Task 1 - JSON output format
2. Task 2 - Standardized exit codes
3. Task 3 - Better dry-run/plan mode

### Continue (Week 2)
4. Task 4 - Query/inspect commands
5. Task 5 - Dependency graph export

### Extend (Week 3+)
6-10. Configuration assistance, batch ops, API enhancements

---

## Testing Strategy
- [x] Add JSON output schema validation tests (tests/test_cli_features.py)
- [x] Add exit code verification tests (tests/test_cli_features.py)
- [ ] Add integration tests for AI agent workflows
- [ ] Add performance tests for large configs
- [ ] Create AI agent test suite

---

## Documentation Updates
- [ ] Update CLI reference for new commands
- [ ] Create "Using with AI Agents" guide
- [ ] Document JSON output schemas
- [ ] Document exit codes reference
- [ ] Add agent integration examples
- [ ] Create batch operations guide

---

## Success Metrics
- AI agents can extract info without regex parsing
- 100% of commands support `--output json`
- Exit codes match documentation
- Agents can preview changes with `--plan`
- Agents can query specific data without full render
- Config generation takes <5 agent calls

