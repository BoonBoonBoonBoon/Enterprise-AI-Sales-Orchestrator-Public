# Design Philosophy

This page captures the **guiding principles** for all websites and portals in the Agentic System ecosystem.

---

## Core Principles

### 1. Product-First, Not Tech-First

The portal exists to solve **business problems** for B2B customers—not to showcase technology. Every feature must answer:

- What workflow does this enable?
- What pain does this remove?
- How does this reduce friction for the operator?

**Implication:** Avoid "cool tech" features that don't map to a clear user goal. Ship boring but useful before flashy.

---

### 2. Safe by Default

Agentic automation is powerful—and risky. The portal must:

- **Default to human approval** (no auto-send without explicit opt-in).
- **Surface hard-stops and throttles** visibly (never hide why something was blocked).
- **Make dangerous actions feel dangerous** (confirmation dialogs, red buttons, explicit warnings).

**Implication:** The safest setting should always be the default; risky settings require explicit activation.

---

### 3. Tenant-Scoped Everything

Every piece of data, every metric, every setting is **scoped to the logged-in tenant**. Users should never see data from other tenants, and the system must enforce this at the database level (RLS).

**Implication:** No global views for customers; admin-only dashboards can aggregate across tenants but are never customer-facing.

---

### 4. API-First Architecture

The portal never talks to Redis streams, agents, or internal services directly. It only calls a **versioned HTTP API** (`/api/v1/*`).

**Implication:**

- UI changes don't break the engine.
- Engine changes don't break the UI.
- The API is the product contract.

---

### 5. Composable Components

UI components are designed for **reuse across portals** (internal, customer, marketing). A shared component library ensures:

- Consistent look and feel.
- Faster iteration (build once, use everywhere).
- Easier maintenance.

**Implication:** Invest in a design system early; don't copy-paste UI code between apps.

---

### 6. Traceability by Default

Every action, every draft, every send must be **traceable**. Users should be able to:

- See why something happened (or didn't).
- Find the `correlation_id` for support escalation.
- Understand the system's reasoning (e.g., `query_trace` for RAG).

**Implication:** Build observability into the UI, not just logs. Surface trace fields in the product.

---

### 7. Progressive Disclosure

Don't overwhelm users with options. Show:

- **Level 1:** Essential actions (approve, reject, send).
- **Level 2:** Common settings (toggle auto-send, edit draft).
- **Level 3:** Advanced/power-user features (policy rules, throttle config).

**Implication:** Use collapsible sections, "Advanced" toggles, and contextual help. Keep the primary path clean.

---

### 8. Mobile-Aware (Not Mobile-First)

B2B ops workflows happen on desktop, but operators check status on mobile. Design for:

- **Desktop:** Full workflow (editing, approvals, settings).
- **Mobile:** Status checks, quick approvals, notifications.

**Implication:** Responsive design is required; mobile-specific features (push notifications) are a bonus.

---

## UX North Stars

| Principle    | Anti-Pattern                   | Good Pattern                                           |
| ------------ | ------------------------------ | ------------------------------------------------------ |
| Clarity      | Vague status ("Processing...") | Specific status ("Awaiting approval: 3 drafts")        |
| Control      | Auto-send enabled silently     | Explicit opt-in with confirmation                      |
| Traceability | "Something went wrong"         | "Failed: rate limit exceeded (correlation_id: abc123)" |
| Speed        | Full page reloads              | Optimistic UI with background sync                     |
| Trust        | Hidden costs/limits            | Visible usage meters and plan limits                   |

---

## Technology Stack (Rationale)

| Choice                   | Why                                                                 |
| ------------------------ | ------------------------------------------------------------------- |
| **Next.js (App Router)** | SSR for SEO (marketing), server actions for portal, React ecosystem |
| **Supabase Auth**        | Managed auth, RLS, multi-tenant ready, fast integration             |
| **Tailwind + Radix**     | Utility CSS + accessible primitives, fast iteration                 |
| **FastAPI Gateway**      | Python ecosystem match, async, OpenAPI, easy RBAC                   |

---

## Anti-Patterns to Avoid

1. **Portal talks to Redis directly** → Always go through the API.
2. **Global metrics shown to customers** → Everything is tenant-scoped.
3. **Auto-send enabled by default** → Approval-first is the only safe default.
4. **Copy-pasted UI between apps** → Use the shared component library.
5. **"Magic" without explanation** → Always show reasoning and trace data.

---

## See Also

- [Portal Feature Roadmap](roadmap.md)
- [Implementation Details](implementations.md)
