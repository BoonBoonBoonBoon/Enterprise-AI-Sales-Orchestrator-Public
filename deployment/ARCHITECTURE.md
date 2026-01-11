# Observability Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AGENTIC SYSTEM - TIER 1 (Manager)                      │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐
│   Client/User Request    │
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MANAGER AGENT (Tier 1)                                   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    ObservabilityContext                                  │   │
│  │  ┌────────────────────────────────────────────────────────────────┐    │   │
│  │  │  1. Shortcut Check                                              │    │   │
│  │  │     - Pattern matching                                          │    │   │
│  │  │     - Cost: $0                                                  │    │   │
│  │  │     ✓ Log: path=shortcut, shortcut_type                        │    │   │
│  │  └────────────────────────────────────────────────────────────────┘    │   │
│  │                              ↓ (if no match)                            │   │
│  │  ┌────────────────────────────────────────────────────────────────┐    │   │
│  │  │  2. Deterministic Pipeline                                      │    │   │
│  │  │     - Normalize → Classify (rules) → Router                    │    │   │
│  │  │     - Optional LLM fallback                                     │    │   │
│  │  │     - Cost: ~$0.0002/exec (if LLM used)                        │    │   │
│  │  │     ✓ Log: intent, confidence, orchestrators, used_fallback    │    │   │
│  │  └────────────────────────────────────────────────────────────────┘    │   │
│  │                              ↓ (if uncertain)                           │   │
│  │  ┌────────────────────────────────────────────────────────────────┐    │   │
│  │  │  3. Deep Agent Fallback                                         │    │   │
│  │  │     - Full LLM reasoning (gpt-4o-mini)                         │    │   │
│  │  │     - Cost: ~$0.003/exec                                       │    │   │
│  │  │     ✓ Log: path=deep_agent, model                             │    │   │
│  │  └────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐    │   │
│  │  │  Observability Context Tracks:                                  │    │   │
│  │  │  • Latency (start → end)                                       │    │   │
│  │  │  • Cost per request                                            │    │   │
│  │  │  • Decision metadata                                           │    │   │
│  │  │  • Errors and exceptions                                       │    │   │
│  │  └────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  Emits to:                                                                       │
│  ├─ Structured JSON Logs (stdout)                                               │
│  ├─ Prometheus Metrics (/metrics:8000)                                          │
│  └─ Redis Audit Stream (manager:decisions:{tenant_id}:{date})                  │
└─────────────────────────────────────────────────────────────────────────────────┘
             │                    │                       │
             │                    │                       │
┌────────────▼──────────┐  ┌──────▼────────┐  ┌──────────▼─────────────┐
│   Promtail (scrape)   │  │  Prometheus   │  │    Redis Streams       │
│   Docker logs         │  │  HTTP scrape  │  │   Audit trail          │
└────────────┬──────────┘  └──────┬────────┘  └──────────┬─────────────┘
             │                    │                       │
             ▼                    ▼                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     GRAFANA STACK (Self-Hosted)                          │
│                                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │    Loki     │  │  Prometheus  │  │    Tempo     │  │   Grafana   │  │
│  │             │  │              │  │              │  │             │  │
│  │  Log Store  │  │ Metric Store │  │ Trace Store  │  │  Dashboard  │  │
│  │  7-day ret. │  │ 30-day ret.  │  │  (optional)  │  │   Builder   │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │
│         │                 │                 │                │           │
│         └─────────────────┴─────────────────┴────────────────┘           │
│                                  │                                       │
│                         ┌────────▼─────────┐                            │
│                         │  Grafana Query   │                            │
│                         │   Datasources    │                            │
│                         └────────┬─────────┘                            │
│                                  ▼                                       │
│                   ┌───────────────────────────────┐                     │
│                   │   Manager Dashboard (12 panels)│                     │
│                   │                                │                     │
│                   │  • Decision rate               │                     │
│                   │  • Latency p50/p95/p99        │                     │
│                   │  • Path distribution          │                     │
│                   │  • Intent classification      │                     │
│                   │  • Fallback usage             │                     │
│                   │  • Confidence scores          │                     │
│                   │  • Cost per tenant            │                     │
│                   │  • Error rate + alerts        │                     │
│                   │  • Recent logs                │                     │
│                   │  • Top tenants                │                     │
│                   │  • LLM usage                  │                     │
│                   │  • Health status              │                     │
│                   └───────────────────────────────┘                     │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────────┐
                   │   Engineer/Ops Dashboard    │
                   │   http://localhost:3000     │
                   │   admin / admin             │
                   └─────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════

