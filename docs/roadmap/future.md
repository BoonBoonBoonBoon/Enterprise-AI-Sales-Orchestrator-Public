# Future Plans

Planned features and enhancements for upcoming releases.

## Q1 2026

### Multi-Provider LLM Support

**Priority:** P1  
**Effort:** Medium

Support switching between LLM providers (OpenAI, Anthropic, local models) without code changes.

**Planned:**

- Provider abstraction layer
- Configuration-based switching
- Fallback chains (OpenAI → Anthropic → local)
- Cost tracking per provider
- Performance comparison tooling

---

### Rate Limiting & Quotas

**Priority:** P1  
**Effort:** Medium

Per-tenant rate limiting and quota management.

**Planned:**

- Redis-based rate limiter
- Configurable limits per tenant
- Quota tracking and enforcement
- Graceful degradation when limits hit
- Admin dashboard for limit management

---

### A/B Testing Framework

**Priority:** P2  
**Effort:** Medium

Test different email templates, subject lines, and strategies.

**Planned:**

- Experiment definition (variants, traffic split)
- Automatic variant assignment
- Metric collection (open rate, reply rate)
- Statistical significance calculation
- Winner auto-promotion

---

## Q2 2026

### Fine-Tuning Pipeline

**Priority:** P2  
**Effort:** Large

Custom model fine-tuning for tenant-specific language and tone.

**Planned:**

- Training data collection from successful outreach
- Fine-tuning job orchestration
- Model versioning and rollback
- A/B testing fine-tuned vs. base models
- Cost-benefit analysis tooling

---

### Multi-Channel Orchestration

**Priority:** P2  
**Effort:** Large

Coordinate outreach across email, LinkedIn, phone, and other channels.

**Planned:**

- Channel Sequencer Agent completion
- LinkedIn API integration
- Unified contact timeline
- Cross-channel deduplication
- Channel performance analytics

---

### Advanced Analytics Dashboard

**Priority:** P2  
**Effort:** Medium

Comprehensive analytics for outreach performance.

**Planned:**

- Campaign performance metrics
- Lead funnel visualization
- Reply sentiment analysis
- Team performance tracking
- Export and reporting

---

## Q3 2026

### Voice Agent Integration

**Priority:** P3  
**Effort:** Large

AI-powered voice calls for outreach and qualification.

**Planned:**

- Voice synthesis integration
- Call scheduling and execution
- Transcription and analysis
- Handoff to human agents
- Compliance recording

---

### Self-Hosted LLM Support

**Priority:** P3  
**Effort:** Large

Support for self-hosted models (Llama, Mistral, etc.).

**Planned:**

- vLLM/TGI integration
- GPU infrastructure guidance
- Model download and management
- Performance optimization
- Hybrid cloud/local routing

---

### White-Label Platform

**Priority:** P3  
**Effort:** Large

Enable partners to offer the platform under their brand.

**Planned:**

- Theming and customization
- Partner management
- Billing integration
- Partner-specific limits
- Documentation white-labeling

---

## Backlog (Unscheduled)

## Adjacent Offerings (Product Expansion Ideas)

These are **additional sellable modules/services** that reuse the same agentic primitives you already have (ingress → Manager → orchestrators → Tier-3 agents → persistence + observability). They are intentionally written as “future work” so you can pick them up later without re-arguing the shape.

Each item includes a crisp MVP slice and what it would likely require.

### 1) Sales Call Copilot (Live + Post-Call)

**Problem it solves:** Reps miss follow-ups, next steps, and objection handling; managers lack consistent coaching signals.

**MVP slice:**

- Ingest call audio/transcript (Zoom/Meet upload webhook or manual upload).
- Generate: summary, next steps, risks, objections, and a follow-up email draft.
- Persist: call record + extracted entities + suggested tasks.

**Dependencies:** transcription provider, calendar/meeting integration, PII handling + retention policy.

**Monetization:** per-seat add-on; premium tier for coaching + analytics.

---

### 2) Customer Success Inbox Copilot (Renewals + Support)

**Problem it solves:** High-volume inbound support/CS email is repetitive; renewal risk signals are buried in threads.

**MVP slice:**

- Inbound triage + categorization (support vs renewal vs billing vs escalation).
- Draft replies using account context + prior resolution patterns.
- “Risk flags” surfaced to ops (sentiment downshift, churn keywords, repeated pain).

**Dependencies:** knowledge base ingestion (docs + prior tickets), safe escalation policy, approval-first UX.

**Monetization:** per-inbox/month; higher tier for risk scoring + playbooks.

---

### 3) Workflow Builder (Non-Dev Orchestration)

**Problem it solves:** Every new automation requires engineering changes; hard to iterate across teams.

**MVP slice:**

- UI for: triggers (email/webhook), steps (classify, retrieve, draft, store), and gates (approval, confidence threshold).
- Generates a validated “workflow spec” that the Manager can execute.
- Audit log: every step, inputs/outputs, decisions.

