# Redis Implementation Guide

**Status:** Active  
**Last Updated:** January 2026

This guide covers implementing Redis Streams communication in agents and orchestrators.

## Table of Contents

1. [Client Setup](#client-setup)
2. [Publishing Tasks](#publishing-tasks)
3. [Consuming Tasks](#consuming-tasks)
4. [Message Envelope](#message-envelope)
5. [Error Handling](#error-handling)
6. [Best Practices](#best-practices)

---

## Client Setup

### Connection

```python
import redis
import os

def get_redis_client():
    return redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True
    )
```

### Environment Variables

```bash
REDIS_URL=redis://localhost:6379
# or for Redis Cloud
REDIS_URL=redis://<REDACTED_REDIS_URL>
```

---

## Publishing Tasks

### Using Core Envelope

```python
from core.envelope import task, to_redis_fields
from core.streams import assert_agents_stream

def delegate_to_agent(redis_client, tenant_id: str, agent_name: str, payload: dict):
    stream = f"{tenant_id}:agents:{agent_name}:tasks"

    # Guard: ensure we're publishing to an agent stream
    assert_agents_stream(stream)

    # Create envelope
    envelope = task(
        tenant_id=tenant_id,
        payload=payload,
        source="leads_orchestrator",
        target=agent_name
    )

    # Publish
    message_id = redis_client.xadd(stream, to_redis_fields(envelope))
    return message_id
```

### Direct Publishing

```python
import json
import uuid
from datetime import datetime

def publish_task(redis_client, stream: str, payload: dict):
    message = {
        "task_id": str(uuid.uuid4()),
        "payload": json.dumps(payload),
        "timestamp": datetime.utcnow().isoformat()
    }
    return redis_client.xadd(stream, message)
```

---

## Consuming Tasks

### Consumer Group Setup

```python
def ensure_consumer_group(redis_client, stream: str, group: str):
    try:
        redis_client.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise
```

### Consumer Loop

```python
def consume_loop(redis_client, stream: str, group: str, consumer: str):
    ensure_consumer_group(redis_client, stream, group)

    while True:
        messages = redis_client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=10,
            block=5000  # 5 second block
        )

        for stream_name, stream_messages in messages:
            for message_id, fields in stream_messages:
                try:
                    result = process_message(fields)
                    redis_client.xack(stream, group, message_id)
                except Exception as e:
                    handle_error(message_id, e)
```

### Using Agent Harness

```python
from core.harness.agent_harness import AgentHarness

class MyAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="my_agent",
        )

    def process_task(self, task: dict) -> dict:
        payload = task.get("payload", {})
        # Process and return result
        return {"status": "success", "data": {...}}

# Run
harness = MyAgentHarness("agentic-dev")
harness.run()  # Blocks, listens on stream
```

---

## Message Envelope

### Standard Format

```json
{
  "task_id": "uuid-v4",
  "tenant_id": "agentic-dev",
  "payload": {
    "action": "query_leads",
    "filters": { "stage": "qualified" }
  },
  "metadata": {
    "source": "manager",
    "target": "leads",
    "correlation_id": "uuid-v4",
    "timestamp": "2026-01-10T12:00:00Z"
  }
}
```

### Creating Envelopes

```python
from core.envelope import task, result, to_redis_fields, from_redis_message

# Create task envelope
envelope = task(
    tenant_id="agentic-dev",
    payload={"action": "query_leads"},
    source="manager",
    target="leads"
)

# Convert to Redis fields
fields = to_redis_fields(envelope)

# Parse from Redis message
envelope = from_redis_message(fields)
```

---

## Error Handling

### Dead Letter Queue

```python
def handle_failed_message(redis_client, tenant_id: str, message_id: str, error: str):
    dlq_stream = f"{tenant_id}:system:dlq"
    redis_client.xadd(dlq_stream, {
        "original_message_id": message_id,
        "error": error,
        "timestamp": datetime.utcnow().isoformat()
    })
```

### Retry with Backoff

```python
from core.harness.retry_strategies import ExponentialBackoff

retry = ExponentialBackoff(max_retries=3, base_delay=1.0)

for attempt in retry.attempts():
    try:
        result = process_message(message)
        break
    except TransientError as e:
        if not retry.should_retry(attempt):
            raise
        retry.wait(attempt)
```

---

## Best Practices

### 1. Always Use Tenant Prefix

```python
# âœ… Correct
stream = f"{tenant_id}:agents:rag:tasks"

# âŒ Wrong - missing tenant
stream = "agents:rag:tasks"
```

### 2. Guard Against Invalid Streams

```python
from core.streams import assert_agents_stream

# Orchestrators can only publish to agent streams
assert_agents_stream(stream)  # Raises if not an agent stream
```

### 3. Acknowledge After Processing

```python
# âœ… Correct - ack after successful processing
result = process_message(message)
redis_client.xack(stream, group, message_id)

# âŒ Wrong - ack before processing (loses messages on crash)
redis_client.xack(stream, group, message_id)
result = process_message(message)
```

### 4. Use Consumer Groups

Always use consumer groups for reliable delivery:

- Messages are tracked per consumer
- Failed messages can be reclaimed
- Multiple consumers can process in parallel

### 5. Set Reasonable Timeouts

```python
# Block for 5 seconds, not indefinitely
messages = redis_client.xreadgroup(..., block=5000)
```

---

## See Also

- [Architecture Overview](overview.md)
- [Operations & Monitoring](operations.md)
- [Agent Harness](https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/core/harness/README.md)

