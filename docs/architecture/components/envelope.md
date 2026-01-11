# Envelope System — Unified Messaging Contract

## Overview

All agents communicate via a standardized **Envelope** (Pydantic model) that wraps task payloads with routing metadata, retry/DLQ state, and optional tracing context. This ensures type safety, audit trails, and seamless context forwarding across multi-agent pipelines.

## Core concepts

**Stateless workers**: Each envelope is self-contained—workers get everything they need from the payload without external lookups.

**Context forwarding**: Orchestrator includes instructions for downstream agents (e.g., RAG → Copywriter) in `payload.forward_to`.

**Correlation IDs**: Link related messages across streams for end-to-end tracing.

**Retry/DLQ lifecycle**: Envelopes track `retry_count` and auto-promote to DLQ when `max_retries` is exceeded.

---

## Envelope schema

### Metadata
```python
class Metadata(BaseModel):
    # Identity
    message_id: str          # Unique per envelope (UUID)
    task_id: str             # Unique per logical task
    correlation_id: str      # Groups related tasks (e.g., batch)
    
    # Routing
    source: str              # "orchestrator", "rag_worker", "copy_worker"
    destination: str | None  # Target stream (e.g., "rag:tasks")
    
    # Timing
    created_at: datetime
    processed_at: datetime | None
    
    # Context (multi-tenancy, campaign tracking)
    req_id: str | None
    user_id: str | None
    tenant_id: str | None
    campaign_id: str | None
    
    # Operations
    priority: Priority       # LOW | NORMAL | HIGH | CRITICAL
    retry_count: int
    max_retries: int
    tags: Dict[str, str]
```

### Envelope
```python
class Envelope(BaseModel):
    metadata: Metadata
    payload: Dict[str, Any]  # Domain-specific task data
    status: Status           # PENDING | SUCCESS | ERROR | RETRY | DLQ
    error: str | None
    error_code: str | None   # e.g., "23505" for duplicate key
    warnings: List[str]
    trace: TraceSpan | None  # Optional distributed tracing
```

---

## Builder functions

### Creating tasks
```python
from agent.utils.typed_envelope import task

envelope = task(
    source="orchestrator",
    task_id="insert-lead-abc",
    destination="persist:tasks",
    payload={
        "op": "insert",
        "table": "leads",
        "values": {"email": "john@acme.com", "first_name": "John"}
    },
    correlation_id="batch-001",
    campaign_id="9646f98a-e987-4a8c-b786-9b82ea985d38",
    priority=Priority.NORMAL
)
```

### Creating results
```python
from agent.utils.typed_envelope import result

result_envelope = result(
    original=task_envelope,
    payload={"id": "75991643-a653-43eb-8220-0ed9f03bc25f", "status": "inserted"},
    source="persist_worker"
)
```

### Creating errors
```python
from agent.utils.typed_envelope import error

error_envelope = error(
    original=task_envelope,
    error_msg="duplicate key value violates unique constraint",
    source="persist_worker",
    code="23505"
)
error_envelope.increment_retry()  # Bumps retry_count; sets status=DLQ if exhausted
```

---

## Context forwarding (Orchestrator → RAG → Copywriter)

### Orchestrator creates RAG task with forwarding instructions
```python
rag_envelope = task(
    source="orchestrator",
    task_id=f"fetch-{lead_id}",
    destination="rag:tasks",
    payload={
        "query": {
            "table": "leads",
            "filters": {"id": lead_id},
            "columns": ["email", "first_name", "company_name"]
        },
        "forward_to": {  # ← Instructions for downstream agent
            "agent": "copywriter",
            "campaign_context": {
                "campaign_name": "Q4 Outreach",
                "previous_subject": "Partnership Opportunity",
                "days_since_last_contact": 7
            },
            "instructions": {
                "tone": "professional_friendly",
                "language": "en-GB",
                "max_length": 200,
                "cta": "book a quick call",
                "template_id": "followup_step3_v2"
            }
        }
    },
    correlation_id="batch-001",
    campaign_id="9646f98a-..."
)
```

