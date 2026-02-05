# System-Wide Development Roadmap (Monty)

**Last Updated:** February 2026

This document provides a **single-page** view of what still needs to be built system-wide, organized by domain. Use it to prioritize sprints, identify dependencies, and track progress across the stack.

---

## Legend

| Icon | Meaning                              |
| ---- | ------------------------------------ |
| ✅   | Complete / shipped                   |
| 🚧   | In progress (skeleton or partial)    |
| 📋   | Planned / not started                |
| ⚠️   | Blocked or has critical dependencies |

---

## 1) Backend — Tier 2 Orchestrators

| Component                      | Status | Description                                           | Dependencies                  | Priority |
| ------------------------------ | ------ | ----------------------------------------------------- | ----------------------------- | -------- |
| **Leads Orchestrator**         | ✅     | Builds `reply_packet` from inbound context            | RAG Agent                     | P0       |
| **Outreach Orchestrator**      | ✅     | Delegates to Copywriter, optional auto-send           | Copywriter, Channel Sequencer | P0       |
| **Inbound Orchestrator**       | ✅     | Triage + classification + routing                     | Classifier Agent              | P0       |
| **Audit Orchestrator**         | 🚧     | Compliance + quality monitoring for outbound          | Policy engine, QA rules       | P1       |
| **Control Orchestrator**       | 📋     | Pause/resume campaigns, config updates, feature flags | Admin API, portal settings    | P2       |
| **Re-Engagement Orchestrator** | 📋     | Detect stale leads, trigger follow-up sequences       | Scheduler Agent, Leads DB     | P2       |
| **Booking Orchestrator**       | 📋     | Calendar availability, link generation, confirmation  | Calendar API, Scheduler Agent | P2       |

---

## 2) Backend — Tier 3 Agents

| Agent                       | Status | Description                                   | Dependencies                    | Priority |
| --------------------------- | ------ | --------------------------------------------- | ------------------------------- | -------- |
| **RAG Agent**               | ✅     | Retrieval + context assembly for leads/convos | Supabase, vector DB             | P0       |
| **Persistence Agent**       | ✅     | CRUD operations + staging promotion           | Supabase RLS                    | P0       |
| **Copywriter Agent**        | ✅     | AI draft generation                           | LLM provider                    | P0       |
| **Classifier Agent**        | ✅     | Inbound triage (rules + LLM fallback)         | —                               | P0       |
| **Channel Sequencer Agent** | 🚧     | Multi-channel send execution + throttles      | Email service, LinkedIn API     | P1       |
| **Scheduler Agent**         | 🚧     | Delayed/scheduled tasks, send windows         | Redis delay queue               | P1       |
| **Enrichment Agent**        | 📋     | Lead/company data enrichment                  | External APIs (Clearbit, etc.)  | P2       |
| **Tone/Voice Agent**        | 📋     | Tenant-specific style enforcement             | Fine-tuned model or prompt bank | P2       |
| **Profile Writer Agent**    | 📋     | Generate/update lead profiles from signals    | RAG Agent, Persistence          | P2       |
| **Call Prep Agent**         | 📋     | Pre-call briefing generation                  | Calendar, conversation history  | P3       |
| **Call Summary Agent**      | 📋     | Post-call summary + next steps extraction     | Transcription provider          | P3       |
| **Copilot Agent**           | 📋     | Internal FAQ / objection handling             | RAG + knowledge base            | P2       |

---

## 3) API Gateway (`api/gateway`)

| Endpoint / Feature        | Status | Description                          | Dependencies         | Priority |
| ------------------------- | ------ | ------------------------------------ | -------------------- | -------- |
| **Auth + Session**        | ✅     | Supabase JWT validation              | Supabase Auth        | P0       |
| **Tenant Selection**      | ✅     | Multi-tenant context                 | —                    | P0       |
| **Drafts CRUD**           | 🚧     | List/get/update/delete drafts        | Persistence Agent    | P0       |
| **Drafts Approve/Reject** | 🚧     | Approval workflow                    | Channel Sequencer    | P0       |
| **Mailboxes CRUD**        | 🚧     | Connect/manage inboxes               | OAuth, Inbox Monitor | P1       |
| **Conversations**         | 🚧     | Thread view + context                | Persistence          | P1       |
| **Leads CRUD**            | 📋     | Lead table operations                | Persistence          | P1       |
| **Campaigns CRUD**        | 📋     | Campaign management                  | Control Orchestrator | P2       |
| **Policies API**          | 📋     | Auto-send rules, hard-stops          | Policy engine        | P2       |
| **Usage / Billing**       | 📋     | Metering, limits, Stripe integration | Billing service      | P2       |
| **Booking API**           | 📋     | Availability, booking links          | Calendar API         | P2       |
| **Copilot Chat API**      | 📋     | Real-time FAQ/objection endpoint     | Copilot Agent, RAG   | P2       |
| **Webhooks (Inbound)**    | 🚧     | Receive inbound email events         | Manager              | P1       |
| **Webhooks (Outbound)**   | 📋     | Notify external systems on events    | —                    | P3       |

