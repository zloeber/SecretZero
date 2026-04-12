**Coding Agent Instructions: Implement Unified Agent Secret-Zero Workflow**

**Goals Summary**  
Implement a clean, unified `secretzero agent sync` workflow that handles **three secret-zero vectors** systematically while staying minimal, backward-compatible, and leveraging existing features (`agent_instructions` per secret, CLI structure, templating/variables, manual fallbacks, and FastAPI). **Feature parity is mandatory:** every planned agent-sync capability must exist in both the CLI and the REST API so remote clients, CI, and integrations can drive the same workflows without forking logic.

1. **Vector 1 (Agent instructs human)**: Agent runs locally (or calls the API), gets rendered instructions, and tells the human exactly what CLI commands or steps to perform (human seeds directly to targets).
2. **Vector 2 (Human provides secrets safely)**: Agent triggers a temporary local web UI where the human enters values; the UI feeds them directly into sync/lockfile update without the value ever entering the agent's context or logs. The API must expose a coherent contract for this vector (e.g. session/bootstrap URLs, status polling, or explicit error semantics) that matches the CLI `--web` behavior—implemented by delegating to the same core code paths as the CLI, not a duplicate implementation.
3. **Vector 3 (Fully automated)**: When providers are authenticated (or via `SZ_AGENT=true`), the workflow runs end-to-end without human intervention—via CLI **and** API request flags / environment semantics aligned with the server process.

The result should feel like **one simple command** (`secretzero agent sync --json [--web]`) **and** one primary API surface (e.g. `POST /agent/sync` with a request body mirroring CLI options) that agents can call reliably, with clear JSON output for parsing and human-readable fallbacks.

---

**API parity requirements (non-negotiable)**  
- Extend `src/secretzero/api/` (e.g. `app.py`, `schemas.py`, auth) so agent sync is available over HTTP with the same semantics as the CLI: structured JSON including `pending_secrets`, `failed_secrets`, and status fields; **no plaintext secret values** in responses, logs, or audit payloads.  
- Define Pydantic request/response models for the agent sync endpoint(s); run `task schema:update` and ensure OpenAPI (`/openapi.json`) documents the new operations.  
- Reuse the same synchronizer / agent logic the CLI uses (`AgentSecretSynchronizer` or equivalent)—**single implementation**, two transports.  
- Document in code and in the skill/docs how each vector maps to CLI flags vs API fields (e.g. `dry_run`, `web`, mode resolution from `Secretfile.agent` and `SZ_AGENT` on the server host).

---

