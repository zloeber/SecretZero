# Ent Site + Vercel Provider Design

## Scope

Implement a Vercel-deployable enterprise microsite (`ent-site`) with a distinctive dark-mode experience, embedded workflow diagrams, Three.js visuals, and a signup-only waitlist flow.  
Add a new SecretZero `vercel` provider for Vercel project environment variable management (v1).

## Goals

- Deploy-ready `ent-site` on Vercel using Next.js App Router.
- Dark-first visual language with reduced-motion support.
- Rich workflow visualization (agent flow, governance loop, sync/rotate/drift patterns).
- Waitlist API (`/api/signup`) storing entries in Vercel KV.
- Provider support in SecretZero for Vercel env vars:
  - Upsert secret values
  - Retrieve state/value
  - Delete values
  - Environment-scoped support (`development`, `preview`, `production`)

## Non-Goals

- Domain/deployment management in provider v1.
- CRM integration in first waitlist release.
- Multi-step onboarding funnels.

## Architecture

### Microsite

- Stack: Next.js + TypeScript.
- App structure:
  - `app/page.tsx`: landing composition
  - `components/hero-scene.tsx`: Three.js visual surface
  - `components/workflow-diagrams.tsx`: SVG/CSS diagrams
  - `components/example-workflows.tsx`: practical scenarios
  - `components/waitlist-form.tsx`: signup UI + API integration
  - `app/api/signup/route.ts`: waitlist endpoint
  - `lib/waitlist-store.ts`: adapter interface + KV implementation
- Theme:
  - Dark mode by default with high-contrast tokenized palette.
  - Accessible focus rings and keyboard behavior.
  - Motion is opt-out with `prefers-reduced-motion`.

### Waitlist Data Flow

1. User submits email and optional context.
2. API validates and normalizes payload.
3. Deduplicate via normalized email hash key.
4. Persist with `@vercel/kv` using namespace `waitlist:*`.
5. Respond with deterministic status:
   - `created`
   - `already_registered`

### SecretZero Provider

- New module: `src/secretzero/providers/vercel.py`
- Auth:
  - `VERCEL_TOKEN` (required)
  - `team_id` optional
- Core capability methods:
  - `store_secret(...)`
  - `retrieve_secret(...)`
  - `delete_secret(...)`
- Uses Vercel REST API for project env vars:
  - Create/update env variable
  - List/read existing variable(s)
  - Delete variable(s)
- Supports env target list in config:
  - `development`, `preview`, `production`

## Validation and Testing

### Microsite

- Unit tests for payload validation and KV adapter behavior.
- API tests for:
  - successful insert
  - duplicate registration
  - invalid payload
- Smoke checks for dark-mode and reduced-motion rendering paths.

### Provider

- Unit tests with mocked Vercel API responses:
  - auth failure
  - project not found
  - upsert success
  - retrieval/list mapping
  - delete behavior
- Bundle registration checks and docs/example validation.

## Delivery Sequence

1. Scaffold Next.js microsite and Vercel-ready configuration.
2. Build dark-mode visual system and Three.js hero.
3. Add workflow diagrams and concrete example workflows.
4. Add waitlist API + KV adapter.
5. Implement SecretZero `vercel` provider + bundle registration.
6. Add docs/examples/tests and run verification.

## Risks and Mitigations

- **Three.js performance on low-power devices**: throttle complexity and support reduced motion.
- **KV lock-in concerns**: adapter abstraction allows future Postgres migration.
- **Provider API shape changes**: isolate HTTP handling and map clear errors.
