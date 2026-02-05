# Pricing & Competitive Research Guide (Monty)

This guide is a **living reference** for setting pricing and comparing Monty against similar “AI employee / AI SDR / inbox copilot” products.

It is written to help you:

- Choose a pricing model that matches your product reality (trust, autonomy, scope).
- Compare competitors on **dimensions that matter** (not feature checklists).
- Run pricing experiments safely without breaking positioning.

**Status:** Draft (keep updating as you gather real market data)

---

## 1) What you’re selling (so pricing is coherent)

Monty today is best described as:

- A **workflow system** for inbound/outbound email handling (draft → review/approve → optional send)
- With **agentic orchestration** (Manager → Orchestrators → Tier-3 Agents)
- Backed by **retrieval + traceability** (`query_trace`, `correlation_id`, auditability)

That is meaningfully different from a pure “AI employee” pitch.

### The pricing implication

You can price Monty as:

1. **Copilot / productivity software** (lower ACV, high volume) or
2. **Managed outcome system** (higher ACV, higher expectations) or
3. A **hybrid**: software + optional managed services

A mismatch here causes churn.

---

## 2) Pricing models (pick 1 primary, 1 secondary)

### Model A — Per seat (classic SaaS)

**Best when:** Monty is used by a team; permissions + workflows matter.

- Pros: familiar; easy procurement; aligns with portal UX
- Cons: heavy-usage teams may become unprofitable if inference costs scale hard

**Add cost-control:** seat-based + usage caps/overages.

### Model B — Per inbox (aligns with email systems)

**Best when:** inbox connections are the atomic value unit.

- Pros: simple; maps to your multi-mailbox architecture; predictable
- Cons: a single inbox can generate high usage; needs throttles/tiers

### Model C — Usage based (drafts/messages/credits)

**Best when:** LLM + enrichment costs scale with volume.

- Pros: protects margin; ties to cost drivers
- Cons: can feel unpredictable; buyers dislike “meter anxiety”

### Model D — Outcome based (meetings booked / qualified leads)

**Best when:** you can measure attribution cleanly.

- Pros: premium; aligns with “AI employee” narrative
- Cons: attribution disputes, long sales cycles, edge cases

### Model E — Managed service retainer (done-for-you)

**Best when:** you want agencies/SMBs who buy outcomes, not tools.

- Pros: high ACV; fast iteration; strong moat
- Cons: requires operations team; less scalable

---

## 3) Recommended pricing approach for Monty (practical)

### Suggested default: Seat + Inbox + Included usage

A simple, defensible structure:

- **Base plan** includes a number of inboxes + seats + included draft volume
- **Overages** only kick in at high usage
- **Autopilot** remains a premium feature gate (trust + risk)

Why: it matches how customers think (seats/inboxes) while keeping costs bounded.

### Trust ladder (you can charge more for autonomy)

Price increases should track autonomy level:

1. **Draft-only** (review required)
2. **Suggest-send** (still approval-first)
3. **Autopilot** (policy-controlled sending)

Autonomy is where “AI employee” pricing becomes credible.

---

## 4) Competitive comparison framework (use this, not “features”)

When comparing to products like 11x-style “AI SDR” offerings, track these axes:

### Axis 1 — Autonomy

- Draft-only
- Approval-first
- Autopilot within guardrails
- Fully autonomous with minimal review

### Axis 2 — Control surface

- Can the user _see_ why decisions were made?
- Is there an audit trail (`query_trace`, logs, message history)?
- Can they constrain actions with explicit policies?

### Axis 3 — Context quality

- Pure prompt + recent thread
- CRM enrichment
- RAG across internal data / conversation history
- Multi-source provenance + confidence scoring

### Axis 4 — Operational maturity

- DLQ/retries/backpressure
- Observability
- Idempotency + dedup
- Tenant isolation / RBAC

### Axis 5 — Deployment + security posture

- Hosted only
- Dedicated environment
- On-prem / VPC
- Data retention controls

---

## 5) “Monty vs 11x-style AI SDR” (high-level differences)

This is intentionally **product-shape** focused. Update it as you verify competitor claims.

### Monty (your system)

- Strength: **system architecture + controllability** (vertical-only orchestration, traceability, safe defaults)
- Natural posture: **approval-first** with optional autopilot
- Strong fit: inbound workflows + team review + operational transparency
- Expansion path: internal copilot (FAQ), CS inbox copilot, workflow builder

### 11x-style AI SDR offerings

- Strength: “**AI employee**” narrative, often bundled with outbound prospecting + meeting booking
- Natural posture: **high autonomy** (buyers expect outcomes)
- Strong fit: teams willing to trade control for velocity
- Risk: trust/compliance concerns; opaque decisioning; higher expectation gap

### What to highlight when selling against them

- **Control + safety:** approval-first, policy gating, hard-stops
- **Traceability:** why decisions happened (`query_trace`, correlation)
- **Extensibility:** modular agentic system vs monolithic “employee”
- **Operational reliability:** retries/DLQ/backpressure and tenant safety

---

## 6) Competitor research checklist (copy/paste)

Create one row per competitor and fill in facts you verify.

| Company              | Category             | ICP                   | Pricing model | Autonomy default | Guardrails/policies | Proof (case studies) | Notes                |
| -------------------- | -------------------- | --------------------- | ------------- | ---------------- | ------------------- | -------------------- | -------------------- |
| 11x (verify)         | AI SDR / AI employee | Mid-market/Enterprise | (verify)      | (verify)         | (verify)            | (verify)             | (verify)             |
| Infinite AI (verify) | AI employees         | (verify)              | (verify)      | (verify)         | (verify)            | (verify)             | (verify)             |
| Artisan (verify)     | AI BDR               | (verify)              | (verify)      | (verify)         | (verify)            | (verify)             | (verify)             |
| Apollo               | Sales engagement     | SMB/Mid               | Seat          | Low/Medium       | Medium              | Strong               | Tooling-heavy        |
| Outreach             | Sales engagement     | Mid/Enterprise        | Seat          | Medium           | High                | Strong               | Enterprise workflows |

**Verification rules:**

- Prefer primary sources (pricing pages, terms, docs, official demos).
- Note the date you checked.
- Save screenshots/links in your research folder.

---

## 7) Pricing experiments (low-risk)

### Experiment 1 — Founding cohort offer (early access)

- Lock-in discount for first X customers
- Clear cap (time/slots)
- Keep it simple: one plan + one add-on

Measure:

- Conversion rate from marketing → signup
- Onboarding completion
- Weekly active usage (drafts reviewed, approvals)

### Experiment 2 — Add-on pricing for autonomy

- Base plan = draft-only
- Add-on = autopilot

Measure:

- Trust adoption: % enabling autopilot
- Churn or support load changes after enabling

### Experiment 3 — Usage overage threshold

- Include enough volume for “normal” teams
- Overages only above a high threshold

Measure:

- Gross margin stability
- Sales objections about “credits”

---

## 8) How to estimate willingness to pay (WTP)

Use three anchors:

1. **Time saved** (hours/week) × blended rate
2. **Revenue impact** (faster responses → more conversions)
3. **Headcount replacement** (only when autonomy is real)

A conservative ROI framing for approval-first products is usually time-based, not headcount-based.

---

## 9) Where to store updates

- Add new competitors and verified facts to this file.
- Add product expansion ideas to `docs/roadmap/future.md`.
- If you change the public pricing page, record the decision in `docs/roadmap/changelog.md`.
