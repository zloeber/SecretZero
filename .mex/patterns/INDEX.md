# Pattern Index

Lookup table for all pattern files in this directory. Check here before starting any task — if a pattern exists, follow it.

| Pattern | Use when |
|---------|----------|
| [agent-sync.md](agent-sync.md) | Changing unified `agent sync` / `POST /agent/sync` (three vectors, CLI+API parity) |
| [add-bundle.md](add-bundle.md) | Adding a provider/generator/target through bundle manifest registration |
| [add-cli-command.md](add-cli-command.md) | Adding or changing `secretzero` CLI commands/options |
| [add-secret.md#task-add-a-simple-secret](add-secret.md#task-add-a-simple-secret) | Adding a standard secret definition to `Secretfile.yml` |
| [add-secret.md#task-add-a-template-secret](add-secret.md#task-add-a-template-secret) | Adding a template-backed multi-field secret |
| [aws-json-target-format.md](aws-json-target-format.md) | Changing AWS `ssm_parameter` / `secrets_manager` structured JSON target behavior or docs |
| [backup-cli-workflow.md](backup-cli-workflow.md) | Changing `secretzero backup create` / `backup restore` defaults, encryption mode, or environment fan-out |
| [gitnexus-metagit-integration.md](gitnexus-metagit-integration.md) | GitNexus `secrets_overlay`, MetaGit registry, discovery bindings, blast-radius CLI |
| [debug-sync.md](debug-sync.md) | Diagnosing sync failures across config/provider/generator/target boundaries |
| [lockfile-state-parity.md](lockfile-state-parity.md) | Changing synced/pending/drift target-state logic across web/graph/CLI surfaces |
| [lockfile-sync-identity.md](lockfile-sync-identity.md) | Extending lockfile operator/CI identity metadata or sync provenance |
| [schema-doc-parity.md](schema-doc-parity.md) | Any schema/model/config-surface change requiring schema+docs+examples parity |
| [security-scan-remediation.md](security-scan-remediation.md) | Reproducing and fixing `task security:scan` / `pip-audit` / `bandit` failures and keeping pre-commit in sync |
| [secretzero-web.md](secretzero-web.md) | Changing `secretzero web` (network seeding UI, TLS, templates, auth) |
| [secretfile-authoring.md](secretfile-authoring.md) | Editing Secretfile structure, variables, provider mappings, and interpolation usage |
