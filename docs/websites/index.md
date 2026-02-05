# Websites / Portals Hub

This section documents the web apps in this repo: what they are, where they live, how to run them locally, and how they connect to auth + the API gateway.

The documentation website (this MkDocs site) is published at the repo GitHub Pages URL and can be run locally with `mkdocs serve`.

## Inventory

| App                  | Path                        | Purpose                                              | Local dev                                   |
| -------------------- | --------------------------- | ---------------------------------------------------- | ------------------------------------------- |
| Internal Portal      | `apps/portal`               | Internal/admin portal + gateway integration          | See [Internal Portal](portal.md)            |
| Customer Portal      | `apps/portal-customer`      | Customer-facing portal (Supabase Auth + SSR cookies) | `http://localhost:3005`                     |
| Experimental Portals | `apps/portal-experimental*` | UI prototypes / iteration sandboxes                  | See [Experimental Portals](experimental.md) |

## Common local setup

### 1) Supabase env vars

Each portal expects Supabase public credentials in its own `.env.local`:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

If a portal uses email/OAuth flows, ensure Supabase Auth URL Configuration includes the correct callback URL for that portal (for example: `/auth/callback`).

### 2) Install + run

From the app folder:

```bash
npm install
npm run dev
```

## Design & Strategy

- **[Design Philosophy](design-philosophy.md)** — Core principles guiding portal development
- **[Feature Roadmap](roadmap.md)** — Planned features: realtime stats, A/B testing, CRM, Slack, booking, and more
- **[Implementation Details](implementations.md)** — Technical guidance for building each feature

## Related docs

- Portal + Gateway auth details: [guides/dev/portal-gateway-auth.md](../guides/dev/portal-gateway-auth.md)
- Customer portal deployment/local notes: [guides/dev/customer-portal.md](../guides/dev/customer-portal.md)