---

## 4) Customer Portal (`apps/portal-customer`)

| Feature                         | Status | Description                               | Dependencies         | Priority |
| ------------------------------- | ------ | ----------------------------------------- | -------------------- | -------- |
| **Login / Auth**                | ✅     | Supabase Auth flow                        | Supabase             | P0       |
| **Dashboard Overview**          | 🚧     | Stats, Monty status, onboarding checklist | API metrics          | P0       |
| **Draft Queue**                 | 🚧     | View/edit/approve/reject drafts           | Drafts API           | P0       |
| **Inbox / Conversation Viewer** | 📋     | Browse threads per mailbox                | Conversations API    | P1       |
| **Mailbox Management**          | 📋     | Connect/disconnect inboxes                | Mailboxes API, OAuth | P1       |
| **Leads Browser**               | 📋     | Table view, search, filters               | Leads API            | P1       |
| **Campaign Settings**           | 📋     | Create/edit campaigns                     | Campaigns API        | P2       |
| **Policy Settings**             | 📋     | Auto-send, hard-stops, throttles          | Policies API         | P2       |
| **Tone/Voice Settings**         | 📋     | Tenant style config, examples             | Tone Agent, API      | P2       |
| **Booking Settings**            | 📋     | Calendar connect, availability            | Booking API          | P2       |
| **Usage Meters**                | 🚧     | Current plan, limits, usage               | Billing API          | P1       |
| **Plan Management**             | 📋     | Upgrade/downgrade, invoices               | Stripe               | P2       |
| **Team / RBAC**                 | 📋     | Invite users, assign roles                | Auth, Supabase       | P2       |
| **Copilot Chat Widget**         | 📋     | Internal help / objection handler         | Copilot API          | P2       |
| **Notifications Center**        | 📋     | In-app alerts, activity feed              | Events, WebSocket    | P3       |

---

## 5) Marketing Site (`apps/portal-experimental-4`)

| Feature                         | Status | Description                        | Dependencies           | Priority |
| ------------------------------- | ------ | ---------------------------------- | ---------------------- | -------- |
| **Hero + Orb**                  | ✅     | Animated brand hero                | —                      | P0       |
| **How It Works**                | ✅     | 3-step explainer                   | —                      | P0       |
| **Features / Benefits**         | ✅     | Value props                        | —                      | P0       |
| **Pricing**                     | ✅     | Tiered pricing cards               | —                      | P0       |
| **FAQ**                         | ✅     | Common questions                   | —                      | P0       |
| **Ask Monty (Placeholder)**     | ✅     | Pre-signup chat placeholder        | —                      | P1       |
| **Ask Monty (Live)**            | 📋     | Wire to Copilot API                | Copilot Agent, Gateway | P2       |
| **Use Cases Section**           | ✅     | Cold outreach, follow-ups, inbound | —                      | P0       |
| **Testimonials / Social Proof** | 📋     | Customer quotes, logos             | Content                | P1       |
| **ROI Calculator**              | 📋     | Interactive savings estimator      | —                      | P2       |
| **Live Demo**                   | 📋     | Sandboxed trial experience         | Demo tenant            | P2       |
| **Blog / Resources**            | 📋     | Content marketing pages            | CMS or MDX             | P3       |

---

## 6) Core Utilities / Infrastructure

