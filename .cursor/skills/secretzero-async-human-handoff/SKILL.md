---
name: secretzero-async-human-handoff
description: >-
  Guides async human-in-the-loop credential flows using SecretZero: emit sealed-box
  request bundles from agent sync, share safe artifacts with a credential holder,
  encrypt HandoffPayload JSON, and complete handoffs with human complete. Use when
  the user works with SecretZero, manual secrets, agent_instructions, async approval,
  sealed-box handoff, .secretzero/requests, or human encrypt/complete.
---

# SecretZero: asynchronous human-in-the-loop handoff

SecretZero can stage credentials that need a **human** (or separate machine) when `secretzero sync` / automation cannot finish inline. The workflow uses **NaCl sealed boxes**: the developer machine keeps the **private key**; the other party encrypts a small JSON payload to the **public key** embedded in `request.json`.

## When this applies

- A `Secretfile` secret has **`agent_instructions`** but **no** inline static value (or it cannot be auto-generated).
- You run **`secretzero agent sync --emit-human-requests`** (opt-in; default is off).
- You need to **collect values later** (chat, ticket, another team) and **apply** them without pasting plaintext into CI logs.

## Artifacts (developer machine)

After emit, each pending secret gets a directory:

```text
<secretfile-directory>/.secretzero/requests/<uuid>/
  request.json    # envelope: instructions snapshot, public key, secretfile SHA-256
  private.key     # NEVER share; chmod 600 on Unix
```

**Share only** what is needed for encryption: contents of `request.json` (or a YAML export of the user-safe fields). Never share `private.key`.

## End-to-end flow

1. **Emit bundles** (from repo root; paths relative to your Secretfile location):

   ```bash
   secretzero agent sync --emit-human-requests -f Secretfile.yml
   ```

   Use `--dry-run` to see what would be created without writing. Use `--human-requests-root` to override the base directory (default: `<secretfile-dir>/.secretzero/requests`).

2. **Credential holder** builds plaintext JSON (**HandoffPayload v1**):

   ```json
   {"v":1,"values":{"<secret_name>":"<plaintext_value>"}}
   ```

   Secret names must match the bundle; v1 supports **static** secrets only (see errors below if kinds differ).

3. **Encrypt** (holder can use SecretZero CLI if installed):

   ```bash
   echo '{"v":1,"values":{"tok":"..."}}' | secretzero human encrypt /path/to/.secretzero/requests/<uuid> --payload-file -
   ```

   - Default: **raw** sealed-box bytes on stdout (suitable for a file).
   - **`--base64-out`**: base64 line for paste-friendly channels.

4. **Complete** (developer machine, same project / Secretfile as when the bundle was created):

   ```bash
   secretzero human complete /path/to/.secretzero/requests/<uuid> --payload cipher.bin
   ```

   - **`--payload -`**: read ciphertext from stdin.
   - **`--base64`**: decode base64 ciphertext before decrypt.
   - **`--dry-run`**: validate decrypt + sync plan without writing targets/lockfile.
   - **`--lockfile`**: if not using default `.gitsecrets.lock` under the project root from the bundle.

## Stale bundles

`request.json` stores a **SHA-256** of the Secretfile at creation time. If the Secretfile changes, **`human complete`** fails with a stale-request error. **Regenerate** the bundle with `agent sync --emit-human-requests` after edits.

## File targets and paths

Local **file** targets resolve relative to the **process current working directory**. Prefer **absolute paths** in the Secretfile for target `path` so sync writes predictable locations regardless of cwd.

## Security expectations

- **`private.key`** decrypts anything sealed to this request’s public key—treat like a secret.
- **`request.json`** still names secrets and includes instructions; handle per policy.
- Do not commit `private.key` or raw ciphertext to public repos unless policy allows.

## Troubleshooting

| Symptom | Likely cause |
|--------|----------------|
| Stale human handoff | Secretfile changed; re-emit bundle |
| Decrypt / crypto error | Wrong ciphertext, truncated base64, or wrong request directory |
| Validation error on payload | Missing secret name, extra name not in bundle, or non-static kind in v1 |
| Nothing written to expected file | Relative target path + unexpected cwd; use absolute `path` |

## Related commands (reference)

| Command | Role |
|---------|------|
| `secretzero agent sync` | Classifies auto vs pending; optional `--emit-human-requests` |
| `secretzero human encrypt` | Holder seals HandoffPayload JSON with bundle’s public key |
| `secretzero human complete` | Developer decrypts and runs sync with `value_overrides` |

## Agent behavior

When the user asks for async HIL with SecretZero:

1. Confirm `agent_instructions` exist for manual secrets and that targets/paths are intentional.
2. Prefer **emit → encrypt off-box → complete** over checking plaintext secrets into git.
3. If implementation details are unclear, inspect `src/secretzero/human_handoff/` and CLI under `human` in `src/secretzero/cli.py`.

Repository hygiene for MRs may be documented in `AGENTS.md` (pre-push checks).
