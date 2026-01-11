# Redis Implementation Status & Architecture Analysis
**Date:** November 20, 2025
**Status:** Analysis of Current Implementation vs. Target Architecture

## 1. Executive Summary
The current Redis implementation provides a functional foundation with `TypedEnvelope` messaging and consumer groups, but suffers from a significant divergence between the **implemented code** (flat, simple naming) and the **documented architecture** (hierarchical, multi-tenant naming).

To achieve the scalable MVP, we must align the implementation with the hierarchical design to support multi-tenancy and proper tier separation.

---

## 2. Current Implementation (The "As-Is")

### 2.1 Stream Configuration (`services/redis/streams.py`)
The current codebase uses simplified, flat stream names.

| Constant | Value | Purpose |
|----------|-------|---------|
| `STREAM_TASKS` | `rag:tasks` | RAG Agent input |
| `STREAM_RESULTS` | `rag:results` | RAG Agent output |
| `STREAM_TASKS_WRITE` | `persist:tasks` | Persistence Agent input |
| `STREAM_TASKS_COPY` | `copy:tasks` | Copywriter Agent input |

**Consumer Groups:**
- `rag-workers` (for RAG)
- `persist-writers` (for Persistence)
- `copy-writers` (for Copywriter)

**Operational Settings:**
- Namespace: `agentic` (Configurable via `REDIS_NAMESPACE`)
- Max Retries: 2
- DLQ Enabled: Yes
- Heartbeats: `ops:hb`
- Idempotency: `ops:idemp` (TTL 24h)

### 2.2 Message Envelope (`core/envelope/typed_envelope.py`)
The message structure is robust and production-ready.

**Structure:**
```python
class Envelope(BaseModel):
    metadata: Metadata
    payload: Dict[str, Any]
    status: Status = Status.PENDING
    error: Optional[Error] = None
    warnings: List[Warning] = []
    trace: Optional[TraceSpan] = None
```

**Metadata Fields:**
- `message_id`: UUID
- `correlation_id`: UUID (Critical for tracing flows)
- `tenant_id`: String
- `priority`: Enum (LOW, NORMAL, HIGH, CRITICAL)
- `source` / `destination`: Component identifiers

**Lifecycle Status:**
`PENDING` → `SUCCESS` | `ERROR` → `RETRY` → `DLQ`

### 2.3 The Discrepancy
There is a critical gap between code and documentation.

| Feature | Implemented (`streams.py`) | Documented (`redis-naming.md`) |
|---------|----------------------------|--------------------------------|
| **Naming** | Flat (`rag:tasks`) | Hierarchical (`{tenant}:agents:rag:tasks`) |
| **Tiers** | Mixed/Flat | Strict (`manager`, `orchestrators`, `agents`) |
| **Tenancy** | Implicit/Missing in key | Explicit prefix (`{tenant}:...`) |

> **Note in Code:** `services/redis/streams.py` explicitly states: *"KEEP NOTE OF THIS AS WE WILL NEED TO CHANGE THE GROUPINGS AND STREAMS LATER ONCE WE HAVE MULTIPLE STREAMS"*

---

## 3. Target Architecture (The "To-Be")

To support the MVP with Manager, Orchestrators, and Agents, we must migrate to the hierarchical pattern.

### 3.1 Stream Topology
**Tier 1: Manager**
- `acme:manager:tasks` (Inbound requests)
- `acme:manager:results` (Final responses)

**Tier 2: Orchestrators**
- `acme:orchestrators:leads:tasks` / `:results`
- `acme:orchestrators:outreach:tasks` / `:results`
- `acme:orchestrators:audit:tasks` / `:results` (Future)

**Tier 3: Agents**
- `acme:agents:rag:tasks` / `:results`
- `acme:agents:persistence:tasks` / `:results`
- `acme:agents:copywriter:tasks` / `:results`
- `acme:agents:booking:tasks` / `:results`

### 3.2 Consumer Group Strategy
Horizontal scaling is achieved by attaching consumer groups to the `:tasks` streams.

| Component | Stream | Consumer Group |
|-----------|--------|----------------|
| **Manager** | `...:manager:tasks` | `manager-workers` |
| **Leads Orch** | `...:leads:tasks` | `leads-workers` |
| **Outreach Orch** | `...:outreach:tasks` | `outreach-workers` |
| **RAG Agent** | `...:rag:tasks` | `rag-workers` |

---

## 4. Communication Flows

### 4.1 Delegation Flow (Manager → Orchestrator → Agent)
1. **Manager** receives request, generates `correlation_id`.
2. **Manager** delegates to **Leads Orchestrator**:
   - Writes to `{tenant}:orchestrators:leads:tasks`
   - Preserves `correlation_id`.
3. **Leads Orchestrator** processes, needs RAG:
   - Writes to `{tenant}:agents:rag:tasks`
   - Preserves `correlation_id`.
4. **RAG Agent** completes work:
   - Writes to `{tenant}:agents:rag:results`
5. **Leads Orchestrator** reads result, aggregates:
   - Writes to `{tenant}:orchestrators:leads:results`
6. **Manager** reads result, finalizes.

### 4.2 Envelope Propagation
The `TypedEnvelope` is designed for this. When delegating:
- **New Envelope** is created for the downstream task.
- **Metadata** is copied/linked:
  - `correlation_id` is passed through.
  - `parent_id` (if we add it) points to the upstream message ID.
  - `priority` is inherited.

---

## 5. Migration Plan for MVP

1. **Update `streams.py`**: Deprecate flat constants, add dynamic key builders matching the documentation.
2. **Update Consumers**: Modify `__init__` in all consumers to use the new dynamic stream names based on `tenant_id`.
3. **Migration Script**: (Optional) If we have live data, we need to drain old streams. For dev, we can flush.

### Required Code Changes
- **`services/redis/streams.py`**: Add `StreamKeyBuilder` class.
- **`tiers/tier_*/.../consumer.py`**: Update to use `StreamKeyBuilder`.
