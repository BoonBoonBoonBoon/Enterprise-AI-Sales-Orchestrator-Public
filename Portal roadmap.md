# Portal Roadmap (Client Ops Portal) — Jan 2026

This document defines the **client-facing frontend** strategy for the Agentic System, with an MVP focus on an **Ops Portal for B2B customers**.

The portal is the product surface that makes the existing backend feel like **real B2B software**: onboarding, control, approval workflow, visibility, and billing.

---

## Product North Star

Deliver a portal where a customer (ops user) can:

1. Connect one or more mailboxes.
2. See their **inbox activity** and browse full conversations/threads.
3. See inbound-triggered drafts with retrieved context.
4. Approve/edit/reject replies.
5. Optionally enable controlled auto-send policies.
6. Track what happened (status, traceability, failures) without engineering help.

### MVP goal (explicit)

Each customer logs into a portal and sees **personalized, tenant-scoped**:

- Metrics (e.g., lifetime emails sent/received, drafts created, approvals, sends, failures, leads qualified)
- Inbox and conversation history
- Leads database (leads + qualified leads)
- Draft approval queue

---

## Scope Choices (Locked for MVP)

### Target buyer / user

- **Primary persona:** B2B customer ops team (admin + operators + viewers).
- **Tenant model (MVP):** **one customer per tenant**, supporting **multiple mailboxes** inside that tenant.
- **Future option (keep on roadmap):** agency tenant with client sub-workspaces (true hierarchy; see “Future Expansion”).

### Sending modes

- **Human approval first (default):** draft-only until explicitly approved.
- **Auto-send (optional):** allowed but controlled by policy + throttles + hard-stops.

---

## Goals (What the portal must enable)

### 1) Customer-specific visibility (tenant-scoped)

- Personalized metrics and KPIs for the logged-in tenant
- Inbox browsing per connected mailbox
- Conversation/thread view with full message chain
- Leads + qualified leads browsing/search

### 2) Customer control (safe-by-default)

- Draft review + edit + approve + reject
- Auto-send is available but not the default; it is always policy-controlled
- Clear reasons for blocked sends (hard-stops, throttles, policy)

### 3) Supportability (no-engineer debugging)

- Expose traceability fields in UI (e.g., `correlation_id` and a readable `query_trace` summary)
- Clear statuses: drafted → approved → sent/failed (with errors)

---

## Two-Frontend Strategy (Recommended)

Most B2B SaaS needs **two frontends** (can share a design system):

1. **Marketing website (public):** credibility + conversion (pricing, security, demo).
2. **Customer portal (authenticated):** operational workflows (mailboxes, drafts, approvals).

This roadmap focuses on (2) **Customer portal**, while keeping marketing work as a parallel track.

---

## Portal vs Generic Website (Why Portal First)

Because the MVP is an **ops workflow** (inbound → draft → approval → send), a portal is required for:

- Approval queue UX (especially with `OUTBOUND_APPROVAL_MODE=1`).
- Per-tenant settings (mailboxes, campaigns, limits, policies).
- Supportability (trace-by-correlation, status visibility, failure reasons).

A purely generic website only works for hands-off products; this MVP is not hands-off.

---

## MVP Portal UX (What the portal includes)

### Primary navigation (MVP)

- **Drafts (Approval Queue)** — main screen
- **Conversations** — thread + context viewer
- **Mailboxes** — connect/manage multiple mailboxes
- **Campaigns (basic)** — defaults, signatures, safe settings
- **Settings** — tenant profile, policy flags, users/roles
- **Usage & Billing** — plan, limits, invoices (if billing ships in MVP)

### The Draft Card (the key UI component)

Each draft shows:

- From / subject / received time
- Mailbox (which inbox this belongs to)
- Retrieved lead/company facts (when available)
- Recent messages/context snippet
- Drafted reply (editable)
- Status and trace fields (`correlation_id`, `query_trace` summary)
- Actions:
  - **Approve & Send**
  - **Reject** (with reason)
  - **Save edit**
  - (Optional) **Request rewrite**

### MVP “Golden Path” User Journey

