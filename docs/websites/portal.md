# Internal Portal (apps/portal)

## Purpose

The internal portal is a Next.js app used for internal/admin workflows and (in local dev) commonly proxies API calls to the Gateway.

- Path: `apps/portal`

## Local development

### Install + run

```bash
cd apps/portal
npm install
npm run dev
```

Notes:

- The repo’s local-dev setup often runs the portal on `http://localhost:3002` to avoid conflicts, but the script is `next dev` (default is `3000` unless configured).

### Environment variables

Create `apps/portal/.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
API_GATEWAY_URL=http://localhost:8001
```

## Auth + Gateway integration

This setup is captured in the existing guide:

- [guides/dev/portal-gateway-auth.md](../guides/dev/portal-gateway-auth.md)
