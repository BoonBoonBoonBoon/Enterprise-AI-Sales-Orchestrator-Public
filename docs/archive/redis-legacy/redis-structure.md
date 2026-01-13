how Redis can back your whole system: manager â†’ orchestrator â†’ low-level agents â†’ health â†’ auditing. I also included a ready-to-commit doc you can drop into the repo.

High-level flows

- Command path
  - Campaign Manager publishes a command (cm:commands).
  - Orchestrator consumes commands, expands into tasks (orchestrator:tasks).
  - Orchestrator routes tasks to the right worker streams (rag:tasks, persist:tasks).
- Worker paths
  - RAG workers consume rag:tasks â†’ publish rag:results.
  - Persist workers consume persist:tasks â†’ write DB â†’ publish persist:results.
- Observability
  - Every step emits audit events (audit:events) and tracing spans (audit:spans).
  - Services heartbeat via ops:hb:{service}:{id} and emit health changes to ops:health.
  - DLQ captures hard failures (persist:dlq, rag:dlq).

Keyspace layout (namespaced)

- agentic-dev:cm:commands (STREAM) group=cm-managers
- agentic-dev:cm:events (STREAM) group=cm-subscribers
- agentic-dev:orchestrator:commands (STREAM) group=orchestrators
- agentic-dev:orchestrator:tasks (STREAM) group=orchestrators
- agentic-dev:orchestrator:results (STREAM) no group
- agentic-dev:rag:tasks (STREAM) group=rag-workers
- agentic-dev:rag:results (STREAM) no group
- agentic-dev:persist:tasks (STREAM) group=persist-writers
- agentic-dev:persist:results (STREAM) no group
- agentic-dev:persist:dlq (STREAM) group=dlq-readers
- agentic-dev:audit:events (STREAM) group=auditors
- agentic-dev:audit:spans (STREAM) group=auditors
- agentic-dev:ops:health (STREAM) group=ops
- agentic-dev:ops:hb:{service}:{id} (STRING) TTL=30s
- agentic-dev:ops:stats:{service}:m:{yyyymmddhhmm} (HASH) rolling counters
- agentic-dev:locks:idemp:{stream}:{msg_id} (STRING) TTL for idempotency
- agentic-dev:cache:rag:chunks:{doc_id} (HASH) optional RAG cache with TTL

Message shapes (examples)

- cm:commands
  - { type: "start_campaign", campaign_id, params, req_id, ts }
- orchestrator:tasks
  - { type: "fanout", items: [...], req_id, ts }
- rag:tasks
  - { query, k: 8, req_id, ts }
- rag:results
  - { ok: true, hits: [...], req_id, ts, worker }
- persist:tasks
  - { op: "upsert", table: "leads", row: {...}, on_conflict: ["email"], req_id, ts }
- persist:results
  - { ok: true, id, req_id, ts, worker }
- audit:events
  - { event: "task_accepted", stream, msg_id, worker, req_id, ts }
- ops:health
  - { service: "rag_worker", id, status: "up", ts }

Ops conventions

- Consumer groups
  - cm-managers, orchestrators, rag-workers, persist-writers, auditors, ops
- Trimming
  - Streams use MAXLEN ~ 20kâ€“100k depending on volume (prevent unbounded growth).
- Idempotency
  - SETNX agentic-dev:locks:idemp:{stream}:{msg_id} with TTL to dedupe replays.
- Heartbeats
  - SETEX agentic-dev:ops:hb:{service}:{id} 30 "1" every 10â€“15s. Health page reads keys with TTL > 0.
- DLQ
  - On final failure: XADD agentic-dev:persist:dlq with error context; alert from there.

CLI/health youâ€™ll use often

- XINFO STREAM agentic-dev:persist:tasks
- XINFO GROUPS agentic-dev:rag:tasks
- XPENDING agentic-dev:rag:tasks rag-workers
- XRANGE agentic-dev:audit:events - + COUNT 5
- GET agentic-dev:ops:hb:rag_worker:{id}

Drop-in documentation file

````markdown
# Redis Topology (Streams-first)

Namespace: `agentic-dev` (from REDIS_NAMESPACE)

## Streams and Groups

- cm (Campaign Manager)

  - `agentic-dev:cm:commands` (STREAM) â€” group=`cm-managers`
  - `agentic-dev:cm:events` (STREAM) â€” group=`cm-subscribers`