### RAG worker forwards fetched data + instructions to copywriter
```python
# RAG fetches lead data
lead_data = rag_agent.query(...)

# RAG creates copywriter task from original envelope's forward_to
copy_envelope = task(
    source="rag_worker",
    task_id=f"copy-{lead_id}",
    destination="copy:tasks",
    payload={
        "lead_data": lead_data[0],  # Fetched record
        "campaign_context": rag_envelope.payload["forward_to"]["campaign_context"],
        "instructions": rag_envelope.payload["forward_to"]["instructions"]
    },
    correlation_id=rag_envelope.metadata.correlation_id,
    campaign_id=rag_envelope.metadata.campaign_id,
    tags={**rag_envelope.metadata.tags, "parent_task_id": rag_envelope.metadata.task_id}
)
```

### Copywriter processes with full context
```python
def process_copy_task(envelope: Envelope):
    lead = envelope.payload["lead_data"]
    campaign = envelope.payload["campaign_context"]
    inst = envelope.payload["instructions"]
    
    # Build LLM prompt
    prompt = f"""
You are writing a {inst['tone']} follow-up email.

Lead: {lead['first_name']} at {lead['company_name']}
Previous contact: {campaign['days_since_last_contact']} days ago
Previous subject: "{campaign['previous_subject']}"

Tone: {inst['tone']}
Language: {inst['language']}
Max length: {inst['max_length']} words
CTA: {inst['cta']}
"""
    
    # Generate copy (placeholder; replace with LLM call)
    subject = f"Following up: {campaign['previous_subject']}"
    body = f"Hi {lead['first_name']},\n\n..."
    
    return result(
        original=envelope,
        payload={
            "subject": subject,
            "body": body,
            "metadata": {"model": "gpt-4", "tokens": 150}
        },
        source="copy_worker"
    )
```

---

## Redis integration

### Serialize for XADD
```python
from agent.utils.typed_envelope import to_redis_fields

redis.xadd("persist:tasks", to_redis_fields(envelope), maxlen=1000)
```

### Parse from XREADGROUP
```python
from agent.utils.typed_envelope import from_redis_message

for stream, entries in redis.xreadgroup(...):
    for msg_id, fields in entries:
        envelope = from_redis_message(fields)
        # Process envelope...
```

---

## Retry and DLQ handling

### Worker retries with backoff
```python
retries = 0
while True:
    try:
        result = process_task(envelope)
        publish_result(result)
        ack_message(msg_id)
        break
    except Exception as e:
        if retries < envelope.metadata.max_retries:
            retries += 1
            time.sleep(backoff_ms / 1000.0)
            continue
        
        # Exhausted retries → DLQ
        error_env = error(envelope, str(e), source="worker", code=getattr(e, 'code', None))
        error_env.increment_retry()
        
        if error_env.status == Status.DLQ:
            redis.xadd("persist:dlq", to_redis_fields(error_env))
        else:
            redis.xadd("persist:results", to_redis_fields(error_env))
        
        ack_message(msg_id)
        break
```

---

## Example: Full pipeline (Orchestrator → RAG → Copywriter)

### 1. Orchestrator command
```json
{
  "type": "campaign_followup_batch",
  "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
  "lead_ids": ["75991643-a653-43eb-8220-0ed9f03bc25f"],
  "step": 3
}
```

### 2. Orchestrator → RAG (rag:tasks)
```json
{
  "metadata": {
    "message_id": "uuid-1",
    "task_id": "fetch-75991643",
    "correlation_id": "batch-001",
    "source": "orchestrator",
    "destination": "rag:tasks",
    "campaign_id": "9646f98a-...",
    "tags": {"workflow": "followup", "step": "3"}
  },
  "payload": {
    "query": {
      "table": "leads",
      "filters": {"id": "75991643-a653-43eb-8220-0ed9f03bc25f"}
    },
    "forward_to": {
      "agent": "copywriter",
      "campaign_context": {...},
      "instructions": {...}
    }
  },
  "status": "pending"
}
```

