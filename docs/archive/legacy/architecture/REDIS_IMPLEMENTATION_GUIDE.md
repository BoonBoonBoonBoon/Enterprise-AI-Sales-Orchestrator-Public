# Redis Architecture Implementation Guide

**Last Updated**: November 22, 2025  
**Status**: Production Ready  
**Version**: 2.0

---

## Quick Start

### 1. Visualize Your Data Flow
```bash
python scripts/manage_redis_streams.py --visualize
```

### 2. Audit Current Streams
```bash
python scripts/manage_redis_streams.py --audit
```

### 3. Initialize All Streams
```bash
python scripts/manage_redis_streams.py --initialize
```

### 4. Verify Everything Works
```bash
python scripts/manage_redis_streams.py --verify
```

---

## What Changed?

### Old System (❌ Deprecated)
```python
# Hardcoded stream names scattered across files
task_stream = f"{tenant_id}:rag:tasks"  # Where is this defined?
result_stream = f"{tenant_id}:orchestrators:leads:tasks"  # Inconsistent!
```

**Problems**:
- No single source of truth
- Inconsistent naming conventions
- No upstream/downstream visibility
- Hard to add new streams
- Migration nightmares

### New System (✅ Canonical)
```python
from services.redis.stream_registry import get_registry, Tier, StreamType

# Type-safe, centralized stream access
registry = get_registry()
task_stream = registry.get_stream_key(
    Tier.AGENT, "rag", StreamType.TASKS, tenant_id
)
# Returns: "agentic-dev:agents:rag:tasks"

# Get metadata
stream_def = registry.get(Tier.AGENT, "rag", StreamType.TASKS)
print(stream_def.consumer_group)  # "rag-workers"
print(stream_def.max_len)  # 20000
print(stream_def.description)  # Full description

# Get data flow
downstream = registry.get_downstream_streams(
    Tier.AGENT, "rag", StreamType.RESULTS, tenant_id
)
# Returns: ["agentic-dev:leads:results"]
```

**Benefits**:
- Single source of truth (`stream_registry.py`)
- Consistent naming enforced by code
- Queryable data flow graph
- Easy to add new streams
- Migration tools included

---

## The Canonical Naming Convention

### Manager (Tier 1)
```
{tenant}:manager:tasks
{tenant}:manager:results
```

### Orchestrators (Tier 2)
```
{tenant}:leads:tasks
{tenant}:leads:results
{tenant}:outreach:tasks
{tenant}:outreach:results
```

**Why NOT** `{tenant}:orchestrators:leads:tasks`?
- Shorter = simpler
- "orchestrators" adds no value
- Following KISS principle

### Agents (Tier 3)
```
{tenant}:agents:rag:tasks
{tenant}:agents:rag:results
{tenant}:agents:persistence:tasks
{tenant}:agents:persistence:results
{tenant}:agents:copywriter:tasks
{tenant}:agents:copywriter:results
{tenant}:agents:booking:tasks
{tenant}:agents:booking:results
{tenant}:agents:sequencing:tasks
{tenant}:agents:sequencing:results
{tenant}:agents:deduplication:tasks
{tenant}:agents:deduplication:results
```

### System Streams
```
{tenant}:system:dlq
{tenant}:system:events
{tenant}:system:health
{tenant}:system:audit
{tenant}:system:metrics
```

---

## Data Flow Patterns

### Downstream (Task Delegation)

```
External API
    ↓
Manager → {tenant}:manager:tasks
    ├─> {tenant}:leads:tasks
    │   ├─> {tenant}:agents:rag:tasks
    │   ├─> {tenant}:agents:persistence:tasks
    │   └─> {tenant}:agents:deduplication:tasks
    │
    └─> {tenant}:outreach:tasks
        ├─> {tenant}:agents:copywriter:tasks
        ├─> {tenant}:agents:booking:tasks
        └─> {tenant}:agents:sequencing:tasks
```

### Upstream (Result Propagation)

```
Agents (Tier 3)
    ↓
{tenant}:agents:*:results
    ↓
Orchestrators (Tier 2)
    ↓
{tenant}:leads:results
{tenant}:outreach:results
    ↓
Manager (Tier 1)
    ↓
{tenant}:manager:results
    ↓
External API Response
```

---

## Implementation Examples

### Example 1: Consumer with Registry

```python
from services.redis.stream_registry import get_registry, Tier, StreamType
import redis
import os

class RAGConsumer:
    def __init__(self, redis_client, tenant_id: str):
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.registry = get_registry()
        
        # Get streams from registry
        self.task_stream = self.registry.get_stream_key(
            Tier.AGENT, "rag", StreamType.TASKS, tenant_id
        )
        self.result_stream = self.registry.get_stream_key(
            Tier.AGENT, "rag", StreamType.RESULTS, tenant_id
        )
        
        # Get consumer group from stream definition
        stream_def = self.registry.get(Tier.AGENT, "rag", StreamType.TASKS)
        self.consumer_group = stream_def.consumer_group  # "rag-workers"
        self.consumer_name = f"rag-worker-{os.getpid()}"
        
        # Ensure consumer group exists
        try:
            self.redis.xgroup_create(
                self.task_stream,
                self.consumer_group,
                id="0",
                mkstream=True
            )
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise
```

