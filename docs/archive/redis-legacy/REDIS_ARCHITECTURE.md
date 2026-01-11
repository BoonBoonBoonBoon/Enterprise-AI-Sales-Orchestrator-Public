# Redis Architecture - Canonical Specification

**Version**: 2.0  
**Date**: November 22, 2025  
**Status**: Active  
**Authority**: This document supersedes all previous Redis naming and architecture documents

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Design Principles](#design-principles)
3. [Stream Naming Convention](#stream-naming-convention)
4. [Data Flow Patterns](#data-flow-patterns)
5. [Stream Inventory](#stream-inventory)
6. [Implementation Guide](#implementation-guide)
7. [Migration from Legacy](#migration-from-legacy)
8. [Monitoring & Operations](#monitoring--operations)

---

## Executive Summary

This document defines the **canonical Redis architecture** for the Agentic System. It establishes:

### The Standard Stream Naming Pattern
```
{tenant_id}:{tier}:{component}:{stream_type}
```

### Three-Tier Hierarchy
- **Tier 1 (Manager)**: Strategic decision-making - `{tenant}:manager:{type}`
- **Tier 2 (Orchestrators)**: Business logic - `{tenant}:{orch}:{type}`
- **Tier 3 (Agents)**: Operational execution - `{tenant}:agents:{agent}:{type}`

### Clear Data Flow Direction
- **Downstream** (Delegation): Manager → Orchestrator → Agent
- **Upstream** (Results): Agent → Orchestrator → Manager

---

## Design Principles

### 1. **Simplicity First**
The naming convention is deliberately simple to avoid confusion:
- Manager streams: 2 components (`{tenant}:manager:tasks`)
- Orchestrator streams: 3 components (`{tenant}:leads:tasks`)
- Agent streams: 4 components (`{tenant}:agents:rag:tasks`)

**Why NOT** `{tenant}:orchestrators:leads:tasks`?
- The word "orchestrators" adds no value (we know `leads` is an orchestrator)
- Shorter names = less typing, less errors, faster development
- Following the KISS principle

### 2. **Hierarchical Isolation**
Each tier has clear boundaries:
```
Tier 1: {tenant}:manager:*
Tier 2: {tenant}:{orchestrator_name}:*
Tier 3: {tenant}:agents:{agent_name}:*
System: {tenant}:system:*
```

### 3. **Multi-Tenancy by Default**
Every stream MUST start with `{tenant_id}`:
- Enables complete isolation between tenants
- Allows scaling by tenant (shard by tenant_id if needed)
- Prevents accidental cross-tenant data leaks

### 4. **Explicit Data Flow**
Every stream definition includes:
- **upstream**: Which streams feed INTO this stream
- **downstream**: Which streams this stream feeds INTO

This creates a queryable graph of data flow.

### 5. **Type Safety**
The `StreamRegistry` provides type-safe access:
```python
# Compile-time safe
registry.get_stream_key(Tier.AGENT, "rag", StreamType.TASKS, tenant_id)

# Runtime error if stream doesn't exist
registry.get(Tier.AGENT, "nonexistent", StreamType.TASKS)  # KeyError
```

---

## Stream Naming Convention

### Format Specification

```
{tenant_id}:{tier_component}:{stream_type}
```

Where:
- `{tenant_id}`: Tenant identifier (e.g., `agentic-dev`, `acme`, `demo`)
- `{tier_component}`: Varies by tier (see below)
- `{stream_type}`: One of `tasks`, `results`, `events`, `dlq`, `health`, `audit`, `metrics`

### Tier-Specific Patterns

#### Tier 1: Manager
```
{tenant}:manager:tasks
{tenant}:manager:results
```

**Rationale**: Manager is singular - only one manager per tenant.

#### Tier 2: Orchestrators
```
{tenant}:leads:tasks
{tenant}:leads:results

{tenant}:outreach:tasks
{tenant}:outreach:results
```

**Rationale**: Direct component name (no "orchestrators" prefix for simplicity).

#### Tier 3: Agents
```
{tenant}:agents:rag:tasks
{tenant}:agents:rag:results

{tenant}:agents:persistence:tasks
{tenant}:agents:persistence:results

{tenant}:agents:copywriter:tasks
{tenant}:agents:copywriter:results
```

**Rationale**: "agents" prefix distinguishes from orchestrators and allows multiple specialized agents.

#### System Streams
```
{tenant}:system:dlq
{tenant}:system:events
{tenant}:system:health
{tenant}:system:audit
{tenant}:system:metrics
```

**Rationale**: System-wide concerns that span all tiers.

### Pattern Matching Examples

```redis
# All streams for a tenant
KEYS agentic-dev:*

# All task streams
KEYS agentic-dev:*:tasks

# All agent streams
KEYS agentic-dev:agents:*

# All RAG streams
KEYS agentic-dev:agents:rag:*

# All system streams
KEYS agentic-dev:system:*
```

---

## Data Flow Patterns

### Downstream Flow (Task Delegation)

```
External Request
    ↓
┌─────────────────────────┐
│ Tier 1: Manager         │
│ {tenant}:manager:tasks  │
└────────┬────────┬───────┘
         │        │
         │        └──────────────────┐
         ↓                           ↓
┌──────────────────┐      ┌──────────────────┐
│ Tier 2: Leads    │      │ Tier 2: Outreach │
│ {tenant}:leads:  │      │ {tenant}:outreach│
│        :tasks    │      │        :tasks    │
└────┬─────┬───────┘      └────┬─────┬───────┘
     │     │                   │     │
     │     └──────┐            │     └─────────────┐
     ↓            ↓            ↓                   ↓
┌────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│ RAG    │  │ Persist  │  │ Copy     │  │ Booking      │
│ Agent  │  │ Agent    │  │ Agent    │  │ Agent        │
└────────┘  └──────────┘  └──────────┘  └──────────────┘
  :tasks      :tasks        :tasks        :tasks
```

### Upstream Flow (Result Propagation)

```
┌────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│ RAG    │  │ Persist  │  │ Copy     │  │ Booking      │
│ Agent  │  │ Agent    │  │ Agent    │  │ Agent        │
└────┬───┘  └─────┬────┘  └─────┬────┘  └──────┬───────┘
  :results    :results      :results       :results
     │              │            │               │
     │              │            └───────────────┘
     └──────────────┘                    │
                │                        │
                ↓                        ↓
        ┌──────────────────┐      ┌──────────────────┐
        │ Tier 2: Leads    │      │ Tier 2: Outreach │
        │ {tenant}:leads:  │      │ {tenant}:outreach│
        │      :results    │      │      :results    │
        └────────┬─────────┘      └─────────┬────────┘
                 │                          │
                 └──────────────────────────┘
                              ↓
                ┌─────────────────────────┐
                │ Tier 1: Manager         │
                │ {tenant}:manager:results│
                └────────┬────────────────┘
                         ↓
                  External Response
```

### Cross-Cutting Streams

All components publish to system streams:

```
Any Component
    ├─> {tenant}:system:health    (Heartbeats every 10s)
    ├─> {tenant}:system:audit     (Important actions)
    ├─> {tenant}:system:metrics   (Performance data)
    └─> {tenant}:system:events    (State changes)

Failed Messages → {tenant}:system:dlq
```

---

## Stream Inventory

### Tier 1: Manager

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:manager:tasks` | External requests | `manager-workers` | 10k msgs, 48h |
| `{tenant}:manager:results` | Final responses | None (API reads) | 10k msgs, 48h |

**Data Flow**:
- **IN**: External API/webhooks
- **OUT**: `{tenant}:leads:tasks`, `{tenant}:outreach:tasks`

---

### Tier 2: Orchestrators

#### Leads Orchestrator

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:leads:tasks` | Lead workflows | `leads-workers` | 5k msgs, 24h |
| `{tenant}:leads:results` | Lead results | None | 5k msgs, 24h |

**Data Flow**:
- **IN**: `{tenant}:manager:tasks`
- **OUT**: `{tenant}:agents:rag:tasks`, `{tenant}:agents:persistence:tasks`, `{tenant}:agents:deduplication:tasks`

#### Outreach Orchestrator

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:outreach:tasks` | Campaign workflows | `outreach-workers` | 5k msgs, 24h |
| `{tenant}:outreach:results` | Campaign results | None | 5k msgs, 24h |

**Data Flow**:
- **IN**: `{tenant}:manager:tasks`
- **OUT**: `{tenant}:agents:copywriter:tasks`, `{tenant}:agents:booking:tasks`, `{tenant}:agents:sequencing:tasks`

---

### Tier 3: Agents

#### RAG Agent (Research & Enrichment)

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:agents:rag:tasks` | Enrichment requests | `rag-workers` | 20k msgs, 12h |
| `{tenant}:agents:rag:results` | Enriched data | None | 20k msgs, 12h |

**Data Flow**:
- **IN**: `{tenant}:leads:tasks`
- **OUT**: `{tenant}:leads:results`

#### Persistence Agent (Database)

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:agents:persistence:tasks` | Bulk DB operations | `persistence-workers` | 50k msgs, 6h |
| `{tenant}:agents:persistence:results` | Write confirmations | None | 10k msgs, 6h |

**Data Flow**:
- **IN**: `{tenant}:leads:tasks`
- **OUT**: `{tenant}:leads:results`

#### Copywriter Agent (Content)

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:agents:copywriter:tasks` | Content generation | `copywriter-workers` | 5k msgs, 24h |
| `{tenant}:agents:copywriter:results` | Generated content | None | 5k msgs, 24h |

**Data Flow**:
- **IN**: `{tenant}:outreach:tasks`
- **OUT**: `{tenant}:outreach:results`

#### Booking Agent (Calendar)

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:agents:booking:tasks` | Meeting scheduling | `booking-workers` | 3k msgs, 48h |
| `{tenant}:agents:booking:results` | Booking confirmations | None | 3k msgs, 48h |

**Data Flow**:
- **IN**: `{tenant}:outreach:tasks`
- **OUT**: `{tenant}:outreach:results`

#### Sequencing Agent (Optimization)

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:agents:sequencing:tasks` | Send optimization | `sequencing-workers` | 5k msgs, 24h |
| `{tenant}:agents:sequencing:results` | Optimized schedules | None | 5k msgs, 24h |

**Data Flow**:
- **IN**: `{tenant}:outreach:tasks`
- **OUT**: `{tenant}:outreach:results`

#### Deduplication Agent

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:agents:deduplication:tasks` | Duplicate detection | `deduplication-workers` | 5k msgs, 12h |
| `{tenant}:agents:deduplication:results` | Merge suggestions | None | 5k msgs, 12h |

**Data Flow**:
- **IN**: `{tenant}:leads:tasks`
- **OUT**: `{tenant}:leads:results`

---

### System Streams

| Stream | Purpose | Consumer Group | Retention |
|--------|---------|----------------|-----------|
| `{tenant}:system:dlq` | Failed messages | `dlq-handlers` | 100k msgs, 7d |
| `{tenant}:system:events` | System events | `event-processors` | 50k msgs, 3d |
| `{tenant}:system:health` | Heartbeats | `health-monitors` | 10k msgs, 1d |
| `{tenant}:system:audit` | Audit trail | `audit-processors` | 100k msgs, 30d |
| `{tenant}:system:metrics` | Performance data | `metrics-collectors` | 50k msgs, 2d |

---

## Implementation Guide

### 1. Using the Stream Registry

```python
from services.redis.stream_registry import get_registry, Tier, StreamType

# Get the registry
registry = get_registry()

# Get a stream key
rag_tasks = registry.get_stream_key(
    Tier.AGENT, 
    "rag", 
    StreamType.TASKS, 
    tenant_id="agentic-dev"
)
# Returns: "agentic-dev:agents:rag:tasks"

# Get stream metadata
stream_def = registry.get(Tier.AGENT, "rag", StreamType.TASKS)
print(f"Max length: {stream_def.max_len}")
print(f"Consumer group: {stream_def.consumer_group}")
print(f"Description: {stream_def.description}")

# Get downstream streams (where results go)
downstream = registry.get_downstream_streams(
    Tier.AGENT, "rag", StreamType.RESULTS, "agentic-dev"
)
# Returns: ["agentic-dev:leads:results"]

# Visualize data flow
print(registry.visualize_data_flow("agentic-dev"))
```

### 2. Consumer Implementation Pattern

```python
from services.redis.stream_registry import get_registry, Tier, StreamType
import redis

class RAGConsumer:
    def __init__(self, redis_client, tenant_id: str):
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.registry = get_registry()
        
        # Get stream keys from registry
        self.task_stream = self.registry.get_stream_key(
            Tier.AGENT, "rag", StreamType.TASKS, tenant_id
        )
        self.result_stream = self.registry.get_stream_key(
            Tier.AGENT, "rag", StreamType.RESULTS, tenant_id
        )
        
        # Get consumer group from stream definition
        stream_def = self.registry.get(Tier.AGENT, "rag", StreamType.TASKS)
        self.consumer_group = stream_def.consumer_group
        self.consumer_name = f"rag-worker-{os.getpid()}"
        
        # Create consumer group
        self._ensure_consumer_group()
    
    def _ensure_consumer_group(self):
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

### 3. Publishing Messages

```python
from services.redis.stream_registry import get_registry, Tier, StreamType
import json

def publish_enrichment_task(redis_client, tenant_id: str, lead_id: str, query: str):
    """Publish a task to RAG agent"""
    registry = get_registry()
    
    # Get target stream
    stream_key = registry.get_stream_key(
        Tier.AGENT, "rag", StreamType.TASKS, tenant_id
    )
    
    # Get stream definition for MAXLEN
    stream_def = registry.get(Tier.AGENT, "rag", StreamType.TASKS)
    
    # Publish message
    message_id = redis_client.xadd(
        stream_key,
        {
            "task_id": f"enrich_{lead_id}",
            "lead_id": lead_id,
            "query": query,
            "timestamp": datetime.utcnow().isoformat()
        },
        maxlen=stream_def.max_len
    )
    
    return message_id
```

### 4. Stream Initialization

```python
from services.redis.stream_registry import get_registry
import redis

def initialize_streams(redis_client, tenant_id: str):
    """Initialize all streams for a tenant"""
    registry = get_registry()
    
    # Get all streams for tenant
    all_streams = registry.get_all_streams(tenant_id)
    
    for stream_name, stream_key in all_streams.items():
        stream_def = registry._streams[stream_name]
        
        # Create consumer group if defined
        if stream_def.consumer_group:
            try:
                redis_client.xgroup_create(
                    stream_key,
                    stream_def.consumer_group,
                    id="0",
                    mkstream=True
                )
                print(f"✓ Created {stream_key} with group {stream_def.consumer_group}")
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    print(f"✓ {stream_key} already exists")
                else:
                    print(f"✗ Error creating {stream_key}: {e}")
```

---

## Migration from Legacy

### Current Issues

The system currently has multiple naming conventions:
1. Old streams: `{tenant}:rag:tasks`
2. Some consumers listening to: `{tenant}:orchestrators:leads:tasks`
3. Manager delegating to: `{tenant}:leads:tasks`

### Migration Steps

#### Phase 1: Update Consumers (✅ DONE)
- Updated Leads consumer to listen to `{tenant}:leads:tasks`
- Updated Outreach consumer to listen to `{tenant}:outreach:tasks`

#### Phase 2: Integrate Stream Registry (IN PROGRESS)
1. Update all consumers to use `StreamRegistry`
2. Remove hardcoded stream names
3. Use registry for all stream operations

#### Phase 3: Migrate Old Streams
For legacy streams that don't match the new convention:

```python
def migrate_stream(redis_client, old_stream: str, new_stream: str):
    """
    Migrate messages from old stream naming to new.
    
    This reads all messages from old stream and copies to new stream,
    then optionally deletes the old stream.
    """
    messages = redis_client.xrange(old_stream, "-", "+", count=1000)
    
    for msg_id, fields in messages:
        # Copy to new stream
        redis_client.xadd(new_stream, fields)
    
    print(f"Migrated {len(messages)} messages from {old_stream} to {new_stream}")
    
    # Optional: Delete old stream after verification
    # redis_client.delete(old_stream)
```

#### Phase 4: Update Documentation
- Update all references to use new naming
- Remove contradictory documentation
- Mark old docs as deprecated

---

## Monitoring & Operations

### Health Checks

```python
from services.redis.stream_registry import get_registry

def check_stream_health(redis_client, tenant_id: str):
    """Check health of all streams"""
    registry = get_registry()
    all_streams = registry.get_all_streams(tenant_id)
    
    health = {}
    for name, stream_key in all_streams.items():
        try:
            length = redis_client.xlen(stream_key)
            info = redis_client.xinfo_stream(stream_key)
            health[stream_key] = {
                "status": "healthy",
                "length": length,
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry")
            }
        except Exception as e:
            health[stream_key] = {
                "status": "error",
                "error": str(e)
            }
    
    return health
```

### Consumer Group Monitoring

```python
def monitor_consumer_groups(redis_client, tenant_id: str):
    """Monitor consumer group lag"""
    registry = get_registry()
    
    # Get all streams with consumer groups
    for name, stream_def in registry._streams.items():
        if stream_def.consumer_group:
            stream_key = stream_def.get_key(tenant_id)
            
            try:
                # Get pending messages
                pending = redis_client.xpending(stream_key, stream_def.consumer_group)
                
                if pending and pending[0] > 0:
                    print(f"⚠ {stream_key}: {pending[0]} pending messages")
                    
                    # Get detailed pending info
                    details = redis_client.xpending_range(
                        stream_key, 
                        stream_def.consumer_group,
                        "-", "+", 10
                    )
                    
                    for msg in details:
                        print(f"  - Message {msg['message_id']}: "
                              f"delivered {msg['times_delivered']} times, "
                              f"idle {msg['time_since_delivered']}ms")
            except Exception as e:
                print(f"✗ Error checking {stream_key}: {e}")
```

### Data Flow Visualization

```bash
# Run from command line
python -c "
from services.redis.stream_registry import get_registry
registry = get_registry()
print(registry.visualize_data_flow('agentic-dev'))
"
```

### Stream Metrics

```python
def get_stream_metrics(redis_client, tenant_id: str):
    """Get metrics for all streams"""
    registry = get_registry()
    metrics = {}
    
    for name, stream_def in registry._streams.items():
        stream_key = stream_def.get_key(tenant_id)
        
        try:
            info = redis_client.xinfo_stream(stream_key)
            metrics[stream_key] = {
                "length": info["length"],
                "radix_tree_keys": info["radix-tree-keys"],
                "radix_tree_nodes": info["radix-tree-nodes"],
                "groups": info["groups"],
                "last_generated_id": info["last-generated-id"]
            }
        except:
            metrics[stream_key] = None
    
    return metrics
```

---

## References

- **Implementation**: `services/redis/stream_registry.py`
- **Tests**: `tests/integration/test_stream_registry.py` (to be created)
- **Migration Script**: `scripts/migration/migrate_redis_streams.py` (to be created)

---

## Appendix: Quick Reference

### Manager Streams
```
{tenant}:manager:tasks      # External requests IN
{tenant}:manager:results    # Final results OUT
```

### Orchestrator Streams
```
{tenant}:leads:tasks        # Lead workflows IN
{tenant}:leads:results      # Lead results OUT
{tenant}:outreach:tasks     # Campaign workflows IN
{tenant}:outreach:results   # Campaign results OUT
```

### Agent Streams
```
{tenant}:agents:rag:tasks              # Enrichment IN
{tenant}:agents:rag:results            # Enrichment OUT
{tenant}:agents:persistence:tasks      # DB operations IN
{tenant}:agents:persistence:results    # DB results OUT
{tenant}:agents:copywriter:tasks       # Content gen IN
{tenant}:agents:copywriter:results     # Content OUT
{tenant}:agents:booking:tasks          # Scheduling IN
{tenant}:agents:booking:results        # Bookings OUT
{tenant}:agents:sequencing:tasks       # Optimization IN
{tenant}:agents:sequencing:results     # Schedules OUT
{tenant}:agents:deduplication:tasks    # Dedup IN
{tenant}:agents:deduplication:results  # Dedup OUT
```

### System Streams
```
{tenant}:system:dlq        # Failed messages
{tenant}:system:events     # System events
{tenant}:system:health     # Heartbeats
{tenant}:system:audit      # Audit trail
{tenant}:system:metrics    # Performance
```

---

**Last Updated**: November 22, 2025  
**Status**: Active and Authoritative  
**Supersedes**: All previous Redis architecture documents