- orchestrator

  - `agentic-dev:orchestrator:commands` (STREAM) â€” group=`orchestrators`
  - `agentic-dev:orchestrator:tasks` (STREAM) â€” group=`orchestrators`
  - `agentic-dev:orchestrator:results` (STREAM) â€” no group

- RAG workers

  - `agentic-dev:rag:tasks` (STREAM) â€” group=`rag-workers`
  - `agentic-dev:rag:results` (STREAM) â€” no group
  - Cache (optional): `agentic-dev:cache:rag:chunks:{doc_id}` (HASH, TTL)

- Persistence workers

  - `agentic-dev:persist:tasks` (STREAM) â€” group=`persist-writers`
  - `agentic-dev:persist:results` (STREAM) â€” no group
  - DLQ: `agentic-dev:persist:dlq` (STREAM) â€” group=`dlq-readers`

- Audit and tracing

  - `agentic-dev:audit:events` (STREAM) â€” group=`auditors`
  - `agentic-dev:audit:spans` (STREAM) â€” group=`auditors`

- Operations

  - `agentic-dev:ops:health` (STREAM) â€” group=`ops`
  - `agentic-dev:ops:hb:{service}:{id}` (STRING, TTL=30s)
  - `agentic-dev:ops:stats:{service}:m:{yyyymmddhhmm}` (HASH)

- Idempotency / locks
  - `agentic-dev:locks:idemp:{stream}:{msg_id}` (STRING, TTL)

## End-to-end flow

1. Campaign Manager â†’ `cm:commands`
2. Orchestrator consumes, emits `orchestrator:tasks` and routes to:
   - RAG: `rag:tasks`
   - Persistence: `persist:tasks`
3. Workers process and emit results:
   - RAG â†’ `rag:results`
   - Persistence â†’ `persist:results`
4. Audit logs for each step â†’ `audit:events`, spans â†’ `audit:spans`
5. Health:
   - Workers heartbeat `ops:hb:{service}:{id}`
   - State changes â†’ `ops:health`
6. Failures:
   - Retries with backoff; final failures â†’ `persist:dlq` (and optionally `rag:dlq`)

## Message envelopes (examples)

- `persist:tasks`

```json
{"op":"upsert","table":"leads","row":{...},"on_conflict":["email"],"req_id":"uuid","ts":1739700000}
```

- `rag:tasks`

```json
{
  "query": "lead emails for client X",
  "k": 8,
  "req_id": "uuid",
  "ts": 1739700000
}
```

- `audit:events`

```json
{
  "event": "task_acked",
  "stream": "persist:tasks",
  "msg_id": "176080...-0",
  "worker": "writer-1",
  "req_id": "uuid",
  "ts": 1739700001
}
```

## Operational guidance

- Trimming: set MAXLEN on high-volume streams (`STREAM_MAXLEN=20000`).
- Groups:
  - Create with `SETID $` for fresh runs; use `0-0` to replay.
- Idempotency:
  - Before processing, `SETNX locks:idemp:{stream}:{msg_id} = 1` with short TTL.
- Heartbeats:
  - `SETEX ops:hb:{service}:{id} 30 1` every 10â€“15s; UI shows keys with TTL>0.
- DLQ handling:
  - Alert on new entries; provide requeue tooling (`XAUTOCLAIM` + enqueue).

## Quick health checks

- `XINFO GROUPS agentic-dev:persist:tasks`
- `XPENDING agentic-dev:rag:tasks rag-workers`
- `XINFO STREAM agentic-dev:audit:events`
- `KEYS agentic-dev:ops:hb:*`
````

---

# ðŸ—ï¸ Complete Agentic System Architecture Explained

## Overview

You have a **three-tier agentic orchestration system** built on Redis Streams that enables AI agents to coordinate complex multi-step workflows. Think of it as a "brain hierarchy" where strategic decisions cascade down to tactical execution.

---

## ðŸŽ¯ The Three Tiers

### **Tier 1: Manager Agent** (Strategic Orchestrator)

**Role:** Entry point for all external requests. Makes high-level decisions about which orchestrators to use.

**Streams:**

- `agentic-dev:manager:tasks` â† External requests arrive here
- `agentic-dev:manager:results` â†’ Final results published here

**What it does:**