### 3. RAG → Copywriter (copy:tasks)
```json
{
  "metadata": {
    "message_id": "uuid-2",
    "task_id": "copy-75991643",
    "correlation_id": "batch-001",  // ← Same correlation
    "source": "rag_worker",
    "destination": "copy:tasks",
    "campaign_id": "9646f98a-...",
    "tags": {"parent_task_id": "fetch-75991643"}
  },
  "payload": {
    "lead_data": {
      "id": "75991643-...",
      "email": "john.doe@acme.com",
      "first_name": "John",
      "company_name": "Acme Corp"
    },
    "campaign_context": {...},  // ← Forwarded from orchestrator
    "instructions": {...}       // ← Forwarded from orchestrator
  },
  "status": "pending"
}
```

### 4. Copywriter → Results (copy:results)
```json
{
  "metadata": {
    "message_id": "uuid-3",
    "task_id": "copy-75991643",
    "correlation_id": "batch-001",  // ← Same correlation
    "source": "copy_worker",
    "processed_at": "2024-10-26T14:30:00.567890Z"
  },
  "payload": {
    "subject": "Following up: Partnership at Acme Corp",
    "body": "Hi John,\n\n...",
    "metadata": {"model": "gpt-4", "tokens": 150}
  },
  "status": "success"
}
```

---

## Migration guide

### Phase 1: New code (orchestrator, copywriter)
Use enhanced envelope exclusively. No backward compatibility needed.

### Phase 2: Existing workers (RAG, persist)
Add adapter to accept both old and new formats:
```python
def parse_message(fields):
    try:
        return from_redis_message(fields)  # New envelope
    except Exception:
        # Fallback to legacy JSON parsing
        data = json.loads(fields.get("data", "{}"))
        return legacy_to_envelope(data)
```

### Phase 3: Remove legacy
Once all enqueues use new envelope, remove adapters and old envelope helpers.

---

## Benefits

- **Type safety**: Pydantic catches schema errors at parse time
- **Audit trail**: Full context in every message; easy DLQ replay
- **Scalability**: Stateless workers; horizontal scaling trivial
- **Debuggability**: `streams_health.py` shows full payloads with context
- **A/B testing**: Variant in `instructions.variant`; easy to split traffic
- **Multi-tenancy**: `tenant_id`, `campaign_id` in metadata
- **Distributed tracing**: Optional `trace` field for OpenTelemetry integration

---

## Quick reference

| Task | Function | Example |
|------|----------|---------|
| Create task | `task(source, task_id, payload, ...)` | `task("orch", "t1", {...})` |
| Create result | `result(original, payload, source)` | `result(env, {...}, "worker")` |
| Create error | `error(original, msg, source, code)` | `error(env, "fail", "w", "23505")` |
| Serialize | `to_redis_fields(envelope)` | `redis.xadd(stream, to_redis_fields(env))` |
| Parse | `from_redis_message(fields)` | `env = from_redis_message(fields)` |
| Retry | `envelope.increment_retry()` | Bumps count; sets DLQ if exhausted |
| Mark done | `envelope.mark_processed()` | Sets `processed_at`, `status=SUCCESS` |

---

## Future Enhancements

*Note: All current functionality works correctly. These are quality-of-life and future-proofing enhancements, not bugs.*

### 1. Pydantic V2 Migration
**Current**: Pydantic V1 (23 deprecation warnings)  
**Enhancement**: Migrate to Pydantic V2 for performance and better validation  
**Effort**: Medium  
**Benefit**: Removes deprecation warnings, 5-50x faster validation

```python
# Changes needed:
Config → model_config
allow_mutation=False → frozen=True
```