**Dependencies:** a stable internal workflow DSL, versioning/rollback, safety guardrails to prevent cross-stream violations.

**Monetization:** platform tier; charges scale with workflows + executions.

---

### 4) Deliverability + Domain Warmup (Ops Service)

**Problem it solves:** Outreach fails when deliverability is poor; warmup tooling is fragmented.

**MVP slice:**

- Health checks (SPF/DKIM/DMARC, bounce rate tracking).
- Warmup scheduler + throttles (ties into Channel Sequencer constraints).
- Simple dashboard: reputation indicators + recommended actions.

**Dependencies:** mailbox telemetry, sending constraints, strong compliance posture.

**Monetization:** managed service + subscription; premium onboarding package.

---

### 5) Data Enrichment + Lead Intelligence (RAG-First)

**Problem it solves:** Bad lead data causes weak personalization and wasted touches.

**MVP slice:**

- Given an email/domain: enrich company name, role, website, ICP tags.
- Persist enrichment with provenance + timestamps.
- Expose “confidence + sources” to downstream drafting.

**Dependencies:** external enrichment APIs, caching, cost controls, provenance tracking.

**Monetization:** per-enrichment credit packs; bundled into higher tiers.

---

### 6) Compliance / Brand QA Gate (Pre-Send Review)

**Problem it solves:** Teams need consistent tone + compliance checks before messages go out.

**MVP slice:**

- Run an automated QA pass on drafted outbound: banned phrases, claims, link checks, tone rules.
- Block or require approval with a human-readable reason.

**Dependencies:** policy engine + rule configuration UI, audit logging, tenant-specific rules.

**Monetization:** compliance add-on; regulated-industry tier.

---

### 7) “Human-in-the-Loop” Ops Console (Internal Service Offering)

**Problem it solves:** Many customers want outcomes, not tooling; your team needs a single pane for approvals and escalations.

**MVP slice:**

- Internal dashboard for: draft queue across tenants, escalations, retries/DLQ, and QA failures.
- SLA tagging + assignment.

**Dependencies:** multi-tenant admin RBAC, operational runbooks, DLQ workflows.

**Monetization:** managed service retainer; premium support plan.

---

### 8) “Playbook Packs” (Verticalized Copy + Policies)

**Problem it solves:** Customers struggle to configure prompts/policies; time-to-value is too slow.

**MVP slice:**

- Pre-built playbooks (SaaS inbound, agency inbound, SDR follow-ups, etc.) that set:
  - classification intent rules,
  - drafting style constraints,
  - safe-send gates.

**Dependencies:** packaging/versioning of config + prompts, easy import/export.

**Monetization:** add-on marketplace; onboarding bundle.

---

### 9) CRM “Close the Loop” (Sync + Outcome Tracking)

**Problem it solves:** Without outcomes (meetings booked, deals created), it’s hard to prove ROI.

**MVP slice:**

- Bi-directional sync for contacts/leads + activity logging.
- Track outcomes tied back to `correlation_id` (reply → meeting → pipeline).

**Dependencies:** Salesforce/HubSpot integrations, identity mapping, rate limits.

**Monetization:** higher tier; per-integration fee.

---

### 10) Multi-Client Agency Workspace (True Hierarchy)

**Problem it solves:** Agencies need client sub-workspaces with separation and reporting.

**MVP slice:**

- Agency tenant → client workspaces (scoped streams + scoped data).
- Cross-client reporting for the agency admin.

**Dependencies:** tenancy model upgrades, strict RLS, portal UX changes.

**Monetization:** agency plan priced by client workspaces + volume.

### Ideas Under Consideration

| Idea                    | Priority | Notes                                           |
| ----------------------- | -------- | ----------------------------------------------- |
| Calendar integration    | P3       | Auto-schedule meetings from replies             |
| CRM sync                | P3       | Bidirectional sync with Salesforce/HubSpot      |
| Email warmup            | P3       | Automated domain warmup sequences               |
| Predictive lead scoring | P3       | ML-based scoring model                          |
| Multi-language support  | P3       | Generate outreach in prospect's language        |
| Mobile app              | P4       | iOS/Android for notifications and quick actions |

---

## Feature Requests

Have an idea? We track feature requests in GitHub Issues with the `enhancement` label.

When submitting a feature request, please include:

1. **Problem:** What problem does this solve?
2. **Proposal:** How should it work?
3. **Alternatives:** What other approaches were considered?
4. **Impact:** Who benefits and how much?

---

## Deprecation Plans

### Planned Deprecations

| Component           | Deprecation Date | Removal Date | Replacement           |
| ------------------- | ---------------- | ------------ | --------------------- |
| Old harness config  | March 2026       | June 2026    | HarnessConfig class   |
| Legacy stream names | April 2026       | July 2026    | New naming convention |

We provide at least 3 months notice before removing deprecated features.