1. Operator signs up / logs in
2. Creates/joins a tenant (one customer per tenant)
3. Connects 1+ mailboxes
4. Sends a test email to a connected inbox
5. Draft appears in Draft Queue
6. Operator edits and approves
7. System sends (or fails) and logs outcome with traceability

---

## Roadmap: Portal Build-Out (Phased)

### Phase P0 — Product contract (2–4 days)

- Finalize the portal’s domain model:
  - Mailbox
  - Draft
  - Conversation
  - Campaign
  - Policy
  - Tenant
  - User + Roles
- Freeze API contract surface for portal: all UI functionality must map to versioned API endpoints (`/api/v1/*`).

**Exit criteria:** screens can be mocked against a stable API spec.

### Phase P1 — Skeleton portal + auth (Week 1)

- Build a minimal portal shell (layout, navigation).
- Implement authentication and tenant selection.
- Implement RBAC basics (admin vs operator vs viewer).

**Exit criteria:** user logs in, selects tenant, sees empty “Drafts” view.

### Phase P2 — Mailboxes (Week 2)

- Add multi-mailbox management:
  - connect mailbox
  - connection status
  - label/routing config (minimal)
- Minimal “send a test message → draft appears” operator workflow.

**Exit criteria:** mailbox can be added and shows health + last sync.

### Phase P3 — Draft Queue + Conversation Viewer (Week 3)

- Draft queue with editable composer.
- Conversation viewer with retrieved context.
- Approve/send and reject flows.

**Exit criteria:** operator can approve a draft and observe “Sent/Failed” with traceability.

### Phase P4 — Policies (approve-first default + controlled auto-send) (Week 4)

- Settings UI for:
  - approve-first default (required)
  - auto-send enablement
  - throttles/limits
  - hard-stop rules display
- Guardrails in UI to prevent risky auto-send defaults.

**Exit criteria:** tenant can enable auto-send in a controlled way and understands what it does.

### Phase P5 — Billing + usage (Week 5)

- Basic plan view and limits.
- Usage meter summary (messages/day, drafts/day, mailboxes).
- If Stripe ships: invoices + subscription state.

**Exit criteria:** billing state is visible; plan limits are explainable and enforceable.

---

## Alternative Frontend Concepts (Keep on Roadmap)

These are deliberately _not_ MVP focus, but remain options:

1. **Campaign Portal:** “Autopilot Outreach Manager”
   - Emphasis: campaign creation, lead lists, outreach scheduling
   - Tradeoff: bigger surface area, slower MVP

2. **Unified Workspace:** “All-in-one Sales Workspace”
   - Emphasis: CRM-like UI + analytics + multi-channel
   - Tradeoff: highest scope, highest build cost

---

## Technology Options (Choices to Keep Visible)

### Option A — Extend Streamlit (fastest)

- Pros: fastest iteration, Python-native, good for internal/beta
- Cons: weaker B2B perception, harder auth/RBAC/billing polish

### Option B — Next.js Portal (recommended for B2B)

- Next.js App Router, server actions
- Shared component library
- Auth (recommended: Supabase Auth)

**Recommendation:** build Option B for customers; keep Streamlit for internal admin.

---

## Modularity Principles (Non-Negotiables)

To avoid rewrites post-MVP:

- **API-first portal:** portal never touches Redis directly; it calls `/api/v1/*`.
- **Tenant-scoped config:** mailbox mappings, policy flags, limits stored per tenant (DB-backed when ready).
- **Adapter pattern:** mailbox providers and senders are adapters (Gmail/IMAP now, Outlook later).
- **Feature flags:** new features gated behind flags; safe defaults for sending.
- **Versioning:** breaking changes get `/api/v2/*` rather than breaking v1.

---

## What NOT to Build for MVP (Time sinks)

- Full CRM replacement UI
- Complex analytics dashboards
- Multi-channel messaging UI (SMS/LinkedIn/etc)
- Deep campaign builders
- Fancy AI chat interfaces

---

## Open Decisions (Capture all choices)

- Primary inbox provider: Gmail API vs IMAP vs both
- Tenant model expansion: agency-tenant with sub-clients (true multi-tenant hierarchy) vs flat
- Auto-send policy granularity: global toggle vs per-mailbox vs per-campaign
- Pricing metric: per mailbox, per seat, or per message volume
- Portal stack: Streamlit vs Next.js