### 2. Timezone-Aware Datetimes
**Current**: Naive datetimes (18 warnings in Python 3.13+)  
**Enhancement**: Use `datetime.now(timezone.utc)` instead of `datetime.utcnow()`  
**Effort**: Low (find/replace)  
**Benefit**: Python 3.13 compatibility, explicit timezone handling

```python
# Before:
created_at: datetime = datetime.utcnow()

# After:
created_at: datetime = datetime.now(timezone.utc)
```

### 3. Envelope Versioning
**Current**: No schema version tracking  
**Enhancement**: Add `schema_version` field to metadata  
**Benefit**: Safe schema evolution without breaking consumers

```python
class Metadata(BaseModel):
    schema_version: str = "1.0"  # NEW
    message_id: str
    # ...existing fields...
```

### 4. Payload Type Validation
**Current**: `payload: Dict[str, Any]` (no validation)  
**Enhancement**: Typed schemas per worker  
**Benefit**: Catch errors at envelope creation, not processing time

```python
# Discriminated union:
PayloadType = Union[
    RAGPayload,
    CopywriterPayload,
    PersistencePayload
]

class Envelope(BaseModel):
    payload: PayloadType  # Type-checked!
```

### 5. Result/Error Type Safety
**Current**: `error: str | None`  
**Enhancement**: Structured error with category, retryable flag, suggested action

```python
class ErrorDetail(BaseModel):
    code: str               # e.g., "DB_TIMEOUT"
    category: str           # e.g., "TRANSIENT", "PERMANENT"
    retryable: bool
    message: str
    suggested_action: Optional[str] = None
```

### 6. Trace Span Activation
**Current**: `trace: TraceSpan | None` (passive field)  
**Enhancement**: Active OpenTelemetry integration  
**Benefit**: Automatic distributed tracing with context propagation

```python
# Hook pattern:
with envelope.activate_trace_span():
    # Processing happens inside span
    result = process_task(envelope)
```

### 7. Envelope Compression
**Current**: No compression  
**Enhancement**: gzip for large payloads (>10KB)  
**Benefit**: Reduced Redis memory, faster network transfer

```python
class Metadata(BaseModel):
    compressed: bool = False  # Flag for decompression
    # If True, decompress payload before parsing
```

### 8. Envelope Size Limits
**Current**: No validation  
**Enhancement**: Reject envelopes >1MB  
**Benefit**: Prevent memory issues, enforce chunking for large data

```python
def validate_envelope_size(envelope: Envelope):
    size_bytes = len(json.dumps(envelope.dict()).encode('utf-8'))
    if size_bytes > 1_000_000:
        raise ValueError(f"Envelope too large: {size_bytes} bytes")
```

### 9. Better Error Context
**Current**: `error: str`  
**Enhancement**: Attach full traceback, stack frames  
**Benefit**: Easier debugging of failures

```python
class Metadata(BaseModel):
    error_traceback: Optional[str] = None
    error_context: Optional[Dict[str, Any]] = None  # Local variables at failure
```

### 10. Metrics Hooks
**Current**: No instrumentation  
**Enhancement**: Add callbacks for envelope lifecycle events  
**Benefit**: Easy integration with Prometheus/DataDog

```python
# Hook pattern:
def on_envelope_created(envelope: Envelope): ...
def on_envelope_processed(envelope: Envelope, duration_ms: float): ...
def on_envelope_error(envelope: Envelope, error: Exception): ...
```

### Priority Assessment

**High Value, Low Effort:**
- Timezone-aware datetimes (fixes Python 3.13 deprecation)
- Envelope size limits (prevent memory issues)

**High Value, Medium Effort:**
- Pydantic V2 migration (removes all deprecation warnings)
- Payload type validation (catch errors earlier)
- Trace span activation (observability)

**Low Priority:**
- Envelope compression (only needed at scale)
- Advanced error context (current error handling sufficient)
- Metrics hooks (implement when observability priority comes up)

---

**Last Updated:** November 9, 2025  
**Current Status:** Fully functional with V1 schema