**End-to-end API testing with Tavern**  
Implement **black-box HTTP tests** using [Tavern](https://tavern.readthedocs.io/en/latest/) (pytest plugin): YAML-defined scenarios that hit a running SecretZero API instance (or pytest fixtures that start the app on `127.0.0.1` with a known `Secretfile` / lockfile test harness).

- Add Tavern as a dev/test dependency (`tavern[pytest]` or equivalent) and register the pytest plugin so `pytest` collects Tavern files.  
- Create **one dedicated Tavern YAML file per vector workflow** (three files minimum), using the `test_*.tavern.yaml` naming convention so discovery matches Tavern’s pytest integration. Suggested layout (adjust names to project conventions):  
  - `tests/e2e/test_agent_vector1_instructs_human.tavern.yaml` — Vector 1: responses include templated `agent_instructions` / `pending_secrets` as expected; assert **absence** of secret material in JSON.  
  - `tests/e2e/test_agent_vector2_web_flow.tavern.yaml` — Vector 2: exercise the API contract for the secure web path (e.g. session or redirect URL present, successful completion shape); avoid asserting real secret values; mock or isolate external providers as needed.  
  - `tests/e2e/test_agent_vector3_automated.tavern.yaml` — Vector 3: `SZ_AGENT` / auto-mode behavior reflected in API responses when the test environment is configured for full automation.  
- Each file should be readable standalone: `test_name`, `stages` with `request`/`response` (status, JSON subsets), and use anchors or shared includes only if it improves clarity.  
- Wire these into `task test` or a dedicated `task test:e2e` if separation is preferred; document how to run them in the test README or `context/setup.md` only if the repo already documents tests there.

---

**Step 1: Extend the Secretfile schema and models for top-level agent configuration**  
Locate where Pydantic models for `Secretfile` are defined (likely in `src/secretzero/models.py` or the file that generates `Secretfile.schema.json`).  

Add a new `AgentConfig` model with fields for default mode and web UI settings (e.g., port range).  

Then add an optional top-level `agent` field to the main `Secretfile` model (default to "auto" mode).  

Ensure the schema update task reflects these changes so `agent_instructions` (which already exists per-secret with `summary`, `steps`, `prerequisites`, etc.) can be extended with templating support later.  

Validate by checking that `Secretfile.example.yml` and tests still load correctly.

---

**Step 2: Add templating / variable rendering to AgentInstructions**  
Find the `AgentInstructions` and `AgentInstructionStep` models.  

Add (or extend) a `render()` method (or helper function) that processes templated strings using the existing variable system from the Secretfile (support `{{secret_name}}`, `{{target.xxx}}`, etc., consistent with other parts of the codebase).  

Apply this rendering automatically when returning pending secrets in agent flows so instructions become context-aware (e.g., injecting target names or URLs).  

Keep it optional and backward-compatible for existing `agent_instructions`.

---

**Step 3: Implement environment variable detection and mode resolution**  
Locate CLI/config loading logic (likely `cli.py`, `config.py`, or wherever environment variables and `Secretfile` are parsed).  

Add support for `SZ_AGENT=true` (or similar) to force non-interactive "auto" mode.  

Create logic to resolve the final mode by combining:  
- Top-level `Secretfile.agent.mode` ("auto" | "human" | "web")  
- The `SZ_AGENT` env var (takes precedence)  
- The `--web` CLI flag  

This ensures Vector 3 works seamlessly when automation is possible. **Mirror the same resolution rules for the API** (query/body flags and server environment).

---

**Step 4: Add or enhance the `agent sync` CLI command**  
In the CLI entrypoint (likely `src/secretzero/cli.py`), add or extend a subcommand `secretzero agent sync`.  

Support these flags: `--file`, `--lockfile`, `--dry-run`, `--json` (for agent-friendly output), `--web`, and `--verbose`.  

Inside the command:  
- Load Secretfile and lockfile using existing helpers.  
- Resolve the operating mode from Step 3.  
- Delegate to the synchronizer logic (extend or create `AgentSecretSynchronizer` if it doesn't exist yet, building on current sync/manual fallback code).  
- For non-web modes, render instructions via the new templating and output JSON or human-readable results.  

Make `--json` the default-friendly output for agents (include `pending_secrets`, `failed_secrets`, `status`, etc.).

---

**Step 5: Implement the temporary local web UI for Vector 2**  
Create or extend code for a secure, one-time local web form (use existing FastAPI dependency).  

When `--web` is used:  
- Start a temporary FastAPI server bound to `127.0.0.1` on a random high port from the configured range.  
- Auto-open the browser if in the default local interactive mode (or print the URL clearly).
- Display a simple form with fields for each pending secret that requires manual input.  
- On submission, inject the provided values directly into the existing sync/manual fallback path (without exposing them to stdout, logs, or any agent context).  
- Run the sync + lockfile update, return success status, and auto-shutdown the server.  

Add graceful degradation if the web server can't start (fall back to CLI prompts).  

Ensure values never persist beyond the sync operation. **Expose API behavior consistent with this flow** (e.g. returning a localhost URL and correlation id for clients that cannot open a browser themselves).

---

**Step 6: Integrate and refine core sync/agent logic**  
Update or create the synchronizer class (in `agent.py`, `sync.py`, or equivalent) to:  
- Respect the resolved mode.  
- Use templated `agent_instructions` for pending items.  
- Force non-interactive behavior under `SZ_AGENT=true` or "auto" mode (skip prompts, report failures clearly in JSON).  
- Integrate with existing manual fallback and provider logic so all three vectors flow through the same code paths.  

Ensure zero-knowledge guarantees remain intact (values never leak into lockfile plaintext or responses).

---

**Step 7: REST API — agent sync endpoints and shared models**  
Implement `POST /agent/sync` (or the path chosen to match existing API style) in `src/secretzero/api/app.py`, with request/response types in `src/secretzero/api/schemas.py`. Delegate to the same agent synchronizer as the CLI. Cover all three vectors with documented request options; ensure auth (`RequireAuth`) and audit logging follow existing API patterns without recording secret values.

---

**Step 8: Tavern end-to-end tests (one YAML per vector)**  
Add the three Tavern YAML files under `tests/e2e/` (or the project’s agreed location), fixtures for the test app and Secretfile, and pytest configuration so CI runs them. Verify they pass against the implemented endpoints.

---

**Step 9: Update documentation, skill, examples, and unit tests**
- Enhance `AGENTS.md` and the file in `skills/secretzero/` with a clear "Unified Agent Workflow" section describing the single CLI command **and** the primary API endpoint, and how each maps to the three vectors.  
- Update `Secretfile.example.yml` (and any test files) to demonstrate the new top-level `agent:` config and templated `agent_instructions` on at least one secret.  
- Add or expand the schema documentation (in `docs/` or wherever schema details live) to cover the new fields.  
- Add unit tests for mode switching, templating, `--web` behavior (mock the server if needed), and API handler behavior (FastAPI `TestClient` where appropriate).

Run full validation tasks to ensure examples and schema pass.

---

**Step 10: Final cleanup, validation, and commit**  
Re-run the full lint/format/schema/test suite one last time, including Tavern E2E tests.  

Commit changes incrementally with clear messages (e.g., "feat: add top-level agent config", "feat: templated agent_instructions", "feat(api): agent sync endpoint", "test(e2e): tavern vector workflows", etc.).  

Provide a high-level summary of what was changed and how an agent should now invoke the workflow from **CLI and API**, and how to run the Tavern suites.

---

You are an expert on this codebase — explore files as needed (e.g., start by examining models for Secretfile/AgentInstructions, CLI structure, `src/secretzero/api/`, and any existing agent/sync code). Make changes precise, reusable, and minimal. Prioritize clarity so the three vectors feel like natural variations of one command **and** one API contract.

If you encounter ambiguities (e.g., exact file locations or existing helper functions), resolve them by reading the code first, then proceed.  

Once complete, confirm the workflow works for all three vectors with example invocations **for both CLI and HTTP**, and that the three Tavern YAML workflows pass.
