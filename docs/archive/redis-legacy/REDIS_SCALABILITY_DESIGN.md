# Redis Scalability & Stream Topology Design
**Date:** November 20, 2025
**Status:** Design Specification

## 1. Core Design Principles
To ensure the Agentic System is scalable, multi-tenant, and observable, we are adopting the following Redis Streams architecture.

1. **Hierarchical Naming:** `{tenant}:{tier}:{component}:{type}`
2. **Consumer Groups:** Horizontal scaling via competing consumers.
3. **Strict Typing:** All messages must be `TypedEnvelope` objects.
4. **Stream Isolation:** Separate streams for Tasks (Input) and Results (Output).

---

## 2. Stream Topology Specification

### 2.1 Naming Convention
The system will use a dynamic key builder pattern.

**Format:**
`{tenant_id}:{tier_prefix}:{component_name}:{stream_type}`

**Definitions:**
- `tenant_id`: Unique tenant identifier (e.g., "acme", "default").
- `tier_prefix`:
  - Tier 1: `manager`
  - Tier 2: `orchestrators`
  - Tier 3: `agents`
- `component_name`: Service identifier (e.g., `leads`, `rag`).
- `stream_type`: `tasks` | `results` | `dlq`

### 2.2 Stream Inventory (MVP)

#### Tier 1: Manager
| Stream Key | Purpose | Consumers | Retention (MAXLEN) |
|------------|---------|-----------|--------------------|
| `{t}:manager:tasks` | Inbound requests | `manager-workers` | 10,000 |
| `{t}:manager:results` | Final outcomes | API Gateway / Client | 10,000 |

#### Tier 2: Orchestrators
| Stream Key | Purpose | Consumers | Retention |
|------------|---------|-----------|-----------|
| `{t}:orchestrators:leads:tasks` | Lead gen workflows | `leads-workers` | 5,000 |
| `{t}:orchestrators:leads:results` | Lead gen outcomes | Manager | 5,000 |
| `{t}:orchestrators:outreach:tasks` | Campaign workflows | `outreach-workers` | 5,000 |
| `{t}:orchestrators:outreach:results` | Campaign outcomes | Manager | 5,000 |

#### Tier 3: Agents
| Stream Key | Purpose | Consumers | Retention |
|------------|---------|-----------|-----------|
| `{t}:agents:rag:tasks` | Knowledge retrieval | `rag-workers` | 20,000 |
| `{t}:agents:rag:results` | Retrieval results | Orchestrators | 20,000 |
| `{t}:agents:persistence:tasks` | DB writes | `persist-workers` | 50,000 |
| `{t}:agents:persistence:results` | Write confirmations | Orchestrators | 10,000 |
| `{t}:agents:copywriter:tasks` | Content generation | `copy-workers` | 5,000 |
| `{t}:agents:copywriter:results` | Generated content | Orchestrators | 5,000 |

---

## 3. Scalability Strategy

### 3.1 Consumer Groups
Each service will define a consumer group. This allows us to run multiple instances of any agent to increase throughput.

**Configuration:**
- **Group Name:** `{component}-workers` (e.g., `rag-workers`)
- **Consumer Name:** `{hostname}-{pid}-{uuid}` (Unique per instance)
- **Prefetch Count:**
  - CPU-bound agents (RAG, Copy): 1-5 messages
  - IO-bound agents (Persistence): 10-50 messages

### 3.2 Auto-Scaling Triggers
We can scale workers based on the **Lag** metric (Pending messages).

**Scaling Rules (Example):**
- If `rag:tasks` lag > 100 for 1 min → Scale RAG workers +1
- If `rag:tasks` lag < 10 for 5 min → Scale RAG workers -1

### 3.3 Multi-Tenancy
- **Isolation:** Achieved via the `{tenant_id}` prefix.
- **Scaling:** High-volume tenants can be moved to dedicated Redis clusters if needed (sharding by tenant).

---

## 4. Implementation Guide

### 4.1 The `StreamKeyBuilder` Class
We will replace the static constants in `streams.py` with this utility.

```python
class StreamKeyBuilder:
    @staticmethod
    def make(tenant_id: str, tier: str, component: str, stream_type: str) -> str:
        return f"{tenant_id}:{tier}:{component}:{stream_type}"

    @staticmethod
    def manager_tasks(tenant_id: str) -> str:
        return f"{tenant_id}:manager:tasks"

    @staticmethod
    def orchestrator_tasks(tenant_id: str, orchestrator: str) -> str:
        return f"{tenant_id}:orchestrators:{orchestrator}:tasks"

    @staticmethod
    def agent_tasks(tenant_id: str, agent: str) -> str:
        return f"{tenant_id}:agents:{agent}:tasks"
```

### 4.2 Retention Policy
We will use `XADD ... MAXLEN ~ 10000` to prevent streams from growing indefinitely. The `~` (approximate) modifier is crucial for Redis performance.

### 4.3 Dead Letter Queue (DLQ)
Failed messages (after retries) are moved to a dedicated DLQ stream:
`{tenant}:system:dlq`
This allows for manual inspection and replay without blocking the main processing pipelines.
