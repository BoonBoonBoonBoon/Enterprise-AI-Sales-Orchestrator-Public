# Customer Portal (apps/portal-customer)

## Purpose

Customer-facing portal with Supabase Auth.

- Path: `apps/portal-customer`
- Local dev URL: `http://localhost:3005`

## Local development

### Install + run

```bash
cd apps/portal-customer
npm install
npm run dev
```

### Environment variables

Create `apps/portal-customer/.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

## Auth notes (important)

- Uses SSR cookie-based auth (`@supabase/ssr`) + Next.js middleware gating.
- Callback route: `/auth/callback` is used for OAuth and PKCE session exchange.
- Password recovery UX exists via `/forgot-password` → `/reset-password`.

Deployment + URL configuration details live here:

- [guides/dev/customer-portal.md](../guides/dev/customer-portal.md)
