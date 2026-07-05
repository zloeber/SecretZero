# Provider plugin architecture

## When to use

Adding or packaging SecretZero providers, generators, or targets as pip-installable plugins; scaffolding new provider packages; or verifying sync/drift without live cloud credentials.

## Entry points

Built-in and third-party bundles register via PEP 621 entry points:

```toml
[project.entry-points."secretzero.providers"]
myprovider = "my_pkg:_get_bundle_manifest"
```

The loaded object may be a `BundleManifest` **or** a zero-arg callable returning one (built-in pattern in `secretzero.providers.*:_get_bundle_manifest`).

`BundleRegistry.discover_and_register()` runs entry-point discovery before built-in bundle registration and skips duplicates.

## Optional dependencies

Heavy SDKs live in `[project.optional-dependencies]` (`aws`, `azure`, `vault`, …). Install targeted extras:

```bash
pip install "secretzero[aws]"
pip install "secretzero[all]"
```

## Scaffold CLI

```bash
secretzero init provider mycloud -o ./plugins
# alias: secretzero scaffold-bundle mycloud
```

Implementation: `src/secretzero/commands/init_provider.py` (`scaffold_provider_bundle`).

Generated packages include:

- `pyproject.toml` with `secretzero.providers` entry point
- Pydantic-friendly provider model stubs (`provider.py`, optional `targets.py` / `generators.py`)
- Starter tests (`test_provider.py`, `test_bundle.py`)

## Mock provider test harness

For CI without cloud credentials:

- `tests/support/mock_provider_bundle.py` — in-memory provider + target
- `tests/test_sync_engine_provider_mocks.py` — sync, force rotation, file-target drift, callable entry-point factory

## Parity

New provider capabilities must remain consistent across CLI, API, and MCP (`sz_sync`, `sz_drift_check`, etc.). Respect `SZ_AGENT_MODE` on all new commands.
