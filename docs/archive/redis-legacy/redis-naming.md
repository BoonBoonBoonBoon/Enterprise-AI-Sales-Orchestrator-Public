# Redis Stream Naming Convention

## Overview
Standardized naming structure for Redis Streams across the three-tier architecture.

## Naming Pattern

### Format
```
{tenant_id}:{tier}:{agent_name}:{stream_type}
```

### Components
- **tenant_id**: Tenant identifier (e.g., `acme`, `demo`, `test-tenant`)
- **tier**: Architecture tier (`manager`, `orchestrators`, `agents`)
- **agent_name**: Specific agent/orchestrator name
- **stream_type**: `tasks` or `results`

## Stream Structure by Tier

### Tier 1: Manager Agent
```
{tenant}:manager:tasks           # Incoming user requests
{tenant}:manager:results         # Final results to user
```

**Example:**
- `acme:manager:tasks`
- `acme:manager:results`

### Tier 2: Orchestrators

#### Leads Orchestrator
```
{tenant}:orchestrators:leads:tasks
{tenant}:orchestrators:leads:results
```

#### Outreach Orchestrator  
```
{tenant}:orchestrators:outreach:tasks
{tenant}:orchestrators:outreach:results
```

**Examples:**
- `acme:orchestrators:leads:tasks`
- `acme:orchestrators:leads:results`
- `acme:orchestrators:outreach:tasks`
- `acme:orchestrators:outreach:results`

### Tier 3: Operational Agents

#### RAG Agent (Research & Enrichment)
```
{tenant}:agents:rag:tasks        # Enrichment requests
{tenant}:agents:rag:results      # Enriched data
```

#### Persistence Agent (Database Operations)
```
{tenant}:agents:persistence:tasks
{tenant}:agents:persistence:results
```

#### Copywriter Agent (Content Generation)
```
{tenant}:agents:copywriter:tasks
{tenant}:agents:copywriter:results
```

#### Booking Agent (Calendar Management)
```
{tenant}:agents:booking:tasks
{tenant}:agents:booking:results
```

#### Sequencing Agent (Send Optimization)
```
{tenant}:agents:sequencing:tasks
{tenant}:agents:sequencing:results
```

#### Deduplication Agent (Lead Merging)
```
{tenant}:agents:deduplication:tasks
{tenant}:agents:deduplication:results
```

**Examples:**
- `acme:agents:rag:tasks`
- `acme:agents:rag:results`
- `acme:agents:persistence:tasks`
- `acme:agents:persistence:results`

## Benefits of This Structure

### 1. **Namespace Hierarchy**
```
{tenant}/
├── manager/
│   ├── tasks
│   └── results
├── orchestrators/
│   ├── leads/
│   │   ├── tasks
│   │   └── results
│   └── outreach/
│       ├── tasks
│       └── results
└── agents/
    ├── rag/
    │   ├── tasks
    │   └── results
    ├── persistence/
    │   ├── tasks
    │   └── results
    └── copywriter/
        ├── tasks
        └── results
```

### 2. **Easy Pattern Matching**
```redis
# All RAG streams for tenant
KEYS acme:agents:rag:*

# All agent streams for tenant
KEYS acme:agents:*

# All task streams for tenant
KEYS acme:*:*:tasks

# All streams for tenant
KEYS acme:*
```

### 3. **Clear Organizational Structure**
- Tier 1 (strategic) → `manager`
- Tier 2 (business logic) → `orchestrators`
- Tier 3 (operational) → `agents`

### 4. **Multi-Tenancy Support**
Each tenant has isolated streams with no cross-contamination.

### 5. **Monitoring & Debugging**
Easy to identify stream ownership and purpose from the name alone.

## Consumer Group Naming

### Format
```
{agent_name}-workers
```

### Examples
- `rag-workers`
- `persistence-workers`
- `copywriter-workers`
- `leads-orchestrator-workers`
- `outreach-orchestrator-workers`

**Consumer instance naming:**
```
{agent_name}-worker-{pid}
```
- `rag-worker-12345`
- `persistence-worker-67890`

## Implementation

### RAG Agent Consumer (Example)
```python
class RAGConsumer:
    def __init__(self, redis_client, tenant_id="default"):
        # Stream names - organized under agents namespace
        self.task_stream = f"{tenant_id}:agents:rag:tasks"
        self.result_stream = f"{tenant_id}:agents:rag:results"
        self.consumer_group = "rag-workers"
        self.consumer_name = f"rag-worker-{os.getpid()}"
```

### Publishing Tasks
```python
# From Leads Orchestrator to RAG Agent
redis.xadd(
    f"{tenant_id}:agents:rag:tasks",
    {
        "task_id": "enrich-123",
        "action": "enrich_company",
        "payload": json.dumps(company_data)
    }
)
```

### Consuming Tasks
```python
# RAG Agent consumer
messages = redis.xreadgroup(
    "rag-workers",                        # Consumer group
    f"rag-worker-{os.getpid()}",         # Consumer name
    {f"{tenant_id}:agents:rag:tasks": ">"},  # Stream
    count=10,
    block=5000
)
```

## Migration Notes

### Old Structure (Deprecated)
```
{tenant}:rag:tasks           ❌ Too flat
{tenant}:rag:results         ❌ No tier indication
{tenant}:persist:tasks       ❌ Inconsistent naming
```

### New Structure (Current)
```
{tenant}:agents:rag:tasks           ✅ Clear hierarchy
{tenant}:agents:rag:results         ✅ Tier indicated
{tenant}:agents:persistence:tasks   ✅ Full name
```

## Stream Maxlen Policy

### Recommendations
- **Tasks**: Short retention (auto-trim after processing)
  - `MAXLEN ~ 1000` - Keep last 1000 tasks for debugging
- **Results**: Longer retention (cache enriched data)
  - `MAXLEN ~ 10000` - Keep results for potential re-use

### Implementation
```python
redis.xadd(
    f"{tenant_id}:agents:rag:results",
    payload,
    maxlen=10000,  # Approximate trim
)
```

## Monitoring Queries

### Check Stream Lengths
```redis
# RAG task queue depth
XLEN acme:agents:rag:tasks

# RAG result cache size
XLEN acme:agents:rag:results
```

### Check Consumer Groups
```redis
# RAG consumer group info
XINFO GROUPS acme:agents:rag:tasks

# RAG consumer details
XINFO CONSUMERS acme:agents:rag:tasks rag-workers
```

### Check Pending Messages
```redis
# Pending messages in RAG consumer group
XPENDING acme:agents:rag:tasks rag-workers
```

## References

- **Implementation**: `agent/operational_agents/rag_agent/consumer_new.py`
- **Tests**: `tests/test_rag_agent_new.py`
- **Architecture**: Three-tier Deep Agents + Harness pattern
- **Date**: November 7, 2025

---

**Status**: ✅ Implemented for RAG Agent
**Next**: Apply to Persistence, Copywriter, and remaining Tier 3 agents