```
External Request: "Find 50 AI startups and create outreach campaign"
    â†“
Manager analyzes goal
    â†“
Manager decides: "This needs BOTH leads discovery AND outreach"
    â†“
Delegates to Tier 2:
    â”œâ”€ XADD agentic-dev:leads:tasks (find leads)
    â””â”€ XADD agentic-dev:outreach:tasks (create campaign)
```

**Configuration:**

- 2 retries (strategic level, rarely fails)
- 120s timeout (coordination takes time)
- Checkpointing enabled (multi-step workflows)
- 2000 req/hr quota

---

### **Tier 2: Orchestrators** (Business Logic)

#### **2A: Leads Orchestrator**

**Role:** Discovers, validates, and manages leads database

**Streams:**

- `agentic-dev:leads:tasks` â† Receives delegations from Manager
- `agentic-dev:leads:results` â†’ Publishes results back

**8 Tools:**

**Deterministic (Fast, Direct):**

1. `validate_lead` - Check email format, required fields (<5ms)
2. `write_lead` - Save single lead to database (50-100ms)
3. `update_lead` - Modify lead fields (50-100ms)
4. `query_leads` - Search leads by filters (50-500ms)
5. `move_lead_stage` - Change pipeline stage (50-100ms)

**Delegation (Complex, Subagent):** 6. `delegate_to_rag_agent` - Enrich lead with external data (2-5s) 7. `delegate_to_persistence_agent` - Bulk import 100+ leads (5-30s) 8. `delegate_to_deduplication_agent` - Find duplicates (3-10s)

**Example Flow:**

```
Manager delegates: "Find tech leads in SF"
    â†“
Leads Orchestrator receives task
    â†“
Decides: "Query database for tech companies in SF"
    â†“
Uses query_leads tool
    â†“
Returns 50 leads to Manager
```

**Configuration:**

- 3 retries
- 60s timeout
- No checkpointing (fast operations)
- 1000 req/hr quota

---

#### **2B: Outreach Orchestrator**

**Role:** Coordinates multi-channel outreach campaigns

**Streams:**

- `agentic-dev:outreach:tasks` â† Receives delegations from Manager
- `agentic-dev:outreach:results` â†’ Publishes results back

**8 Tools:**

**Deterministic:**

1. `validate_campaign` - Check campaign data, prevent spam
2. `create_touchpoint` - Create single outreach touchpoint
3. `schedule_touchpoint` - Schedule touchpoint for future
4. `query_campaign_metrics` - Get campaign performance stats
5. `update_campaign_status` - Change campaign status

**Delegation:** 6. `delegate_to_copywriter` - Generate email copy (3-8s) 7. `delegate_to_booking` - Schedule meetings (5-15s) 8. `delegate_to_sequencing` - Optimize send timing with ML (10-30s)

**Multi-Channel Strategy:**

```
Email (Day 0) â†’ LinkedIn (Day 3) â†’ Phone (Day 7) â†’ Follow-up (Day 10)
```

**Example Flow:**

```
Manager delegates: "Create campaign for 50 leads"
    â†“
Outreach Orchestrator receives task
    â†“
Decides: "Need email copy, then schedule sequence"
    â†“
Step 1: Delegates to Copywriter (generate emails)
    â†“
Step 2: Uses schedule_touchpoint (Day 0, Day 3, Day 7)
    â†“
Returns campaign plan to Manager
```

**Configuration:**

- 5 retries (external APIs can fail)
- 120s timeout (copy generation takes time)
- Checkpointing enabled (long campaigns)
- 500 req/hr quota (respect external rate limits)

---

### **Tier 3: Operational Agents** (Specialized Capabilities)

These are called by Tier 2 orchestrators for specific tasks.

**Streams (6 agents, TO BE BUILT):**

- `agentic-dev:copywriter:tasks/results` - Email/content generation
- `agentic-dev:booking:tasks/results` - Calendar/meeting scheduling
- `agentic-dev:sequencing:tasks/results` - ML-based send optimization
- `agentic-dev:rag:tasks/results` - Vector search enrichment
- `agentic-dev:persistence:tasks/results` - Bulk data operations
- `agentic-dev:deduplication:tasks/results` - Fuzzy matching/merging

---

## ðŸ”„ Complete Flow Example

**User Request:** "Find 100 tech leads in SF and create email campaign"

