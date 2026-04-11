---
name: decisions
description: Key architectural and technical decisions with reasoning. Load when making design choices or understanding why something is built a certain way.
triggers:
  - "why do we"
  - "why is it"
  - "decision"
  - "alternative"
  - "we chose"
edges:
  - target: context/architecture.md
    condition: when a decision relates to system structure
  - target: context/stack.md
    condition: when a decision relates to technology choice
  - target: patterns/add-bundle.md
    condition: when implementing extensibility changes that depend on these decisions
last_updated: 2026-04-10
---

# Decisions

## Decision Log
### Bundle-driven extensibility via manifests and registry
**Date:** 2024-01-01 (inferred)  
**Status:** Active  
**Decision:** Providers, generators, and targets are registered via bundle manifests and `BundleRegistry`, including entry-point discovery.  
**Reasoning:** Keeps core sync logic decoupled from provider-specific integrations and supports third-party extension packages.  
**Alternatives considered:** Hard-coded provider/generator/target branching in `SyncEngine` (rejected for poor extensibility and maintenance overhead).  
**Consequences:** New integrations must add `_get_bundle_manifest()` and registry wiring; direct branching is a design violation.

### Lockfile stores only hashes and metadata
**Date:** 2024-01-01 (inferred)  
**Status:** Active  
**Decision:** `.gitsecrets.lock` stores SHA-256 hashes and provenance metadata, never raw secret values.  
**Reasoning:** Lockfile is versioned and used for audit/drift state; persisting values would create a critical security risk.  
**Alternatives considered:** Encrypted lockfile payloads (rejected due to key-management burden and unnecessary risk surface).  
**Consequences:** Partial sync for existing secrets may require retrieving values from existing targets when adding new targets.

### Open kind handling for extensibility
**Date:** 2024-01-01 (inferred)  
**Status:** Active  
**Decision:** Kind resolution is registry-based and tolerant of extension-defined kinds instead of enforcing a closed built-in set only.  
**Reasoning:** External bundles need to register new generator/target kinds without core code changes.  
**Alternatives considered:** Strictly closed enum-only kind model (rejected; blocks extension bundles).  
**Consequences:** Validation of kind support happens at registry lookup/runtime boundaries, with explicit user-facing errors for unknown registrations.

### Variable interpolation supports shell-style and Jinja style
**Date:** 2024-01-01 (inferred)  
**Status:** Active  
**Decision:** Config interpolation supports `${VAR}` and `{{var.key}}` in `ConfigLoader`, with shell-style applied first.  
**Reasoning:** Supports practical Secretfile authoring patterns across infra users while retaining structured templating behavior.  
**Alternatives considered:** Single syntax only (rejected as less ergonomic for mixed teams and templates).  
**Consequences:** Interpolation errors/typos must be diagnosed with `secretzero render`; empty substitutions are a common pitfall.
