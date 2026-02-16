# SecretZero Project Roadmap

This roadmap outlines the planned development phases for SecretZero, a secrets orchestration, lifecycle, and bootstrap engine.

## Overview

SecretZero development is organized into distinct phases, each building upon the previous one. This phased approach ensures that core functionality is solid before adding more advanced features.

## Phase 1: Foundation (CURRENT PHASE - ✅ COMPLETE)

**Goal**: Establish the core data structures, configuration format, and basic CLI tooling.

**Status**: Complete

### Deliverables

- ✅ Pydantic data models for Secretfile.yml schema
- ✅ Configuration loader with variable interpolation support
- ✅ Schema validation and error handling
- ✅ Basic CLI commands:
  - `secretzero init` - Create new Secretfile from template
  - `secretzero validate` - Validate Secretfile.yml structure
  - `secretzero secret-types` - List supported secret types
  - `secretzero test` - Test provider connectivity (stub)
- ✅ Comprehensive test suite (30 tests, 96% coverage)
- ✅ Project structure and build configuration
- ✅ Documentation framework

### Key Components

- **Models** (`src/secretzero/models.py`): Strongly-typed Pydantic models for:
  - Secretfile root configuration
  - Variables and metadata
  - Provider configurations with auth profiles
  - Secret definitions with templates
  - Template fields with generators
  - Target configurations
  
- **Config Loader** (`src/secretzero/config.py`): 
  - YAML parsing and validation
  - Jinja2-based variable interpolation
  - Support for `{{var.name}}` and `{{var.name or 'default'}}` syntax
  
- **CLI** (`src/secretzero/cli.py`):
  - Rich console output with colors and tables
  - Interactive help and documentation
  - Template-based initialization

### Testing

All core functionality is covered by unit tests:
- Model validation tests
- Configuration loading and interpolation tests
- CLI command tests

## Phase 2: Secret Generation & Local Storage (NEXT)

**Goal**: Implement actual secret generation and local file storage capabilities.

**Timeline**: 2-3 weeks

### Planned Deliverables

- [ ] Secret generator implementations:
  - [ ] Random password generator
  - [ ] Random string generator
  - [ ] Static value generator with validation
  - [ ] Script-based generator
- [ ] Local file target implementation:
  - [ ] Dotenv format support
  - [ ] JSON format support
  - [ ] YAML format support
  - [ ] Merge/append logic
- [ ] Lockfile management:
  - [ ] Create `.gitsecrets.lock` with metadata hashes
  - [ ] Check for existing secrets before generation
  - [ ] Track creation and update timestamps
- [ ] CLI commands:
  - [ ] `secretzero sync --dry-run` - Show what would be generated
  - [ ] `secretzero sync` - Generate and store secrets
  - [ ] `secretzero show <secret>` - Display secret metadata
- [ ] Environment variable fallback for generators

### Architecture

```
secretzero/
├── generators/
│   ├── base.py
│   ├── random_password.py
│   ├── random_string.py
│   ├── static.py
│   └── script.py
├── targets/
│   ├── base.py
│   └── file.py
└── lockfile.py
```

## Phase 3: Cloud Provider Integration

**Goal**: Add support for major cloud secret management services.

**Timeline**: 3-4 weeks

### Planned Deliverables

- [ ] AWS provider implementation:
  - [ ] Ambient authentication (IAM roles, profiles)
  - [ ] SSM Parameter Store target
  - [ ] Secrets Manager target
  - [ ] Assume role support
- [ ] Azure provider implementation:
  - [ ] Azure AD authentication
  - [ ] Key Vault target
  - [ ] Managed Identity support
- [ ] HashiCorp Vault provider:
  - [ ] Token authentication
  - [ ] KV v2 engine support
  - [ ] Dynamic secrets (future)
- [ ] Provider testing and connectivity checks
- [ ] Graceful fallback to manual input on auth failure

## Phase 4: CI/CD Integration

**Goal**: Support for CI/CD secret storage and automated workflows.

**Timeline**: 2-3 weeks

### Planned Deliverables

- [ ] GitHub Actions secrets target
- [ ] GitLab CI/CD variables target
- [ ] Jenkins credentials target
- [ ] CI/CD authentication patterns:
  - [ ] OIDC authentication
  - [ ] Personal access tokens
  - [ ] Service principals
- [ ] Automated secret rotation in CI/CD pipelines

## Phase 5: Kubernetes & Container Support

**Goal**: Kubernetes-native secret management.

**Timeline**: 2-3 weeks

### Planned Deliverables

- [ ] Kubernetes Secret target
- [ ] External Secrets Operator manifest generation
- [ ] Multiple namespace support
- [ ] RBAC configuration helpers
- [ ] Helm chart for deployment

## Phase 6: Advanced Features

**Goal**: Secret rotation, policies, and compliance features.

**Timeline**: 4-5 weeks

### Planned Deliverables

- [ ] Secret rotation:
  - [ ] Rotation policy enforcement
  - [ ] Automated rotation workflows
  - [ ] Rotation history tracking
- [ ] Policy system:
  - [ ] Rotation policies
  - [ ] Compliance policies (SOC2, ISO27001)
  - [ ] Access control policies
- [ ] Drift detection:
  - [ ] Compare lockfile to actual secrets
  - [ ] Alert on out-of-band changes
- [ ] Multi-environment support:
  - [ ] Environment profiles
  - [ ] Variable file overlays
  - [ ] Environment validation

## Phase 7: API Service

**Goal**: Convert CLI into a service with REST API.

**Timeline**: 3-4 weeks

### Planned Deliverables

- [ ] REST API server:
  - [ ] FastAPI-based implementation
  - [ ] OpenAPI documentation
  - [ ] Authentication and authorization
- [ ] API endpoints:
  - [ ] CRUD for Secretfile configurations
  - [ ] Secret generation and retrieval
  - [ ] Rotation workflows
  - [ ] Audit logs
- [ ] Web UI (optional):
  - [ ] Configuration management
  - [ ] Secret visibility (metadata only)
  - [ ] Audit trail visualization

## Phase 8: Documentation & Website

**Goal**: Comprehensive documentation and public website.

**Timeline**: 2-3 weeks

### Planned Deliverables

- [ ] Static website (secret0.com):
  - [ ] MkDocs or Docusaurus setup
  - [ ] Getting started guide
  - [ ] Comprehensive API documentation
  - [ ] Use case examples
  - [ ] Best practices guide
- [ ] Video tutorials
- [ ] Interactive examples
- [ ] Blog posts and articles

## Continuous Tasks

Throughout all phases:

- **Testing**: Maintain >90% code coverage
- **Documentation**: Keep docs up-to-date with features
- **Security**: Regular security audits and dependency updates
- **Performance**: Profile and optimize critical paths
- **Community**: Respond to issues and incorporate feedback

## Success Metrics

- Unit test coverage: >90%
- Integration test coverage: >80%
- Documentation completeness: 100% of public APIs
- Security vulnerabilities: 0 critical, 0 high
- User feedback: >4.5 stars on GitHub

## Contributing

We welcome contributions at any phase! See individual phase files in the `project/` directory for detailed task breakdowns and contribution guidelines.

## Questions or Feedback?

Open an issue on GitHub or join our community discussions.