---

## Definition of Done (Portal MVP)

Portal is “MVP sellable” when:

- A new customer can self-onboard, connect 2+ mailboxes, and run the golden path.
- Drafts reliably appear with enough context to approve.
- Approve-first is default; auto-send is optional and controlled.
- Failures are visible with reason and trace identifiers.
- Plan limits and usage are visible (billing optional but strongly recommended for B2B sales).

---

## Future Expansion (Keep on Roadmap)

The MVP ships as **one customer per tenant**, but we explicitly keep these as planned options:

### Option 1 — Agency hierarchy (tenant → client workspaces)

- One agency tenant contains multiple client workspaces.
- Each workspace has:
  - mailboxes
  - leads
  - metrics
  - policies
- Operators can switch workspaces; RBAC can be workspace-scoped.

### Option 2 — True multi-tenant platform (reseller / white-label)

- Agency provisions and manages client tenants.
- Billing can be consolidated at agency level.
- Requires stronger provisioning flows, audit trails, and support tooling.

# System Des ----------------------------------------------

## Recommendation: keep it in the same repo (monorepo), but as _separate apps_

For MVP speed **and** long-term modularity, keep everything in **this repository** and add a clean “apps + services” structure. Avoid mixing frontend code into the existing tier folders.

A separate repo is only worth it later (when you have multiple teams, independent release cadence, or strict security boundaries).

---

## Why same repo is the right move (right now)

- **Shared contracts:** the portal must match your envelopes/status model, tenant model, and API contracts.
- **Fewer integration failures:** auth/tenant/RLS rules, approval states, and mailbox config are easier to iterate when versioned together.
- **Post-MVP modularity:** you can still keep strict boundaries by directory + interfaces (API-first), without repo sprawl.

---

## System design rule for the portal (most important)

**The portal must never talk to Redis streams directly.**  
It should only call a versioned HTTP API (`/api/v1/*`). That API layer is the “product boundary” that protects your 3-tier engine from UI churn.

---

## Proposed local folder layout (minimal, modular, B2B-standard)

Add a top-level `apps/` and `api/` without disturbing tiers, core, services.

```text
Agentic System/
├─ apps/
│  ├─ portal/               # Next.js authenticated ops portal (customers)
│  └─ marketing/            # Next.js/astro static marketing site (optional)
├─ api/
│  └─ gateway/              # FastAPI: /api/v1 (auth, tenants, drafts, mailboxes)
├─ tiers/                   # unchanged (Manager/Orchestrators/Agents)
├─ core/                    # unchanged
├─ services/                # unchanged
├─ deployment/              # unchanged
├─ docs/                    # add portal specs + API contracts here
└─ ...existing files...
```

### What lives where (clear boundaries)

- **`apps/portal`**: UI, routes, components, portal auth UI, approval UX
- **`api/gateway`**: tenant-aware API, RBAC, plan enforcement, webhooks
- **`tiers/*`**: unchanged orchestration engine (Redis Streams, envelopes)
- **`services/*`**: adapters (Supabase, email providers, etc.)

---

## Sequence to build locally (lowest regret)

1. **Create `api/gateway` first** with just:
   - auth session validation (Supabase)
   - tenant selection
   - “list drafts” + “approve draft” endpoints (even if stubbed initially)

2. **Create `apps/portal` next** and point it at the gateway.
   - Build UI pages against mocked responses if needed.
   - Replace mocks once gateway endpoints are ready.

3. Keep **Streamlit** as internal admin (optional), but don’t ship it as the customer portal unless you’re intentionally doing a “beta console” phase.

---

## When a separate repo _does_ make sense

Split later if:

- you need separate deployments/domains per app (portal vs engine)
- you want stricter access control (frontend devs shouldn’t see infra secrets)
- you have multiple teams releasing independently

Until then: monorepo + strict boundaries is cleaner.

---

## One clarifying question (to finalize structure)

Do you want the **API gateway to also serve the marketing/portal** in production (single deployment), or do you plan **separate deployments** (portal on Vercel, API on a server/K8s)? This affects env handling and CORS from day one.
