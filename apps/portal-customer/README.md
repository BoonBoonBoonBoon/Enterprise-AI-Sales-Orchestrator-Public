# Milo Customer Portal

Customer-facing portal for Milo users to manage their AI-powered email outreach.

## Features

- **Dashboard** - Overview of pending drafts, activity, and key metrics
- **Inbox** - Review, edit, approve, or reject AI-generated email drafts
- **Leads** - Pipeline view with table/kanban modes and lead scoring
- **Analytics** - Performance tracking for campaigns and outreach
- **Settings** - Account, AI voice/tone, notifications, integrations, security

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Auth**: Supabase Auth with SSR (@supabase/ssr)
- **Styling**: TailwindCSS with CSS variables
- **Icons**: Lucide React
- **UI**: Radix UI primitives

## Getting Started

### Prerequisites

- Node.js 18+
- A Supabase project with Auth enabled

### Environment Setup

Copy `.env.example` to `.env.local` and fill in your Supabase credentials:

```bash
cp .env.example .env.local
```

Required variables:

- `NEXT_PUBLIC_SUPABASE_URL` - Your Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Your Supabase anon/public key

### Install Dependencies

```bash
npm install
```

### Run Development Server

```bash
npm run dev
```

The portal runs on [http://localhost:3005](http://localhost:3005).

## Project Structure

```
src/
├── app/
│   ├── auth/callback/     # OAuth callback handler
│   ├── dashboard/         # Protected dashboard routes
│   │   ├── inbox/         # Draft review
│   │   ├── leads/         # Lead pipeline
│   │   ├── analytics/     # Performance metrics
│   │   └── settings/      # User settings
│   ├── login/             # Login page
│   ├── signup/            # Signup page
│   └── page.tsx           # Entry redirect
├── components/
│   └── layout/            # Sidebar, Header
└── lib/
    ├── supabase/          # Supabase clients (browser, server, middleware)
    ├── api.ts             # API utilities
    └── utils.ts           # Helper functions
```

## Authentication Flow

1. User visits `/login` or `/signup`
2. Supabase handles email/password or OAuth (Google)
3. OAuth redirects to `/auth/callback`
4. Middleware protects `/dashboard/*` routes
5. Authenticated users are redirected to `/dashboard`

## Development

### Port Configuration

The dev server runs on port 3005 to avoid conflicts with:

- Internal portal (`apps/portal`) on 3001
- Experimental sites on 3000, 3002-3004

### Adding New Pages

1. Create a new folder under `src/app/dashboard/`
2. Add `page.tsx` with your component
3. Update the sidebar navigation in `src/components/layout/sidebar.tsx`

## Deployment

Build for production:

```bash
npm run build
```

The output can be deployed to Vercel, Netlify, or any Node.js hosting.