### Example 2: Publishing Tasks

```python
from services.redis.stream_registry import get_registry, Tier, StreamType
from datetime import datetime

def publish_enrichment_task(redis_client, tenant_id: str, lead_id: str):
    """Publish enrichment task to RAG agent"""
    registry = get_registry()
    
    # Get target stream
    stream_key = registry.get_stream_key(
        Tier.AGENT, "rag", StreamType.TASKS, tenant_id
    )
    
    # Get max length from stream definition
    stream_def = registry.get(Tier.AGENT, "rag", StreamType.TASKS)
    
    # Publish
    message_id = redis_client.xadd(
        stream_key,
        {
            "task_id": f"enrich_{lead_id}",
            "lead_id": lead_id,
            "operation": "enrich_company",
            "timestamp": datetime.utcnow().isoformat()
        },
        maxlen=stream_def.max_len  # 20000 for RAG
    )
    
    return message_id
```

### Example 3: Getting Data Flow

```python
from services.redis.stream_registry import get_registry, Tier, StreamType

registry = get_registry()

# Where does RAG send results?
downstream = registry.get_downstream_streams(
    Tier.AGENT, "rag", StreamType.RESULTS, "agentic-dev"
)
print(downstream)  # ["agentic-dev:leads:results"]

# Where does RAG get tasks from?
upstream = registry.get_upstream_streams(
    Tier.AGENT, "rag", StreamType.TASKS, "agentic-dev"
)
print(upstream)  # ["agentic-dev:leads:tasks"]

# Get complete data flow graph
graph = registry.get_data_flow_graph("agentic-dev")
# {
#   "agentic-dev:manager:tasks": ["agentic-dev:leads:tasks", "agentic-dev:outreach:tasks"],
#   "agentic-dev:leads:tasks": ["agentic-dev:agents:rag:tasks", ...],
#   ...
# }
```

---

## Migration Guide

### Step 1: Audit Current State
```bash
python scripts/manage_redis_streams.py --audit
```

**Output**:
```
CANONICAL STREAMS (Following New Convention)
  ✓ agentic-dev:manager:tasks (10 messages)
  ✓ agentic-dev:leads:tasks (5 messages)
  ...

LEGACY STREAMS (Old Naming Convention)
  ⚠ agentic-dev:rag:tasks (100 messages)
     → Should migrate to: agentic-dev:agents:rag:tasks
  ⚠ agentic-dev:orchestrators:leads:tasks (0 messages)
     → Should migrate to: agentic-dev:leads:tasks
  ...
```

### Step 2: Initialize New Streams
```bash
python scripts/manage_redis_streams.py --initialize
```

This creates all streams and consumer groups defined in the registry.

### Step 3: Migrate Legacy Streams (DRY RUN)
```bash
# First, test without deleting old streams
python scripts/manage_redis_streams.py --migrate
```

### Step 4: Migrate and Delete Old (After Verification)
```bash
# DANGEROUS: This will delete old streams
python scripts/manage_redis_streams.py --migrate --delete-old
```

### Step 5: Update Consumers
Update all consumer code to use the registry:

**Before**:
```python
task_stream = f"{tenant_id}:rag:tasks"
```

**After**:
```python
from services.redis.stream_registry import get_registry, Tier, StreamType

registry = get_registry()
task_stream = registry.get_stream_key(
    Tier.AGENT, "rag", StreamType.TASKS, tenant_id
)
```

### Step 6: Verify
```bash
python scripts/manage_redis_streams.py --verify
```

---

## Adding New Streams

To add a new agent or orchestrator:

### 1. Add to Registry

Edit `services/redis/stream_registry.py`:

```python
# In StreamRegistry._register_all_streams()

# Add new agent
self.register(StreamDefinition(
    key_pattern="{tenant}:agents:linkedin:tasks",
    tier=Tier.AGENT,
    component="linkedin",
    stream_type=StreamType.TASKS,
    consumer_group="linkedin-workers",
    max_len=10000,
    retention_hours=24,
    description="LinkedIn API integration tasks",
    upstream=["{tenant}:leads:tasks"],
    downstream=["{tenant}:leads:results"]
))

self.register(StreamDefinition(
    key_pattern="{tenant}:agents:linkedin:results",
    tier=Tier.AGENT,
    component="linkedin",
    stream_type=StreamType.RESULTS,
    consumer_group=None,
    max_len=10000,
    retention_hours=24,
    description="LinkedIn API results",
    upstream=[],
    downstream=["{tenant}:leads:results"]
))
```

