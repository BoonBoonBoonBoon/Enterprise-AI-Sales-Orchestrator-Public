# Redis Stream Data Flow - Visual Reference

**Version**: 2.0  
**Date**: November 22, 2025

---

## Complete System Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                                   │
│                     (API, Webhooks, User Interface)                          │
└────────────────────────────┬────────────────────────────────────────────────┘
                             │ POST /api/campaigns
                             │ {"goal": "Find leads..."}
                             ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                                TIER 1                                        │
│                              MANAGER                                         │
│                        (Strategic Decision)                                  │
│                                                                              │
│  Stream: {tenant}:manager:tasks                                             │
│  └─ Consumer Group: manager-workers                                         │
│      └─ Manager Deep Agent                                                  │
│          ├─ Analyzes user goal                                              │
│          ├─ Classifies intent (lead_enrichment, outreach, etc.)            │
│          └─ Delegates to appropriate orchestrators                          │
│                                                                              │
│  Results: {tenant}:manager:results                                          │
│  └─ Final aggregated results sent to external systems                       │
└──────────────┬────────────────────────┬─────────────────────────────────────┘
               │                        │
               │ Delegation             │ Delegation
               │ (Downstream)           │ (Downstream)
               ↓                        ↓
┌──────────────────────────┐  ┌──────────────────────────┐
│      TIER 2 - LEADS      │  │    TIER 2 - OUTREACH     │
│   (Business Logic)       │  │    (Business Logic)      │
│                          │  │                          │
│  {tenant}:leads:tasks    │  │  {tenant}:outreach:tasks │
│  └─ Consumer Group:      │  │  └─ Consumer Group:      │
│     leads-workers        │  │     outreach-workers     │
│      └─ Leads Deep Agent │  │      └─ Outreach Agent   │
│                          │  │                          │
│  Responsibilities:       │  │  Responsibilities:       │
│  • Lead discovery        │  │  • Campaign creation     │
│  • Data validation       │  │  • Multi-channel coord   │
│  • Database mgmt         │  │  • Timing optimization   │
│  • Enrichment            │  │  • Content generation    │
│                          │  │                          │
│  {tenant}:leads:results  │  │  {tenant}:outreach:      │
│  └─ Aggregates results   │  │      results             │
│     from agents          │  │  └─ Aggregates results   │
└───┬───┬────────┬────┬───┘  └───┬────┬───────┬─────────┘
    │   │        │    │          │    │       │
    │   │        │    │          │    │       │
    │   │        │    │          │    │       │
    ↓   ↓        ↓    ↓          ↓    ↓       ↓
