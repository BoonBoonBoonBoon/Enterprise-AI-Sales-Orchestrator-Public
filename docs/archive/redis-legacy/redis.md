# Redis Service Architecture

Complete reference for Redis infrastructure, streams, and operational procedures in the Agentic System.

---

## Table of Contents

1. [Overview](#overview)
2. [Redis Cloud Setup](#redis-cloud-setup)
3. [Three-Tier Stream Architecture](#three-tier-stream-architecture)
4. [Stream Naming Convention](#stream-naming-convention)
5. [Consumer Groups](#consumer-groups)
6. [Message Structure & Envelope Format](#message-structure--envelope-format)
7. [Operational Features](#operational-features)
8. [Environment Variables](#environment-variables)
9. [Health Monitoring](#health-monitoring)
10. [Troubleshooting](#troubleshooting)
11. [Running the System](#running-the-system)

---

## Overview

Redis Streams is the core messaging backbone for the Agentic System, enabling:

- **Asynchronous task delegation** between tiers (Manager → Orchestrators → Agents)
- **At-least-once delivery semantics** with consumer groups
- **Horizontal scaling** through load-balanced message distribution
- **Fault tolerance** with automatic recovery and retry logic
- **Message persistence** with replay capabilities

### Architecture Principles

1. **Separation of Concerns** - Clear boundaries between Manager (Tier 1), Orchestrators (Tier 2), and Agents (Tier 3)
2. **Async Communication** - All inter-component communication via Redis Streams (no synchronous calls)
3. **Consumer Groups** - Enable horizontal scaling and fault tolerance
4. **Result Aggregation** - Parent tasks wait for child results, flowing back up the hierarchy
5. **Observability** - Task status tracking, metrics, and distributed tracing

---

## Redis Cloud Setup

### Connection Details

**Current Deployment:**

- **Host:** `redis-15143.c335.europe-west2-1.gce.redns.redis-cloud.com`
- **Port:** `15143`
- **Version:** `8.0.2`
- **Protocol:** Non-TLS (`redis://`)
- **Authentication:** Password-based

**Environment Configuration:**

```bash
# .env
REDIS_URL=redis://default:<REDIS_PASSWORD>@redis-15143.c335.europe-west2-1.gce.redns.redis-cloud.com:15143
REDIS_NAMESPACE=agentic-dev
```

**Connection String Format:**

```
redis://[username]:[password]@[host]:[port]/[db]
```

### Namespace & Key Structure

All keys are prefixed with `REDIS_NAMESPACE` for environment isolation:

**Key Pattern:** `{namespace}:{domain}:{key}`

**Examples:**

- Stream: `agentic-dev:rag:tasks`
- Heartbeat: `agentic-dev:ops:hb:rag:worker-1`
- Workflow state: `agentic-dev:workflow:state:correlation-123`

---

## Three-Tier Stream Architecture

The system uses a three-tier architecture where each tier communicates via dedicated Redis Streams:

```
┌─────────────────────────────────────────────────────────────────┐
│                        TIER 1: MANAGER                          │
│  (Strategic AI - Goal decomposition & orchestrator delegation)  │
│  Streams: manager:tasks, manager:results                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ XADD (delegate tasks)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TIER 2: ORCHESTRATORS                        │
│  ┌──────────────┐  ┌─────────────────┐  ┌──────────────────┐   │
│  │    Leads     │  │    Outreach     │  │   Future Orch.   │   │
│  │ Orchestrator │  │  Orchestrator   │  │   (Coding/Data)  │   │
│  │leads:tasks   │  │outreach:tasks   │  │                  │   │
│  └──────────────┘  └─────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ XADD (delegate sub-tasks)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 TIER 3: OPERATIONAL AGENTS                      │
│  ┌──────────┐  ┌─────────┐  ┌─────────┐  ┌────────────────┐   │
│  │   RAG    │  │Copywriter│  │Booking  │  │   Sequencing   │   │
│  │  Agent   │  │  Agent   │  │ Agent   │  │     Agent      │   │
│  │rag:tasks │  │copy:tasks│  │booking: │  │sequencing:     │   │
│  └──────────┘  └─────────┘  └─────────┘  └────────────────┘   │
│  ┌────────────┐  ┌──────────────┐                              │
│  │Persistence │  │Deduplication │                              │
│  │   Agent    │  │    Agent     │                              │
│  │persist:    │  │dedup:tasks   │                              │
│  └────────────┘  └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

### Current Active Streams

#### ✅ Tier 1: Manager (External Entry Point)

| Stream                     | Purpose           | Consumer Group    | Status    |
| -------------------------- | ----------------- | ----------------- | --------- |
| `{tenant}:manager:tasks`   | External requests | `manager-workers` | ✅ Active |
| `{tenant}:manager:results` | Final results     | N/A (XREAD only)  | ✅ Active |

#### ✅ Tier 2: Orchestrators

| Orchestrator | Task Stream               | Result Stream               | Consumer Group     | Status    |
| ------------ | ------------------------- | --------------------------- | ------------------ | --------- |
| **Leads**    | `{tenant}:leads:tasks`    | `{tenant}:leads:results`    | `leads-workers`    | ✅ Active |
| **Outreach** | `{tenant}:outreach:tasks` | `{tenant}:outreach:results` | `outreach-workers` | ✅ Active |

#### ✅ Tier 3: Operational Agents

| Agent           | Task Stream                  | Result Stream                  | Consumer Group        | Status        |
| --------------- | ---------------------------- | ------------------------------ | --------------------- | ------------- |
| **RAG**         | `{tenant}:rag:tasks`         | `{tenant}:rag:results`         | `rag-workers`         | ✅ Active     |
| **Copywriter**  | `{tenant}:copywriter:tasks`  | `{tenant}:copywriter:results`  | `copywriter-workers`  | ✅ Active     |
| **Persistence** | `{tenant}:persistence:tasks` | `{tenant}:persistence:results` | `persistence-workers` | ✅ Active     |
| **Booking**     | `{tenant}:booking:tasks`     | `{tenant}:booking:results`     | `booking-workers`     | ⏳ Referenced |
| **Sequencing**  | `{tenant}:sequencing:tasks`  | `{tenant}:sequencing:results`  | `sequencing-workers`  | ⏳ Referenced |

---

## Stream Naming Convention

**Pattern:** `{tenant_id}:{component}:{type}`

**Components:**

- `manager` - Manager Agent (Tier 1)
- `leads`, `outreach` - Orchestrators (Tier 2)
- `rag`, `copywriter`, `persistence`, `booking`, `sequencing`, `deduplication` - Agents (Tier 3)

**Types:**

- `tasks` - Incoming task stream (consumers read via XREADGROUP)
- `results` - Result stream (consumers publish via XADD)
- `dlq` - Dead Letter Queue for failed messages

**Examples:**

```
agentic-dev:manager:tasks
agentic-dev:leads:tasks
agentic-dev:rag:tasks
agentic-dev:rag:dlq
```

---

## Consumer Groups

Each stream uses consumer groups for parallel processing:

```
Stream: agentic-dev:leads:tasks
    └─ Consumer Group: "leads-workers"
        ├─ Worker 1 (PID 1234) - processes message A
        ├─ Worker 2 (PID 1235) - processes message B
        └─ Worker 3 (PID 1236) - processes message C
```

**Benefits:**

- Multiple workers process tasks in parallel
- Each message delivered to only ONE worker in group
- Automatic load balancing by Redis
- Failure recovery via pending entries list

**Consumer Group Names:**

- `manager-workers` - Manager consumers
- `leads-workers` - Leads Orchestrator consumers
- `outreach-workers` - Outreach Orchestrator consumers
- `rag-workers`, `copywriter-workers`, `persistence-workers`, etc. - Agent consumers

---

## Message Structure & Envelope Format

All messages follow the Envelope format with JSON serialization:

```python
# Message structure
{
    "data": json.dumps({
        "metadata": {
            "message_id": "msg-1",
            "task_id": "t-1",
            "correlation_id": "cor-1",
            "source": "manager",
            "priority": "normal",
            "created_at": "2024-01-15T10:30:00Z"
        },
        "payload": {
            # Task-specific data
        },
        "status": "pending"
    })
}
```

**Message Lifecycle:**

1. **Producer XADD** - Add message to stream
2. **Consumer XREADGROUP** - Read unacknowledged messages
3. **Process** - Execute task with envelope data
4. **Publish Result** - XADD to result stream
5. **Acknowledge** - XACK to remove from pending

---

## Operational Features

### Heartbeats

Workers send periodic heartbeats for health monitoring:

**Key Pattern:** `ops:hb:{service}:{worker_id}`  
**TTL:** `OPS_HB_TTL` (default: 30 seconds)  
**Update Frequency:** `OPS_HB_INTERVAL` (default: 10 seconds)

```bash
# Configuration
OPS_HB_ENABLED=1
OPS_HB_INTERVAL=10
OPS_HB_TTL=30
```

### Idempotency

Prevent duplicate message processing:

**Key Pattern:** `ops:idemp:{stream}:{message_id}`  
**TTL:** `OPS_IDEMP_TTL` (default: 60 seconds)

Workers attempt `SET NX` before processing. If key exists, message is skipped.

### Retries & Dead Letter Queue (DLQ)

Failed messages are retried with exponential backoff:

1. Message fails → Increment retry counter
2. If retries < `REDIS_MAX_RETRIES`, re-add to task stream
3. Optional backoff: `REDIS_RETRY_BACKOFF_MS` milliseconds
4. If max retries exceeded → Send to DLQ (if `ENABLE_DLQ=1`)

**Configuration:**

```bash
REDIS_MAX_RETRIES=2
REDIS_RETRY_BACKOFF_MS=0
ENABLE_DLQ=1
```

**DLQ Streams:**

- `rag:dlq`, `persist:dlq`, `copy:dlq`

### Stream Trimming

Prevent unbounded growth with automatic trimming:

```bash
REDIS_STREAM_MAXLEN=20000  # Max entries (~approximate)
```

XADD operations use `MAXLEN ~` for approximate trimming.

---

## Environment Variables

### Connection & Namespace

```bash
# Connection
REDIS_URL=redis://default:<REDIS_PASSWORD>@host:port/db
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Namespace (environment isolation)
REDIS_NAMESPACE=agentic-dev
```

### Stream Names (Defaults)

```bash
# RAG
REDIS_STREAM_TASKS=rag:tasks
REDIS_STREAM_RESULTS=rag:results
REDIS_STREAM_DLQ=rag:dlq

# Persistence
REDIS_STREAM_TASKS_WRITE=persist:tasks
REDIS_STREAM_RESULTS_WRITE=persist:results

# Copywriter
REDIS_STREAM_TASKS_COPY=copy:tasks
REDIS_STREAM_RESULTS_COPY=copy:results

# Orchestrator
REDIS_STREAM_ORCHESTRATOR_COMMANDS=orchestrator:commands

# Audit
REDIS_STREAM_AUDIT_EVENTS=audit:events
```

### Consumer Groups

```bash
REDIS_GROUP=rag-workers
REDIS_GROUP_WRITERS=persist-writers
REDIS_GROUP_COPY_WRITERS=copy-writers
REDIS_GROUP_ORCHESTRATORS=orchestrators
```

---

## Health Monitoring

### Quick Health Checks

```bash
# Connection test
python scripts/test_redis_cloud.py

# Stream health
python scripts/streams_health.py --section both --verbose

# Specific streams
python scripts/check_rag_tasks.py
python scripts/check_copy_tasks.py
python scripts/check_audit.py
```

### Manual Redis CLI Checks

```bash
# Connect
redis-cli -u "redis://default:<REDIS_PASSWORD>@host:port"

# Stream lengths
XLEN agentic-dev:rag:tasks
XLEN agentic-dev:leads:tasks

# Consumer groups
XINFO GROUPS agentic-dev:rag:tasks
XINFO CONSUMERS agentic-dev:rag:tasks rag-workers

# Pending messages
XPENDING agentic-dev:rag:tasks rag-workers

# Recent entries
XRANGE agentic-dev:rag:tasks - + COUNT 5
XREVRANGE agentic-dev:audit:events + - COUNT 10

# Heartbeats
KEYS agentic-dev:ops:hb:*
TTL agentic-dev:ops:hb:rag:worker-1
```

### Alerting Thresholds

- **Pending messages > 1000** - Worker capacity issue
- **DLQ growth > 10 messages/minute** - Persistent failures
- **No heartbeats** - All workers down
- **Consumer idle > 5 minutes** - Stalled processing

---

## Troubleshooting

### Connection Issues

**Problem:** `ConnectionError: Error connecting to Redis`

**Solutions:**

1. Verify `REDIS_URL` in `.env` matches Redis Cloud instance
2. Check firewall/network access
3. Validate password authentication
4. For TLS issues, ensure `rediss://` scheme

```bash
python scripts/test_redis_cloud.py
python scripts/check_namespace.py
```

### Namespace Mismatch

**Problem:** Tasks enqueued but workers not processing

**Solution:** Ensure all scripts load `.env` before importing:

```python
from dotenv import load_dotenv
load_dotenv()  # Call BEFORE importing config modules
```

### Messages Stuck in Pending

**Problem:** High pending count, workers active but not processing

**Solutions:**

```bash
# Identify stuck messages
XPENDING agentic-dev:rag:tasks rag-workers

# Claim stuck messages
XCLAIM agentic-dev:rag:tasks rag-workers consumer-new 30000 <message-id>

# Force acknowledgment
XACK agentic-dev:rag:tasks rag-workers <message-id>
```

### DLQ Growth

**Investigation:**

```bash
# Sample DLQ entries
python scripts/check_rag_tasks.py

# Audit trail
python scripts/check_audit.py
```

**Common Causes:**

- Invalid lead data (missing fields)
- Database constraint violations
- LLM API rate limits
- Envelope validation errors

---

## Running the System

### Start All Consumers

```powershell
# All-in-one startup
python start_all_consumers.py

# Individual consumers
python agent/manager/consumer.py
python agent/orchestrators/leads_orchestrator/consumer.py
python agent/orchestrators/outreach_orchestrator/consumer.py
```

### Environment Setup

```powershell
# Set tenant
$env:TENANT_ID = "acme"

# Set environment
$env:ENVIRONMENT = "development"

# Redis connection (if not using defaults)
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
```

### Test Delegation

```python
from agent.manager.manager_agent import ManagerAgent
from agent.tools.redis.client import get_redis_client

# Initialize
redis = get_redis_client()
manager = ManagerAgent(redis, tenant_id="acme")

# Test delegation
result = manager.execute(
    goal="Find 50 AI startups in San Francisco"
)
print(result)
```

### Monitor Streams

```python
from agent.tools.redis.client import RedisPubSub

redis = RedisPubSub().client
tenant_id = "agentic-dev"

streams = [
    "manager:tasks", "leads:tasks", "outreach:tasks",
    "rag:tasks", "copywriter:tasks"
]

for stream_name in streams:
    full_name = f"{tenant_id}:{stream_name}"
    try:
        length = redis.xlen(full_name)
        print(f"{stream_name}: {length} messages")
    except:
        print(f"{stream_name}: not found")
```

---

## Complete Flow Example

**Scenario:** "Create outreach campaign for 50 tech leads in San Francisco"

```
1. External API → manager:tasks
2. Manager delegates to leads:tasks + outreach:tasks
3. Leads Orchestrator delegates to rag:tasks for enrichment
4. RAG Agent processes → rag:results
5. Leads completes → leads:results
6. Outreach Orchestrator delegates to copywriter:tasks, booking:tasks, sequencing:tasks
7. Agents process → copywriter:results, booking:results, sequencing:results
8. Outreach completes → outreach:results
9. Manager aggregates → manager:results
10. External API polls manager:results → Returns to client
```

---

## Additional Resources

- **Testing Scripts:** `scripts/test_*.py`, `scripts/check_*.py`
- **Health Monitoring:** `scripts/streams_health.py`
- **Redis Streams Docs:** https://redis.io/docs/data-types/streams/
- **Redis Cloud:** https://redis.io/cloud/

---

**Last Updated:** November 9, 2025  
**Redis Version:** 8.0.2  
**Protocol:** Non-TLS (development), TLS recommended for production