| Component                 | Status | Description                         | Dependencies       | Priority |
| ------------------------- | ------ | ----------------------------------- | ------------------ | -------- |
| **DLQ + Retry**           | ✅     | Dead letter queue for failed tasks  | Redis              | P0       |
| **Graceful Shutdown**     | ✅     | In-flight task handling             | —                  | P0       |
| **Token Management**      | ✅     | Budget tracking, truncation         | —                  | P0       |
| **Observability**         | 🚧     | Tracing (OTel), metrics, logs       | Datadog/Prometheus | P1       |
| **Rate Limiting**         | 📋     | Per-tenant limits                   | Redis              | P1       |
| **Multi-Provider LLM**    | 📋     | OpenAI ↔ Anthropic ↔ local fallback | Config layer       | P1       |
| **A/B Testing Framework** | 📋     | Variant assignment, metrics         | —                  | P2       |
| **Fine-Tuning Pipeline**  | 📋     | Tenant-specific model training      | Training infra     | P3       |

---

## 7) Cross-Cutting Capabilities (New)

These are **system-wide features** that touch multiple layers.

### 7.1 Booking System

| Layer            | What to Build                                                | Status |
| ---------------- | ------------------------------------------------------------ | ------ |
| **Agent**        | Calendar integration (Google/Outlook), availability check    | 📋     |
| **Orchestrator** | Booking Orchestrator: link generation, confirmation handling | 📋     |
| **API**          | `/api/v1/booking/*` endpoints                                | 📋     |
| **Portal**       | Booking settings UI, calendar connect                        | 📋     |
| **Copywriter**   | Insert booking link in drafts                                | 📋     |

### 7.2 Re-Engagement System

| Layer            | What to Build                                                       | Status |
| ---------------- | ------------------------------------------------------------------- | ------ |
| **Agent**        | Scheduler Agent: delayed task execution                             | 🚧     |
| **Orchestrator** | Re-Engagement Orchestrator: stale lead detection, sequence triggers | 📋     |
| **API**          | Sequence CRUD, re-engagement rules                                  | 📋     |
| **Portal**       | Sequence builder UI, re-engagement settings                         | 📋     |

### 7.3 Audit / Compliance System

| Layer            | What to Build                                      | Status |
| ---------------- | -------------------------------------------------- | ------ |
| **Orchestrator** | Audit Orchestrator: pre-send QA, post-send logging | 🚧     |
| **Agent**        | QA Agent: banned phrases, tone rules, link checks  | 📋     |
| **API**          | Audit logs, compliance reports                     | 📋     |
| **Portal**       | Compliance dashboard, rule configuration           | 📋     |

### 7.4 Tone / Voice / Personality System

| Layer          | What to Build                                     | Status |
| -------------- | ------------------------------------------------- | ------ |
| **Agent**      | Tone Agent: style enforcement, prompt bank        | 📋     |
| **Config**     | Per-tenant voice settings (examples, constraints) | 📋     |
| **API**        | `/api/v1/voice/*` CRUD                            | 📋     |
| **Portal**     | Voice settings UI: upload examples, pick tone     | 📋     |
| **Copywriter** | Inject voice context into prompts                 | 📋     |

### 7.5 Profile Writing System

| Layer      | What to Build                                       | Status |
| ---------- | --------------------------------------------------- | ------ |
| **Agent**  | Profile Writer Agent: generate/update lead profiles | 📋     |
| **RAG**    | Aggregate signals (emails, enrichment, calls)       | 🚧     |
| **API**    | Profile CRUD, regenerate endpoint                   | 📋     |
| **Portal** | Lead profile view with AI-generated summary         | 📋     |

### 7.6 Internal Copilot (FAQ / Objection Handling)

| Layer              | What to Build                                     | Status |
| ------------------ | ------------------------------------------------- | ------ |
| **Agent**          | Copilot Agent: RAG over knowledge base + policies | 📋     |
| **Knowledge Base** | Ingest docs, FAQs, prior tickets                  | 📋     |
| **API**            | `/api/v1/copilot/chat` streaming endpoint         | 📋     |
| **Portal**         | Chat widget in dashboard                          | 📋     |
| **Marketing**      | Wire "Ask Monty" to live backend                  | 📋     |

### 7.7 Call Reminder / Prep System