DATA FLOW EXAMPLE:

1. Request arrives: "Send outreach to new leads"
   
2. Manager processes with ObservabilityContext:
   ```python
   with ObservabilityContext(tier="manager", ...) as obs:
       # Check shortcut (no match)
       # Normalize → classify by rules → route
       obs.log_decision(
           path="deterministic_pipeline",
           intent="outreach",
           confidence=0.92,
           orchestrators=["outreach_orchestrator"],
           used_fallback=False,
       )
       obs.track_cost(0.0)  # Rules only, no LLM
   ```

3. Observability emits:
   
   **Logs → Loki:**
   ```json
   {
     "timestamp": "2025-01-13T10:30:45.123Z",
     "level": "INFO",
     "event": "decision",
     "tier": "manager",
     "component": "manager_agent",
     "tenant_id": "acme_corp",
     "execution_id": "exec_1705145445.123",
     "path": "deterministic_pipeline",
     "intent": "outreach",
     "confidence": 0.92,
     "orchestrators": ["outreach_orchestrator"],
     "used_fallback": false,
     "latency_ms": 45.2,
     "cost_usd": 0.0
   }
   ```
   
   **Metrics → Prometheus:**
   ```
   manager_decisions_total{path="deterministic_pipeline",intent="outreach",tenant_id="acme_corp"} 1
   manager_latency_ms{path="deterministic_pipeline",tenant_id="acme_corp"} 45.2
   manager_cost_usd_total{tenant_id="acme_corp"} 0.0
   ```
   
   **Audit → Redis:**
   ```
   Stream: manager:decisions:acme_corp:2025-01-13
   Entry: {
     "execution_id": "exec_1705145445.123",
     "intent": "outreach",
     "confidence": 0.92,
     "path": "deterministic_pipeline",
     "timestamp": "2025-01-13T10:30:45.123Z"
   }
   ```

4. Dashboard updates in real-time:
   - Decision rate: +1
   - Latency p95: 45ms
   - Path: deterministic (green)
   - Cost: $0 (no LLM)
   - Intent: outreach +1

═══════════════════════════════════════════════════════════════════════════════

COST BREAKDOWN:

┌──────────────────────────────────────────────────────────────────────────┐
│  Path                │  Frequency │  Cost/exec  │  Monthly Cost           │
├──────────────────────┼────────────┼─────────────┼─────────────────────────┤
│  Shortcuts           │    40%     │   $0        │  $0                     │
│  Deterministic Only  │    30%     │   $0        │  $0                     │
│  Deterministic+LLM   │    25%     │   $0.0002   │  ~$4                    │
│  Deep Agent          │     5%     │   $0.003    │  ~$3                    │
├──────────────────────┴────────────┴─────────────┼─────────────────────────┤
│  TOTAL (10K requests/month)                      │  ~$7                    │
└──────────────────────────────────────────────────┴─────────────────────────┘

Add Observability Infrastructure:
  • Grafana Stack (self-hosted)     : $0.30/month
  • Alternative (DataDog)            : $100-300/month
  • SAVINGS                          : 95%+

═══════════════════════════════════════════════════════════════════════════════

MONITORING QUERIES:

Prometheus (Metrics):
  # Total decisions
  sum(rate(manager_decisions_total[5m]))
  
  # P95 latency
  histogram_quantile(0.95, rate(manager_latency_ms_bucket[5m]))
  
  # Cost by tenant
  sum by (tenant_id) (manager_cost_usd_total)
  
  # Error rate
  rate(manager_decisions_total{success="false"}[5m])

Loki (Logs):
  # All decisions
  {component="manager_agent"} | json | event="decision"
  
  # High confidence only
  {component="manager_agent"} | json | confidence > 0.8
  
  # LLM fallbacks
  {component="manager_agent"} | json | used_fallback="true"
  
  # Specific tenant
  {tenant_id="acme_corp"}

Redis (Audit):
  # Recent decisions for tenant
  XREAD STREAMS manager:decisions:acme_corp:2025-01-13 0
  
  # Stream info
  XINFO STREAM manager:decisions:acme_corp:2025-01-13

═══════════════════════════════════════════════════════════════════════════════
