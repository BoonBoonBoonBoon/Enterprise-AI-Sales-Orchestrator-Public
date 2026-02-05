# Agentic Portal

Modern, sleek B2B customer portal for the Agentic System.

## Tech Stack

- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS** + **shadcn/ui** components
- **Supabase Auth** (authentication)
- **Lucide React** (icons)

## Getting Started

### Prerequisites

- Node.js 18+
- npm or pnpm

### Installation

```bash
cd apps/portal
npm install
```

### Environment Setup

Copy the example environment file:

```bash
cp .env.example .env.local
```

Configure your environment variables:

```
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
API_GATEWAY_URL=http://localhost:8000
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── dashboard/          # Authenticated portal pages
│   │   ├── drafts/         # Approval queue
│   │   ├── inbox/          # Conversation viewer
│   │   ├── leads/          # Leads database
│   │   ├── mailboxes/      # Mailbox management
│   │   ├── settings/       # Account settings
│   │   ├── layout.tsx      # Dashboard layout with sidebar
│   │   └── page.tsx        # Dashboard home
│   ├── login/              # Authentication
│   ├── globals.css         # Global styles
│   ├── layout.tsx          # Root layout
│   └── page.tsx            # Landing page
├── components/
│   ├── layout/             # Layout components (Sidebar, Header)
│   └── ui/                 # Reusable UI components
├── hooks/                  # Custom React hooks
└── lib/                    # Utilities
```

## Pages

| Route                  | Description                     |
| ---------------------- | ------------------------------- |
| `/`                    | Public landing page             |
| `/login`               | Authentication (login/signup)   |
| `/dashboard`           | Overview with stats and actions |
| `/dashboard/drafts`    | Approval queue for AI drafts    |
| `/dashboard/inbox`     | Conversation viewer             |
| `/dashboard/leads`     | Leads database with filtering   |
| `/dashboard/mailboxes` | Connect and manage mailboxes    |
| `/dashboard/settings`  | Account and policy settings     |

## Design System

The portal uses a dark theme with AI/tech-inspired styling:

- **Primary colors:** Blue to purple gradients
- **Accent colors:** Cyan, green for success, yellow for pending
- **Effects:** Glassmorphism, subtle glows, animated gradients
- **Typography:** Inter font family

## API Integration

The portal communicates with the API gateway at `/api/v1/*`. All requests are proxied through Next.js rewrites to avoid CORS issues.

Example API calls (to be implemented):

```typescript
// Get drafts
GET / api / v1 / drafts;

// Approve a draft
POST / api / v1 / drafts / { id } / approve;

// Get leads
GET / api / v1 / leads;

// Connect mailbox
POST / api / v1 / mailboxes;
```

## Building for Production

```bash
npm run build
npm start
```

## Notes

- This is the MVP version with mock data
- Authentication is placeholder (redirect to dashboard)
- API integration to be connected to the FastAPI gateway
