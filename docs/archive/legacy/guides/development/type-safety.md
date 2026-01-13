# Type Safety with Pydantic Schemas

## Overview

This module provides comprehensive type-safe schemas for all agent payloads, configurations, and validation utilities using Pydantic v2.

## Quick Start

```python
from agent.schemas import RAGTaskPayload, QuerySpec, validate_payload

# Create a validated task
task = RAGTaskPayload(
    query=QuerySpec(
        table="leads",
        filters={"email": {"ilike": "%@example.com"}},
        limit=50
    )
)

# Access with full IDE autocomplete
print(task.query.table)  # "leads"
print(task.query.limit)  # 50

# Validate raw dict
raw_payload = {"query": {"table": "leads", "filters": {}}}
validated = validate_payload(raw_payload, RAGTaskPayload)
```

## Available Schemas

### RAG Agent Schemas

```python
from agent.schemas import RAGTaskPayload, RAGResultPayload, QuerySpec

# Task payload
task = RAGTaskPayload(
    query=QuerySpec(
        table="leads",
        filters={"email": "john@example.com"},
        limit=100,
        order_by="created_at",
        descending=True,
        columns=["id", "email", "name"]
    ),
    forward_to=ForwardSpec(
        agent="copywriter",
        campaign_context={"campaign_id": "camp-123"},
        instructions={"template": "cold_email"}
    ),
    timeout_ms=30000
)

# Result payload
result = RAGResultPayload(
    records=[{"id": "lead-123", "email": "john@example.com"}],
    count=1,
    table="leads",
    query_time_ms=45.2,
    cached=False
)
```

### Copywriter Agent Schemas

```python
from agent.schemas import (
    CopywriterTaskPayload,
    LeadData,
    CampaignContext,
    CopyInstructions,
    CopyTone,
    CopyTemplate
)

# Task payload
task = CopywriterTaskPayload(
    lead_data=LeadData(
        id="lead-123",
        email="john@example.com",
        name="John Doe",
        company="Acme Corp",
        title="VP of Engineering"
    ),
    campaign_context=CampaignContext(
        campaign_id="camp-123",
        variant="A",
        sequence_step=1,
        product_name="AI Platform",
        value_proposition="Automate 80% of customer support"
    ),
    instructions=CopyInstructions(
        template=CopyTemplate.COLD_EMAIL,
        tone=CopyTone.PROFESSIONAL,
        word_count=150,
        personalization_level=4
    )
)

# Result payload
from agent.schemas import CopywriterResultPayload, GeneratedCopy

result = CopywriterResultPayload(
    generated_copy=GeneratedCopy(
        subject="Quick question about Acme Corp",
        body="Hi John,\n\nI noticed...",
        word_count=147
    ),
    lead_id="lead-123",
    campaign_id="camp-123",
    generation_time_ms=3200
)
```

### Persistence Agent Schemas

```python
from agent.schemas import (
    PersistenceTaskPayload,
    WriteSpec,
    WriteOperation,
    ConflictResolution
)

# Task payload
task = PersistenceTaskPayload(
    write=WriteSpec(
        table="leads",
        operation=WriteOperation.UPSERT,
        data=[
            {"id": "lead-123", "email": "john@example.com", "name": "John Doe"},
            {"id": "lead-456", "email": "jane@example.com", "name": "Jane Smith"}
        ],
        conflict_columns=["id"],
        conflict_resolution=ConflictResolution.UPDATE,
        returning=["id", "updated_at"]
    ),
    atomic=True,
    dry_run=False
)

# Result payload
from agent.schemas import PersistenceResultPayload, WriteResult

result = PersistenceResultPayload(
    write_result=WriteResult(
        operation=WriteOperation.UPSERT,
        rows_affected=2,
        conflicts_detected=1,
        conflicts_resolved=1
    ),
    table="leads",
    write_time_ms=125.3
)
```

### Configuration Schemas