| Layer            | What to Build                            | Status |
| ---------------- | ---------------------------------------- | ------ |
| **Agent**        | Call Prep Agent: generate pre-call brief | 📋     |
| **Scheduler**    | Reminder task before meeting             | 📋     |
| **API**          | `/api/v1/calls/prep` endpoint            | 📋     |
| **Portal**       | Pre-call brief card, notification        | 📋     |
| **Integrations** | Calendar sync, Zoom/Meet webhooks        | 📋     |

### 7.8 Multi-Channel System

| Layer            | What to Build                                        | Status |
| ---------------- | ---------------------------------------------------- | ------ |
| **Agent**        | Channel Sequencer: email → LinkedIn → phone fallback | 🚧     |
| **Integrations** | LinkedIn API, SMS provider, phone dialer             | 📋     |
| **API**          | Channel preferences, per-lead channel history        | 📋     |
| **Portal**       | Channel settings, unified timeline view              | 📋     |

### 7.9 Enhanced Inbound System

| Layer             | What to Build                                                 | Status |
| ----------------- | ------------------------------------------------------------- | ------ |
| **Orchestrator**  | Inbound Orchestrator (done), but extend for:                  | ✅     |
| **Classifier**    | More intent categories (pricing, support, demo request, spam) | 📋     |
| **RAG**           | Pull prior conversation + account context                     | ✅     |
| **Auto-Response** | Immediate acknowledgment for certain intents                  | 📋     |
| **Portal**        | Inbound analytics, classification accuracy review             | 📋     |

---

## 8) Suggested Build Order (Next 3 Sprints)

### Sprint 1 — Core Workflows

1. Finish **Scheduler Agent** (delayed sends, send windows)
2. Complete **Drafts API** + Portal draft queue polish
3. Ship **Mailboxes API** + Portal connect flow
4. Wire **Usage Meters** in portal

### Sprint 2 — Trust & Safety

1. Finish **Audit Orchestrator** (pre-send QA)
2. Build **Policies API** (hard-stops, throttles config)
3. Portal: **Policy Settings** UI
4. Portal: **Tone/Voice Settings** UI (config only, wired to prompts)

### Sprint 3 — Engagement & Intelligence

1. Build **Re-Engagement Orchestrator** + sequence triggers
2. Build **Copilot Agent** + knowledge base ingestion
3. Wire **Ask Monty** (marketing) to live Copilot API
4. Start **Booking Orchestrator** + calendar integration

---

## 9) Dependency Graph (Simplified)

```
                    ┌─────────────────────────────────────┐
                    │          PORTAL + MARKETING          │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │            API GATEWAY               │
                    │  (auth, tenants, drafts, policies)   │
                    └───────────────┬─────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   MANAGER     │         │  ORCHESTRATORS   │         │    SERVICES     │
│   (Tier 1)    │◄───────►│    (Tier 2)      │◄───────►│  (Redis, DB,    │
│               │         │                  │         │   Email, LLM)   │
└───────┬───────┘         └────────┬─────────┘         └─────────────────┘
        │                          │
        │                          ▼
        │                 ┌─────────────────┐
        └────────────────►│     AGENTS      │
                          │    (Tier 3)     │
                          └─────────────────┘
```

---

## 10) Files to Update When Building

| When you build...     | Update these docs                                           |
| --------------------- | ----------------------------------------------------------- |
| New Agent             | `docs/components/tier-3/`, `docs/roadmap/in-progress.md`    |
| New Orchestrator      | `docs/components/tier-2/`, `docs/roadmap/in-progress.md`    |
| New API Endpoint      | `api/gateway/routers/`, `docs/reference/api/`               |
| New Portal Page       | `apps/portal-customer/`, `docs/websites/portal-customer.md` |
| New Marketing Section | `apps/portal-experimental-4/`, `docs/websites/roadmap.md`   |
| Completed Feature     | Move from `in-progress.md` → `changelog.md`                 |

---

## 11) Open Questions (Capture Decisions)

- [ ] Calendar provider priority: Google Calendar first, or support both from day 1?
- [ ] LinkedIn integration: official API or third-party (Phantombuster, etc.)?
- [ ] Voice/tone: per-tenant fine-tuning vs. prompt injection vs. both?
- [ ] Copilot scope: internal-only or also customer-facing in portal?
- [ ] Multi-channel fallback logic: agent-side or orchestrator-side?
- [ ] Call integration: Zoom/Meet webhooks or manual upload first?
