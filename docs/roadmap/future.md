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
