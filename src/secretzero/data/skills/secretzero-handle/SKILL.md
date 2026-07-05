---
name: secretzero-handle
description: |
  Use when the task touches `.env`, dotenv/json/yaml secret files, local `file` targets,
  or any workflow where secret material could enter agent context. Enforces
  `SZ_AGENT_MODE=true` spill-safe CLI usage, ingest preseed, strict manifest validation,
  and safe discovery patterns alongside `secretzero-agent` / `secretzero-author`.
license: Apache-2.0
compatibility: Requires SecretZero CLI (Python 3.12+). Always set SZ_AGENT_MODE=true before CLI on agent hosts.
metadata:
  author: secretzero
  version: "1.1"
allowed-tools: Bash(secretzero:*) Read
---

# SecretZero Handle (spill-safe context)

Enforces **`skills/secretzero/SKILL.md` absolute rule**: SecretZero only for secrets; never load values into agent context.

Use this skill **together with** `skills/secretzero-agent/SKILL.md` and `skills/secretzero-author/SKILL.md` whenever:

- The manifest references **`.env`**, `*.env`, or **`local` / `file`** targets that read or write environment files.
- You are asked to **pre-seed** or **import** values from disk into the lockfile.
- The agent might otherwise run **`secretzero render`**, **`list variables`**, **`get --reveal`**, or **`terraform --include-static-secrets`**.

## Set spill-safe mode

```bash
export SZ_AGENT_MODE=true
```

With this set:

- **`secretzero validate`** also enforces **no plaintext static-like payloads** in the merged manifest (same rules as `--strict-manifest-plaintext`).
- **`secretzero render`** is **blocked** (full interpolated manifest may contain secrets).
- **`secretzero list variables --format json`** returns **names only** (`values_redacted`).
- **`secretzero list targets`** redacts non-structural target `config` fields in JSON and text summaries.
- **`secretzero get --reveal`** is **blocked**.
- **`secretzero backup create`** without **`--encrypted`** is **blocked**; **`backup restore --print`** is **blocked**.
- **`secretzero agent adopt`** / **`agent list`** are safe under spill mode (metadata-only JSON). Use **`--preseed-lockfile`** to hash present credentials without printing values. **`agent backup`** is an alias of **`agent adopt`** (not value-export backup).
- **`secretzero terraform`** with **`--include-static-secrets`** is **blocked**.

Unset `SZ_AGENT_MODE` only on trusted local shells when you intentionally need full dumps.

`SZ_AGENT` (Vector 3 automation) and `SZ_AGENT_MODE` can both be set; spill guards apply when **either** is true.

## MCP server spill mode

The first-party MCP server (`secretzero-mcp`, see `docs/mcp-setup.md`) sets **`SZ_AGENT_MODE=true`** on startup when the variable is unset — same spill contract as CLI above.

- MCP tools (`sz_status`, `sz_sync`, `sz_discover`, `sz_rotate`, `sz_drift_check`) return **metadata only** and reject `reveal` parameters.
- Set **`SZ_WORKSPACE`** (or pass tool `workspace`) to the repository root so lockfile/Secretfile resolution matches the project.
- MCP does **not** replace **`agent sync --web`** or **`ingest preseed`** — use CLI for human seeding and lockfile import from disk.
- Co-load this skill whenever MCP is used for authoring or operations alongside `secretzero-author` / `secretzero-agent`.

## Pre-seed lockfile from a secrets file (no values on stdout)

1. Ensure `Secretfile.yml` defines each secret with a **`local` / `file`** target whose `config.path` matches the on-disk file (e.g. `.env`).
2. Use placeholders / null leaves for static-like secrets—**no literals** in YAML when `SZ_AGENT_MODE` is on.
3. Run:

```bash
secretzero ingest preseed --source ./.env --file Secretfile.yml --format json
```

Stdout is **metadata only** (counts, per-secret status, matched secret names)—same contract as `secretzero import`.

For broader key discovery when authoring manifests:

```bash
secretzero detect . --all-keys --format json
```

That lists **variable names** from dotenv-style files (no values).

## Authoring rules under agent handle

- Never **`read_file`** on `.env`, `.env.*`, `*.pem`, or lane `.szvar` files that may contain secrets.
- Prefer **`secretzero ingest preseed`** + **`secretzero validate`** instead of copying values into chat or YAML.
- Use **`secretzero agent sync --web`** for human entry when ingest cannot cover a secret.

## Install / verify

Same as other SecretZero skills (`uv tool install "secretzero[all]"`, then `secretzero --help`, `secretzero ingest preseed --help`).
