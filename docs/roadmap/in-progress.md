# In Progress

Components and features currently under active development.

## Tier 2 Orchestrators

### Inbound Orchestrator

**Status:** ✅ Active (Jan 2026)  
**Path:** `tiers/tier_2/inbound_orchestrator/`  
**Target:** Complete

The Inbound Orchestrator handles inbound email triage and routing, ensuring automated/low-value messages do not consume downstream resources.

**Implemented Functionality:**

- Tier-0 header-based pre-filter (skip obvious bounces)
- Tier-3 Classifier Agent integration (rules-first, optional LLM fallback)
- Action routing: route-to-leads vs store-only vs drop
- Propagates classification metadata downstream

**Current State:**

- [x] Folder structure created
- [x] README with design
- [x] Consumer implementation
- [x] Classifier integration
- [x] Routing logic
- [x] Tests (targeted unit/integration coverage)

---

### Audit Orchestrator

**Status:** 📋 Skeleton  
**Path:** `tiers/tier_2/audit_orchestrator/`  
**Target:** Q1 2026

The Audit Orchestrator monitors system activity for compliance and quality.

**Planned Functionality:**

- Audit outbound messages for compliance
- Track quality metrics
- Flag anomalies for review
- Generate compliance reports

---

### Control Orchestrator

**Status:** 📋 Skeleton  
**Path:** `tiers/tier_2/control_orchestrator/`  
**Target:** Q1 2026

The Control Orchestrator handles system configuration and control commands.

**Planned Functionality:**

- Pause/resume campaigns
- Update system configuration
- Rate limit management
- Feature flag control

---

## Tier 3 Agents

### Scheduler Agent

**Status:** 🚧 In Progress  
**Path:** `tiers/tier_3/scheduler_agent/`  
**Target:** February 2026

The Scheduler Agent manages delayed and scheduled task execution.

**Planned Functionality:**

- Schedule emails for future sending
- Implement send windows (business hours only)
- Manage follow-up sequences with delays
- Handle timezone-aware scheduling

**Current State:**

- [x] Folder structure created
- [ ] Core scheduling logic
- [ ] Redis-based delay queue
- [ ] Timezone handling
- [ ] Consumer implementation
- [ ] Tests

---

### Channel Sequencer Agent

**Status:** 🚧 In Progress  
**Path:** `tiers/tier_3/channel_sequencer_agent/`  
**Target:** Q1 2026

The Channel Sequencer manages outbound sequencing and delivery execution.

**Implemented Functionality (MVP-safe outbound):**

- Approval-mode drafts (no-send)
- Hard-stop rules (never-send)
- Redis-based throttles (hourly + new threads/day)
- Outbound persistence enqueue (conversation + message) for audit/history

**Planned Functionality:**

- Coordinate email → LinkedIn → phone sequences
- Track channel-specific rate limits
- Manage fallback when channel fails
- Optimize channel selection based on engagement

---

## Infrastructure

### Observability Integration

**Status:** 🚧 In Progress  
**Target:** February 2026

Full observability stack integration.

**Planned:**

- [x] OpenTelemetry tracing setup
- [x] Datadog exporter
- [ ] Prometheus metrics
- [ ] Grafana dashboards
- [ ] Alerting rules
- [ ] Loki log aggregation

---

### Production Deployment

**Status:** 🚧 In Progress  
**Target:** February 2026

Production-ready deployment configuration.

**Planned:**

- [x] Docker Compose for development
- [ ] Kubernetes manifests
- [ ] Helm charts
- [ ] CI/CD pipeline
- [ ] Secrets management (Azure KeyVault / AWS Secrets Manager)
- [ ] Auto-scaling configuration

---

## Documentation

### This Documentation Overhaul

**Status:** 🚧 In Progress  
**Target:** January 2026

Restructured MkDocs documentation you're reading now.

**Planned:**

- [x] New folder structure
- [x] Landing pages for each section
- [x] ADR section
- [x] Roadmap section
- [ ] Complete component documentation
- [ ] Reference documentation
- [ ] Guide completion

---

## How to Contribute

Interested in helping with any of these?

1. Check the component's README for design decisions
2. Look at similar completed components for patterns
3. Start with tests (TDD approach)
4. Submit PR with clear description

Priority items seeking contributors:

- Scheduler Agent implementation
- Kubernetes manifests
- Dashboard templates