```
1. EXTERNAL API
   POST /api/campaigns
   {
       "goal": "Find 100 tech leads in SF and create email campaign",
       "filters": {"industry": "tech", "location": "SF"}
   }
   â†“

2. TIER 1: MANAGER (Strategic Decision)
   Receives: agentic-dev:manager:tasks
   Manager Deep Agent analyzes:
   - "This requires lead discovery AND outreach"
   - "First find leads, then create campaign"

   Publishes to:
   â”œâ”€ agentic-dev:leads:tasks
   â”‚  {"goal": "Find 100 tech leads in SF", "task_id": "abc-123"}
   â””â”€ agentic-dev:outreach:tasks
      {"goal": "Create campaign", "depends_on": "abc-123"}
   â†“

3. TIER 2A: LEADS ORCHESTRATOR (Lead Discovery)
   Reads: agentic-dev:leads:tasks
   Leads Deep Agent decides:
   - "Use query_leads tool for tech companies in SF"
   - "Found 42 leads, need 58 more"
   - "Delegate to RAG agent to enrich from external sources"

   Publishes to:
   â””â”€ agentic-dev:rag:tasks
      {"goal": "Find 58 more tech leads in SF", "task_id": "abc-123-rag"}

   RAG Agent (Tier 3):
   - Queries Crunchbase, LinkedIn APIs
   - Returns 60 enriched leads

   Leads publishes result:
   â””â”€ agentic-dev:leads:results
      {"task_id": "abc-123", "leads": [...102 leads...], "status": "completed"}
   â†“

4. TIER 2B: OUTREACH ORCHESTRATOR (Campaign Creation)
   Reads: agentic-dev:outreach:tasks
   Waits for dependency abc-123 to complete
   Outreach Deep Agent decides:
   - "Create 4-touchpoint sequence"
   - "Need email copy for 102 leads"
   - "Delegate to Copywriter for personalized emails"

   Publishes to:
   â”œâ”€ agentic-dev:copywriter:tasks
   â”‚  {"goal": "Generate 102 personalized emails", "leads": [...]}
   â””â”€ agentic-dev:booking:tasks
      {"goal": "Check availability for 102 meetings"}

   Copywriter Agent (Tier 3):
   - Generates 102 personalized emails
   - Uses lead data for customization

   Booking Agent (Tier 3):
   - Checks calendar availability
   - Suggests meeting times

   Outreach publishes result:
   â””â”€ agentic-dev:outreach:results
      {
          "task_id": "abc-456",
          "campaign_id": "camp-789",
          "touchpoints": [
              {"channel": "email", "day": 0, "count": 102},
              {"channel": "linkedin", "day": 3, "count": 102},
              {"channel": "phone", "day": 7, "count": 50},
              {"channel": "email_followup", "day": 10, "count": 102}
          ],
          "status": "scheduled"
      }
   â†“

5. TIER 1: MANAGER (Result Aggregation)
   Manager waits for both results:
   âœ… agentic-dev:leads:results (102 leads found)
   âœ… agentic-dev:outreach:results (campaign created)

   Publishes final result:
   â””â”€ agentic-dev:manager:results
      {
          "task_id": "master-001",
          "status": "completed",
          "leads_found": 102,
          "campaign_created": "camp-789",
          "touchpoints_scheduled": 356,
          "estimated_completion": "2025-11-20"
      }
   â†“

6. EXTERNAL API RESPONSE
   GET /api/results/master-001
   Returns complete campaign data
```

---

## ðŸ›¡ï¸ Agent Harness (Layer 1: Reliability)

Every agent is wrapped with a **universal harness** that provides production features:

### **Features:**

**1. Retry Logic** (3 strategies available):

- Exponential Backoff (default for LLM APIs)
- Linear Backoff (database locks)
- Jittered Backoff (production, prevents thundering herd)

**2. Observability** (3 backends):

- Simple Logging (development, no dependencies)
- OpenTelemetry (CNCF standard, vendor-agnostic)
- Datadog (production APM)

**3. Checkpointing** (3 backends):

- Redis (fast, 24h TTL)
- S3 (persistent audit trails, 30d+)
- PostgreSQL (queryable analytics)

**4. Quota Management** (2 implementations):

- Redis Token Bucket (distributed with Lua script)
- In-Memory (development, time-window based)

**5. Health Checks:**

- Component status monitoring
- Graceful degradation for optional dependencies

**Example Configuration:**

```python
# Development (fast iteration)
config = HarnessConfig.for_development()
# - 1 retry
# - Simple logging
# - No checkpointing
# - 10,000 req/hr (no limit)

# Production (maximum reliability)
config = HarnessConfig.for_production()
# - 5 retries
# - Datadog tracing
# - Redis checkpointing
# - 1000 req/hr quota
```