┌───────────────────────────────────────────────────────────────────────────┐
│                               TIER 3                                       │
│                        OPERATIONAL AGENTS                                  │
│                      (Specialized Execution)                               │
│                                                                            │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────────┐                │
│  │  RAG AGENT    │  │ PERSISTENCE  │  │ DEDUPLICATION  │                │
│  │               │  │    AGENT     │  │     AGENT      │                │
│  │ {tenant}:     │  │              │  │                │                │
│  │  agents:rag:  │  │ {tenant}:    │  │ {tenant}:      │                │
│  │  tasks        │  │  agents:     │  │  agents:       │                │
│  │               │  │  persistence:│  │  deduplication:│                │
│  │ Consumer:     │  │  tasks       │  │  tasks         │                │
│  │ rag-workers   │  │              │  │                │                │
│  │               │  │ Consumer:    │  │ Consumer:      │                │
│  │ Purpose:      │  │ persistence- │  │ deduplication- │                │
│  │ • Vector DB   │  │  workers     │  │  workers       │                │
│  │ • External    │  │              │  │                │                │
│  │   API calls   │  │ Purpose:     │  │ Purpose:       │                │
│  │ • Data        │  │ • Bulk DB    │  │ • Fuzzy match  │                │
│  │   enrichment  │  │   writes     │  │ • Duplicates   │                │
│  │               │  │ • Transaction│  │ • Merge logic  │                │
│  │ {tenant}:     │  │ • Read ops   │  │                │                │
│  │  agents:rag:  │  │              │  │ {tenant}:      │                │
│  │  results      │  │ {tenant}:    │  │  agents:       │                │
│  └───────┬───────┘  │  agents:     │  │  deduplication:│                │
│          │          │  persistence:│  │  results       │                │
│          │          │  results     │  │                │                │
│          │          └───────┬──────┘  └───────┬────────┘                │
│          │                  │                 │                          │
│          └──────────────────┴─────────────────┘                          │
│                             │ (Upstream)                                 │
│                             │ Results flow back to Leads                 │
│                             ↓                                            │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────────┐                │
│  │ COPYWRITER    │  │   BOOKING    │  │  SEQUENCING    │                │
│  │    AGENT      │  │    AGENT     │  │     AGENT      │                │
│  │               │  │              │  │                │                │
│  │ {tenant}:     │  │ {tenant}:    │  │ {tenant}:      │                │
│  │  agents:      │  │  agents:     │  │  agents:       │                │
│  │  copywriter:  │  │  booking:    │  │  sequencing:   │                │
│  │  tasks        │  │  tasks       │  │  tasks         │                │
│  │               │  │              │  │                │                │
│  │ Consumer:     │  │ Consumer:    │  │ Consumer:      │                │
│  │ copywriter-   │  │ booking-     │  │ sequencing-    │                │
│  │  workers      │  │  workers     │  │  workers       │                │
│  │               │  │              │  │                │                │
│  │ Purpose:      │  │ Purpose:     │  │ Purpose:       │                │
│  │ • Email gen   │  │ • Calendar   │  │ • ML timing    │                │
│  │ • LinkedIn    │  │ • Scheduling │  │ • Send optim   │                │
│  │ • A/B testing │  │ • Availability│ │ • Best times   │                │
│  │ • Templates   │  │ • Invites    │  │ • Cadence      │                │
│  │               │  │              │  │                │                │
│  │ {tenant}:     │  │ {tenant}:    │  │ {tenant}:      │                │
│  │  agents:      │  │  agents:     │  │  agents:       │                │
│  │  copywriter:  │  │  booking:    │  │  sequencing:   │                │
│  │  results      │  │  results     │  │  results       │                │
│  └───────┬───────┘  └───────┬──────┘  └───────┬────────┘                │
│          │                  │                 │                          │
│          └──────────────────┴─────────────────┘                          │
│                             │ (Upstream)                                 │
│                             │ Results flow back to Outreach              │
└─────────────────────────────┴────────────────────────────────────────────┘
                              │
                              │ Results aggregation (Upstream)
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATORS AGGREGATE                            │
│                                                                              │
│  {tenant}:leads:results ──┐                                                 │
│                           ├──> {tenant}:manager:results                     │
│  {tenant}:outreach:results┘                                                 │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              │ Final result (Upstream)
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MANAGER COMPILES FINAL RESULT                      │
│                                                                              │
│  {tenant}:manager:results                                                   │
│  └─ Aggregates all orchestrator results                                    │
│     └─ Formats response for external systems                                │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              │ API Response
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                                   │
│                     (API Response, Webhooks, UI)                            │
│                                                                              │
│  GET /api/results/{task_id}                                                 │
│  Returns: {                                                                 │
│    "status": "completed",                                                   │
│    "leads_found": 102,                                                      │
│    "campaign_created": "camp-789",                                          │
│    "touchpoints_scheduled": 356                                             │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## System-Wide Observability Streams

All components publish to these system streams:

```
┌────────────────────────────────────────────────────────────────────┐
│                      SYSTEM STREAMS                                 │
│                 (Cross-cutting Concerns)                            │
│                                                                     │
│  {tenant}:system:dlq                                               │
│  └─ Dead Letter Queue                                              │
│     └─ Failed messages from any component                          │
│        └─ Consumer Group: dlq-handlers (for retry/inspection)      │
│                                                                     │
│  {tenant}:system:events                                            │
│  └─ System-wide events                                             │
│     └─ State changes, errors, warnings                             │
│        └─ Consumer Group: event-processors                         │
│                                                                     │
│  {tenant}:system:health                                            │
│  └─ Health monitoring                                              │
│     └─ Heartbeat messages from all components                      │
│        └─ Consumer Group: health-monitors                          │
│                                                                     │
│  {tenant}:system:audit                                             │
│  └─ Audit trail (compliance)                                       │
│     └─ Important actions, data access                              │
│        └─ Consumer Group: audit-processors                         │
│        └─ Retention: 30 days                                       │
│                                                                     │
│  {tenant}:system:metrics                                           │
│  └─ Performance metrics                                            │
│     └─ Latency, throughput, errors                                 │
│        └─ Consumer Group: metrics-collectors                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Stream Naming Pattern Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     NAMING PATTERNS                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TIER 1 - MANAGER                                               │
│  ├─ {tenant}:manager:tasks                                      │
│  └─ {tenant}:manager:results                                    │
│                                                                  │
│  TIER 2 - ORCHESTRATORS                                         │
│  ├─ {tenant}:leads:tasks                                        │
│  ├─ {tenant}:leads:results                                      │
│  ├─ {tenant}:outreach:tasks                                     │
│  └─ {tenant}:outreach:results                                   │
│                                                                  │
│  TIER 3 - AGENTS                                                │
│  ├─ {tenant}:agents:rag:tasks                                   │
│  ├─ {tenant}:agents:rag:results                                 │
│  ├─ {tenant}:agents:persistence:tasks                           │
│  ├─ {tenant}:agents:persistence:results                         │
│  ├─ {tenant}:agents:copywriter:tasks                            │
│  ├─ {tenant}:agents:copywriter:results                          │
│  ├─ {tenant}:agents:booking:tasks                               │
│  ├─ {tenant}:agents:booking:results                             │
│  ├─ {tenant}:agents:sequencing:tasks                            │
│  ├─ {tenant}:agents:sequencing:results                          │
│  ├─ {tenant}:agents:deduplication:tasks                         │
│  └─ {tenant}:agents:deduplication:results                       │
│                                                                  │
│  SYSTEM                                                          │
│  ├─ {tenant}:system:dlq                                         │
│  ├─ {tenant}:system:events                                      │
│  ├─ {tenant}:system:health                                      │
│  ├─ {tenant}:system:audit                                       │
│  └─ {tenant}:system:metrics                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Message Flow Example - End-to-End

### Request: "Find 100 AI startups in SF and create email campaign"

```
┌─ STEP 1: External Request
│  POST /api/campaigns
│  {"goal": "Find 100 AI startups in SF and create email campaign"}
│
├─ STEP 2: Manager Receives
│  Stream: agentic-dev:manager:tasks
│  Manager Agent Decision:
│    "This requires both lead discovery AND outreach"
│    "Delegate to BOTH orchestrators"
│
├─ STEP 3: Parallel Delegation
│  ├─> agentic-dev:leads:tasks
│  │   {"goal": "Find 100 AI startups in SF"}
│  │
│  └─> agentic-dev:outreach:tasks
│      {"goal": "Create campaign", "depends_on": "leads_task_id"}
│
├─ STEP 4: Leads Orchestrator Processes
│  Leads Agent Decision:
│    "Query database for existing startups"
│    "Found 42, need 58 more"
│    "Delegate to RAG for external enrichment"
│  
│  ├─> agentic-dev:agents:rag:tasks
│      {"query": "Find 58 more AI startups in SF"}
│
├─ STEP 5: RAG Agent Executes
│  RAG Agent Actions:
│    • Queries Crunchbase API
│    • Queries LinkedIn API
│    • Returns 60 enriched leads
│  
│  └─> agentic-dev:agents:rag:results
│      {"leads": [...60 enriched leads...]}
│
├─ STEP 6: Leads Aggregates Results
│  Leads Orchestrator:
│    • Combines 42 existing + 60 new = 102 leads
│    • Deduplicates (if needed)
│    • Validates data quality
│  
│  └─> agentic-dev:leads:results
│      {"leads_found": 102, "leads": [...]}
│
├─ STEP 7: Outreach Orchestrator Processes
│  (Waits for leads task to complete)
│  
│  Outreach Agent Decision:
│    "Need personalized emails for 102 leads"
│    "Delegate to Copywriter agent"
│  
│  ├─> agentic-dev:agents:copywriter:tasks
│      {"leads": [...102 leads...], "template": "ai_startup_intro"}
│
├─ STEP 8: Copywriter Generates Content
│  Copywriter Agent Actions:
│    • Generates 102 personalized emails
│    • Uses lead data for customization
│    • A/B tests variants
│  
│  └─> agentic-dev:agents:copywriter:results
│      {"emails": [...102 emails...]}
│
├─ STEP 9: Outreach Aggregates Campaign
│  Outreach Orchestrator:
│    • Creates campaign with 4-touch sequence
│    • Schedules touchpoints
│    • Optimizes send times
│  
│  └─> agentic-dev:outreach:results
│      {"campaign_id": "camp-789", "touchpoints": 356}
│
├─ STEP 10: Manager Compiles Final Result
│  Manager Agent:
│    • Waits for both orchestrators
│    • Aggregates results
│    • Formats response
│  
│  └─> agentic-dev:manager:results
│      {
│        "status": "completed",
│        "leads_found": 102,
│        "campaign_created": "camp-789",
│        "touchpoints_scheduled": 356,
│        "estimated_completion": "2025-11-30"
│      }
│
└─ STEP 11: External Response
   GET /api/results/task_12345
   Returns complete campaign data
```

---

## Consumer Group Pattern

Every task stream has a consumer group for horizontal scaling:

```
Stream: {tenant}:agents:rag:tasks
Consumer Group: rag-workers
  ├─ Consumer: rag-worker-12345 (Instance 1)
  ├─ Consumer: rag-worker-67890 (Instance 2)
  └─ Consumer: rag-worker-24680 (Instance 3)

Message Distribution:
  Message 1 → rag-worker-12345
  Message 2 → rag-worker-67890  ← Load balanced
  Message 3 → rag-worker-24680
  Message 4 → rag-worker-12345
  ...
```

---

## Key Concepts

### Downstream = Task Delegation
When a component sends work DOWN to a lower tier:
```
Manager → Leads = Downstream
Leads → RAG = Downstream
```

### Upstream = Result Propagation  
When a component sends results UP to a higher tier:
```
RAG → Leads = Upstream
Leads → Manager = Upstream
```

### Stream Types
- **tasks**: Input stream (receives work)
- **results**: Output stream (publishes results)

### Consumer Groups
Enable horizontal scaling - multiple workers can consume from same stream.

---

**For complete details, see**: `docs/architecture/services/REDIS_ARCHITECTURE.md`
