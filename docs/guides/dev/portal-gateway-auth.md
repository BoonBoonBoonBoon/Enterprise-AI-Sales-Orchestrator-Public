# Portal + Gateway Auth Setup (What We Accomplished Today)

This page captures the practical setup we finalized today for running the **Portal (Next.js)** with **Supabase Auth** and the **Gateway (FastAPI)** locally.

## What’s working now

- Portal uses Supabase Auth via the `/login` page (the homepage is marketing).
- Portal proxies API calls under `/api/v1/*` to the Gateway.
- Portal attaches `Authorization: Bearer <token>` to API requests.
  - Preferentially uses a **dev bypass token** (dev-only), otherwise uses the **Supabase session access token**.
- Gateway exposes a **dev-only** endpoint to mint a JWT for quick local admin access.

## New security features (Jan 2026)

- **Rate limiting** is enforced at the Gateway (stricter limits on `/auth/login` and `/auth/signup`).
- **Tenant isolation** is enforced by Postgres RLS for all tenant-owned tables.
- **Admin endpoints** exist for tenant membership management.
- **Invitation acceptance** exists to join an org after signup/login.

## Environment variables

### Portal (Next.js)

Create/update `apps/portal/.env.local` (this file should not be committed):

```bash
NEXT_PUBLIC_SUPABASE_URL=...            # Supabase project URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=...       # Supabase anon/public key
API_GATEWAY_URL=http://localhost:8001   # Gateway base URL for Next.js rewrite proxy
```

Notes:

- `NEXT_PUBLIC_*` variables are used by the browser bundle.
- `API_GATEWAY_URL` is used by the Next.js rewrite that forwards `/api/v1/*` calls to the Gateway.

### Gateway (FastAPI)

Gateway reads its environment from the repo root `.env` (do not commit secrets). Minimum required:

```bash
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_JWT_SECRET=...
```

## Ports / URLs (local dev)

- Portal: `http://localhost:3002`
- Gateway: `http://localhost:8001`

We moved the Gateway to `8001` during debugging because `8000` had multiple conflicting listeners.

## How to confirm Supabase is “working”

1. Go to `http://localhost:3002/login` and sign in via Supabase.
2. Visit any dashboard route that triggers API calls.
3. Confirm requests to `/api/v1/*` include an `Authorization: Bearer ...` header.

## Dev-only admin bypass

For faster local iteration, the Portal includes a **Dev Admin Login** button on `/login` (only shown in non-production).

- It calls `POST /api/v1/auth/dev-login`.
- It stores the returned token in browser storage and uses it for subsequent API calls.

Recommended dev payload uses a normal email (example):

- `dev-admin@example.com`

### Dev-login gating

`/api/v1/auth/dev-login` is intentionally blocked in production. If you see a 404 locally, ensure at least one of these is true:

- `DEBUG=1`
- `DEV_LOGIN_ENABLED=1`
- `ENV` is `dev`, `development`, or `local`

## Admin endpoints (tenant management)

These live under `/api/v1/admin/*` and require `role=admin`.

- `POST /api/v1/admin/invite` — create an invite for a user (email + role)
- `GET /api/v1/admin/members` — list tenant members
- `PATCH /api/v1/admin/members/{user_id}/role` — change role
- `DELETE /api/v1/admin/members/{user_id}` — remove member
- `GET /api/v1/admin/audit-log` — view audit events

Note: Admin endpoints require Supabase service role access for user management tasks.
Set one of:

- `SUPABASE_SERVICE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

## Invitation acceptance

Invitees join a tenant by calling:

- `POST /api/v1/auth/accept-invite` with `{ "invite_token": "..." }`

This creates/updates membership in `user_client_memberships` and marks the invite as accepted.

## Safety / cleanup notes

- Never enable or expose dev-login in production.
- Avoid running multiple gateway instances on the same port; if something returns 404 but OpenAPI shows the route, you’re probably talking to a different running process.