```python
from agent.schemas import WorkerConfig, RedisConfig, StreamConfig, LogLevel

# Worker configuration
worker_config = WorkerConfig(
    worker_id="rag-worker-1",
    max_retries=3,
    retry_backoff_ms=1000,
    shutdown_timeout=30,
    log_level=LogLevel.INFO,
    enable_tracing=True,
    enable_metrics=True
)

# Redis configuration
redis_config = RedisConfig(
    host="redis.example.com",
    port=6379,
    db=0,
    namespace="agentic-prod",
    max_connections=100,
    use_tls=True
)

# Stream configuration
stream_config = StreamConfig(
    name="rag:tasks",
    maxlen=10000,
    consumer_group="rag-workers",
    max_pending=100,
    max_lag=500,
    enable_dlq=True
)
```

## Validation

### Basic Validation

```python
from agent.schemas import RAGTaskPayload, validate_payload, ValidationError

# Valid payload
try:
    task = validate_payload(
        {"query": {"table": "leads", "filters": {}}},
        RAGTaskPayload
    )
    print("Valid!")
except ValidationError as e:
    print(f"Invalid: {e}")
```

### Safe Validation (No Exceptions)

```python
from agent.schemas import safe_validate

raw_data = {"query": {"table": "leads"}}
model, errors = safe_validate(raw_data, RAGTaskPayload)

if errors:
    print(f"Validation errors: {errors}")
else:
    print(f"Valid model: {model}")
```

### Envelope Payload Validation

```python
from agent.schemas import validate_envelope_payload, RAGTaskPayload

envelope = {
    "metadata": {
        "task_id": "task-123",
        "source": "orchestrator"
    },
    "payload": {
        "query": {"table": "leads", "filters": {}}
    },
    "status": "pending"
}

# Validate just the payload field
task = validate_envelope_payload(envelope, RAGTaskPayload)
assert task.query.table == "leads"
```

## Schema Examples

Every schema includes example payloads in `json_schema_extra`:

```python
from agent.schemas import get_schema_example, RAGTaskPayload

example = get_schema_example(RAGTaskPayload)
print(example)
# {
#     "query": {
#         "table": "leads",
#         "filters": {"email": {"ilike": "%@example.com"}},
#         "limit": 50,
#         ...
#     }
# }

# Use example to create valid instance
task = RAGTaskPayload(**example)
```

## Validation Features

### Field Validation

All schemas include validators for:
- **SQL injection prevention**: Table and column names validated
- **Email format**: Basic email validation
- **URL format**: Endpoint and connection string validation
- **Enum values**: Type-safe enums for operations, statuses, etc.
- **Range checks**: Limits, timeouts, ports, etc.
- **String length**: Min/max constraints on all text fields

### Custom Validators

```python
from pydantic import validator

class QuerySpec(BaseModel):
    table: str
    
    @validator('table')
    def validate_table_name(cls, v):
        """Prevent SQL injection via table name"""
        if not v.replace('_', '').isalnum():
            raise ValueError(f"Invalid table name: {v}")
        return v
```

## Integration with Workers

### RAG Worker Example

```python
from agent.schemas import RAGTaskPayload, validate_envelope_payload
from agent.utils.typed_envelope import from_redis_message

def process(self, msg_id: str, fields: Dict[str, Any]) -> None:
    # Parse envelope
    envelope = from_redis_message(fields)
    
    # Validate payload against schema
    try:
        task = validate_envelope_payload(envelope, RAGTaskPayload)
    except ValidationError as e:
        # Send to DLQ with validation errors
        self._send_to_dlq(envelope, f"Validation failed: {e}")
        return
    
    # Now access with full type safety
    query_spec = task.query
    results = self.rag.query(
        table=query_spec.table,
        filters=query_spec.filters,
        limit=query_spec.limit
    )
```

### Configuration Loading

```python
from agent.schemas import WorkerConfig
import os

# Load from environment
config = WorkerConfig(
    worker_id=os.getenv("WORKER_ID"),
    max_retries=int(os.getenv("MAX_RETRIES", "3")),
    log_level=os.getenv("LOG_LEVEL", "info"),
    enable_tracing=os.getenv("ENABLE_TRACING", "false").lower() == "true"
)

# Validation happens automatically
assert config.max_retries >= 0  # Already validated
```

## Error Messages

Pydantic provides detailed validation errors:

```python
from agent.schemas import RAGTaskPayload, ValidationError

try:
    task = RAGTaskPayload(
        query={"table": "leads; DROP TABLE users;", "filters": {}}  # SQL injection attempt
    )
except ValidationError as e:
    print(e.json())
    # [
    #   {
    #     "loc": ["query", "table"],
    #     "msg": "Invalid table name: leads; DROP TABLE users;",
    #     "type": "value_error"
    #   }
    # ]
```

## JSON Schema Generation

Generate JSON schemas for API documentation:

```python
from agent.schemas import RAGTaskPayload

schema = RAGTaskPayload.model_json_schema()
print(schema)
# {
#   "type": "object",
#   "properties": {
#     "query": {
#       "type": "object",
#       "properties": {
#         "table": {"type": "string", "minLength": 1, "maxLength": 100},
#         ...
#       }
#     }
#   }
# }
```

## Best Practices

### 1. Always Validate Early

```python
# ✅ Good: Validate at entry point
def process(self, envelope):
    task = validate_envelope_payload(envelope, RAGTaskPayload)
    # Now work with validated data
    return self.execute(task)

# ❌ Bad: Assume data is valid
def process(self, envelope):
    # No validation, potential runtime errors
    table = envelope['payload']['query']['table']  # KeyError?
```

### 2. Use Type Hints

```python
# ✅ Good: Full type safety
def execute_query(task: RAGTaskPayload) -> RAGResultPayload:
    # IDE autocomplete works
    results = query_table(task.query.table, task.query.filters)
    return RAGResultPayload(records=results, count=len(results), table=task.query.table)

# ❌ Bad: No type hints
def execute_query(task) -> dict:
    # No IDE support, easy to make mistakes
    results = query_table(task['query']['table'], task['query']['filters'])
    return {'records': results, 'count': len(results)}
```

### 3. Leverage Enums

```python
from agent.schemas import WriteOperation

# ✅ Good: Type-safe enums
if write_spec.operation == WriteOperation.UPSERT:
    # Guaranteed to be valid operation
    perform_upsert(write_spec)

# ❌ Bad: String comparison (typos, case issues)
if write_spec.operation == "upsert":  # What if it's "UPSERT"?
    perform_upsert(write_spec)
```

### 4. Use Safe Validation for User Input

```python
from agent.schemas import safe_validate

# ✅ Good: Graceful error handling
model, errors = safe_validate(user_input, RAGTaskPayload)
if errors:
    return {"error": "Invalid input", "details": errors}
return process(model)

# ❌ Bad: Uncaught exceptions
try:
    model = RAGTaskPayload(**user_input)
except Exception as e:
    # Generic exception handling, poor UX
    return {"error": str(e)}
```

## Testing

### Unit Tests

```python
import pytest
from agent.schemas import RAGTaskPayload, ValidationError

def test_valid_rag_task():
    task = RAGTaskPayload(
        query={"table": "leads", "filters": {}}
    )
    assert task.query.table == "leads"

def test_invalid_table_name():
    with pytest.raises(ValidationError) as exc:
        RAGTaskPayload(
            query={"table": "leads; DROP TABLE", "filters": {}}
        )
    assert "Invalid table name" in str(exc.value)

def test_schema_example_is_valid():
    from agent.schemas import get_schema_example
    example = get_schema_example(RAGTaskPayload)
    task = RAGTaskPayload(**example)
    assert task is not None
```

## Migration Guide

### Migrating Existing Code

**Before (Dict-based):**
```python
def process_task(fields: Dict[str, Any]):
    query = fields['payload']['query']
    table = query['table']  # No validation
    filters = query.get('filters', {})
    limit = query.get('limit', 100)
```

**After (Schema-based):**
```python
from agent.schemas import RAGTaskPayload, validate_envelope_payload

def process_task(fields: Dict[str, Any]):
    envelope = from_redis_message(fields)
    task = validate_envelope_payload(envelope, RAGTaskPayload)
    # Validated, type-safe access
    table = task.query.table
    filters = task.query.filters
    limit = task.query.limit
```

## Future Enhancements

- [ ] JSON Schema → TypeScript type generation
- [ ] OpenAPI spec generation from schemas
- [ ] Runtime schema versioning and migration
- [ ] Custom validators for business logic
- [ ] Schema registry for multi-version support

---

**All schemas are production-ready with comprehensive validation! 🎉**