### 2. Initialize Streams
```bash
python scripts/manage_redis_streams.py --initialize
```

### 3. Use in Code
```python
from services.redis.stream_registry import get_registry, Tier, StreamType

registry = get_registry()
linkedin_tasks = registry.get_stream_key(
    Tier.AGENT, "linkedin", StreamType.TASKS, tenant_id
)
```

That's it! The stream is now part of the system.

---

## Monitoring & Operations

### Check Stream Health
```python
from services.redis.stream_registry import get_registry

def check_health(redis_client, tenant_id: str):
    registry = get_registry()
    all_streams = registry.get_all_streams(tenant_id)
    
    for name, stream_key in all_streams.items():
        try:
            length = redis_client.xlen(stream_key)
            print(f"✓ {stream_key}: {length} messages")
        except Exception as e:
            print(f"✗ {stream_key}: {e}")
```

### Monitor Consumer Groups
```bash
redis-cli -h HOST -p PORT -a PASSWORD
> XINFO GROUPS agentic-dev:agents:rag:tasks
> XPENDING agentic-dev:agents:rag:tasks rag-workers
```

### Export Configuration
```bash
python scripts/manage_redis_streams.py --export config.json
```

This creates a JSON file with all stream definitions and current lengths.

---

## Troubleshooting

### Problem: "Stream not found" error

**Solution**: The stream hasn't been initialized.
```bash
python scripts/manage_redis_streams.py --initialize
```

### Problem: Consumer not receiving messages

**Checklist**:
1. Is the stream initialized?
   ```bash
   python scripts/manage_redis_streams.py --verify
   ```

2. Is the consumer using the correct stream key?
   ```python
   # Use registry instead of hardcoded names
   stream_key = registry.get_stream_key(Tier.AGENT, "rag", StreamType.TASKS, tenant_id)
   ```

3. Is the consumer group created?
   ```bash
   redis-cli XINFO GROUPS {stream_key}
   ```

### Problem: Legacy streams still exist

**Solution**: Migrate them.
```bash
# Dry run first
python scripts/manage_redis_streams.py --migrate

# Then delete old streams
python scripts/manage_redis_streams.py --migrate --delete-old
```

---

## Best Practices

### 1. Always Use the Registry
```python
# ❌ DON'T
task_stream = f"{tenant_id}:agents:rag:tasks"

# ✅ DO
task_stream = registry.get_stream_key(Tier.AGENT, "rag", StreamType.TASKS, tenant_id)
```

### 2. Use Stream Metadata
```python
stream_def = registry.get(Tier.AGENT, "rag", StreamType.TASKS)

# Get configured max length
maxlen = stream_def.max_len  # 20000

# Get consumer group
group = stream_def.consumer_group  # "rag-workers"

# Get description
desc = stream_def.description
```

### 3. Check Data Flow
```python
# Where should I send results?
downstream = registry.get_downstream_streams(
    Tier.AGENT, "rag", StreamType.RESULTS, tenant_id
)

# Where do my tasks come from?
upstream = registry.get_upstream_streams(
    Tier.AGENT, "rag", StreamType.TASKS, tenant_id
)
```

### 4. Respect MAXLEN
```python
stream_def = registry.get(Tier.AGENT, "rag", StreamType.TASKS)

redis_client.xadd(
    stream_key,
    message,
    maxlen=stream_def.max_len  # Use configured value
)
```

---

## Files Overview

```
services/redis/
├── stream_registry.py          # ⭐ Central registry (source of truth)
├── client.py                    # Redis client wrapper
├── config.py                    # Connection configuration
├── streams.py                   # Legacy (to be deprecated)
└── messages.py                  # Message schemas

docs/architecture/services/
└── REDIS_ARCHITECTURE.md        # ⭐ Complete documentation

scripts/
└── manage_redis_streams.py      # ⭐ Migration and management tool
```

---

## Summary

### What You Get
✅ **Single Source of Truth**: All streams defined in one place  
✅ **Type Safety**: Compile-time checks for stream access  
✅ **Data Flow Visibility**: Queryable upstream/downstream relationships  
✅ **Easy Migration**: Tools to transition from legacy naming  
✅ **Simple Addition**: Add new streams with minimal code  
✅ **Monitoring**: Built-in health checks and auditing  

### What Changed
- Stream names now enforced by `StreamRegistry`
- Simpler naming convention (dropped "orchestrators" prefix)
- All metadata (max_len, consumer_group, etc.) centralized
- Data flow relationships explicitly defined
- Migration tools provided

### Next Steps
1. Run `python scripts/manage_redis_streams.py --audit`
2. Run `python scripts/manage_redis_streams.py --visualize`
3. Update your consumers to use the registry
4. Migrate legacy streams
5. Enjoy organized, maintainable Redis architecture!

---

**Questions?** Check `docs/architecture/services/REDIS_ARCHITECTURE.md` for complete details.