---

## ðŸ”§ Redis Configuration (Your .env)

```bash
# Redis Cloud Connection
REDIS_URL=redis://<REDACTED_REDIS_URL>
REDIS_NAMESPACE=agentic-dev  # Tenant isolation

# Stream Configuration
REDIS_STREAM_MAXLEN=20000     # Max messages per stream
ENABLE_DLQ=1                   # Dead letter queue for failures
REDIS_MAX_RETRIES=2
REDIS_RETRY_BACKOFF_MS=0

# Consumer Groups
REDIS_GROUP_WRITERS=persist-writers
REDIS_GROUP_WORKERS=rag-workers

# Existing Streams (from old setup)
REDIS_STREAM_TASKS=rag:tasks
REDIS_STREAM_RESULTS=rag:results
REDIS_STREAM_TASKS_WRITE=persist:tasks
REDIS_STREAM_RESULTS_WRITE=persist:results

# OpenAI for Deep Agents
OPENAI_API_KEY=sk-proj-...

# Supabase (Database)
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=<SUPABASE_JWT>
```

---

## ðŸ“Š Current Stream Topology

### **Active Streams (Tier 1 & 2):**

```
agentic-dev:manager:tasks       â† External entry point
agentic-dev:manager:results     â†’ Final results

agentic-dev:leads:tasks         â† Manager delegates here
agentic-dev:leads:results       â†’ Leads results

agentic-dev:outreach:tasks      â† Manager delegates here
agentic-dev:outreach:results    â†’ Outreach results
```

### **To Be Built (Tier 3):**

```
agentic-dev:copywriter:tasks/results      â³ Email generation
agentic-dev:booking:tasks/results         â³ Meeting scheduling
agentic-dev:sequencing:tasks/results      â³ ML optimization
agentic-dev:rag:tasks/results            â³ Enrichment
agentic-dev:persistence:tasks/results     â³ Bulk operations
agentic-dev:deduplication:tasks/results   â³ Duplicate detection
```

---

## ðŸš€ How to Run

**Start All Consumers:**

```powershell
# Terminal 1: Manager
$env:OPENAI_API_KEY="sk-proj-..."
$env:TENANT_ID="agentic-dev"
python agent/manager/consumer.py

# Terminal 2: Leads
python agent/orchestrators/leads_orchestrator/consumer.py

# Terminal 3: Outreach
python agent/orchestrators/outreach_orchestrator/consumer.py
```

**Send Test Task:**

```python
import redis
r = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

# Send to Manager
r.xadd("agentic-dev:manager:tasks", {
    "payload": json.dumps({
        "task_id": "test-001",
        "goal": "Find 50 tech leads in SF and create email campaign"
    })
})

# Check results (after ~30 seconds)
results = r.xread({"agentic-dev:manager:results": "0"}, count=10)
```

---

## ðŸŽ¯ Key Design Principles

1. **Universal Harness** - ONE wrapper works with ALL agents
2. **Plugin Architecture** - Swap components without code changes
3. **Graceful Degradation** - Optional dependencies handled cleanly
4. **Environment-Specific** - Dev uses simple logging, prod uses Datadog
5. **Cost-Conscious** - Swap backends (Redisâ†’S3) without code changes
6. **Future-Proof** - New orchestrators just wrap, no harness changes

---

## ðŸ“ˆ What's Working Now

âœ… **Manager Agent** - Receives requests, delegates to orchestrators
âœ… **Leads Orchestrator** - 8 tools, database operations
âœ… **Outreach Orchestrator** - 8 tools, campaign coordination
âœ… **Agent Harness** - 11 component implementations
âœ… **Redis Streams** - Manager successfully delegating to Leads
âœ… **Consumer Groups** - Horizontal scaling ready
âœ… **Deep Agents** - LangChain integration working

---

## ðŸ”œ What's Next

1. **Build Tier 3 Agents** - Copywriter, Booking, Sequencing, etc.
2. **End-to-End Testing** - Full campaign flow validation
3. **Production Deployment** - Datadog, Redis cluster, S3 checkpointing
4. **Monitoring Dashboard** - Real-time stream metrics
5. **API Gateway** - REST API for external requests

**Your system is a production-grade orchestration framework that can coordinate unlimited AI agents through Redis Streams!** ðŸš€
