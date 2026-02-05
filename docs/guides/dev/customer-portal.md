# Customer Portal (apps/portal-customer)

This guide explains how to **access the customer portal through your website** and how to run it locally.

The customer portal is a separate Next.js app:

- App: `apps/portal-customer`
- Local dev URL: `http://localhost:3005`

## What “access through the website” means

You need:

1. A public URL for the portal (deployment)
2. A link on your marketing site that points to that URL

Recommended: deploy the portal on a **subdomain** (e.g. `portal.yourdomain.com`).

## Recommended setup: subdomain (`portal.yourdomain.com`)

### 1) Deploy the portal

Deploy the Next.js app from `apps/portal-customer`.

Typical approach:

- Vercel project root: `apps/portal-customer`
- Build: `npm run build`
- Start: `npm run start`

### 2) Add DNS

Create a DNS record for your subdomain (varies by host).

Example:

- `portal.yourdomain.com` → CNAME to your deployment provider

### 3) Configure Supabase Auth URLs

In Supabase Dashboard → Authentication → URL Configuration:

- **Site URL**: `https://portal.yourdomain.com`
- **Redirect URLs**:
  - `https://portal.yourdomain.com/auth/callback`
  - (Optional) `https://portal.yourdomain.com/**`

If you use Google OAuth, ensure the Google OAuth redirect URI matches the callback route above.

### 4) Add a link from the marketing site

Add a “Login” / “Customer Portal” link in your marketing site header:

- `https://portal.yourdomain.com/login`

That’s the whole “access through the website” flow.

## Alternative: same domain path (`yourdomain.com/portal`)

This is possible but requires extra infrastructure:

- A reverse proxy or platform routing that forwards `/portal/*` to the portal app
- Supabase redirect URLs like `https://yourdomain.com/portal/auth/callback`
- Careful cookie/session behavior (since the portal isn’t at the root)

If you want this, decide where your “website” is deployed (Vercel, Cloudflare, NGINX, etc.), and we’ll set up path routing accordingly.

## Local development

### Environment variables

Create `apps/portal-customer/.env.local` based on `.env.example`:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

### Install and run

```bash
cd apps/portal-customer
npm install
npm run dev
```

Open:

- Login: `http://localhost:3005/login`
- Dashboard: `http://localhost:3005/dashboard` (requires auth)

## Notes

- The portal uses Supabase Auth with SSR cookies (`@supabase/ssr`) and a Next.js middleware gate.
- If sign-in works but redirects fail, double-check Supabase “Redirect URLs” match your deployed (or local) URL exactly.
