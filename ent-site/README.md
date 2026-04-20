# SecretZero Enterprise Site (`ent.secret0.com`)

Standalone Next.js microsite for the Enterprise offering, deploy-ready for Vercel.

## Local development

```bash
npm install
npm run dev
```

Open <http://localhost:3000>.

## Build and deploy

```bash
npm run build
```

Deploy this folder on Vercel (`framework: nextjs` in `vercel.json`).

## Waitlist backend

`POST /api/signup` stores deduplicated submissions in Vercel KV via `@vercel/kv`.

Required environment variables on Vercel:

- `KV_REST_API_URL`
- `KV_REST_API_TOKEN`
- `KV_REST_API_READ_ONLY_TOKEN` (optional for read-only contexts)
