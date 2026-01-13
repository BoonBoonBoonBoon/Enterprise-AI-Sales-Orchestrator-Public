# Redis Service

The Redis Service provides connection management and utilities for Redis Streams communication.

## Overview

| Component    | Description                               |
| ------------ | ----------------------------------------- |
| **Location** | `services/redis/`                         |
| **Purpose**  | Redis client management, stream utilities |
| **Used By**  | All agents, orchestrators, Manager        |

## Client Management

### Getting a Client

```python
from services.redis.client import get_redis_client

# Uses REDIS_URL from environment
redis = get_redis_client()

# Or with explicit URL
redis = get_redis_client(url="redis://localhost:6379/0")
```

### Connection Pool

The service maintains a connection pool for efficiency:

```python
# Singleton pattern - same pool reused
client1 = get_redis_client()
client2 = get_redis_client()
assert client1 is client2  # Same instance
```

## Stream Operations

### Publishing

```python
import json

def publish_task(redis, stream: str, task: dict) -> str:
    """Publish task to stream, return message ID."""
    return redis.xadd(stream, {"data": json.dumps(task)})

# Example
message_id = publish_task(
    redis,
    "agentic-dev:agents:rag:tasks",
    {"task_id": "123", "payload": {...}}
)
```

### Reading

```python
def read_messages(redis, stream: str, count: int = 10) -> list:
    """Read messages from stream."""
    return redis.xread({stream: "0"}, count=count)

# With blocking
results = redis.xread(
    {"agentic-dev:agents:rag:results": "$"},
    count=1,
    block=5000  # 5 second timeout
)
```

### Consumer Groups

```python
# Create group
redis.xgroup_create(
    "agentic-dev:agents:rag:tasks",
    "rag_workers",
    id="0",
    mkstream=True
)

# Read with group
messages = redis.xreadgroup(
    groupname="rag_workers",
    consumername="worker-1",
    streams={"agentic-dev:agents:rag:tasks": ">"},
    count=1,
    block=5000
)

# Acknowledge
redis.xack("stream", "rag_workers", message_id)
```

## Stream Utilities

### StreamClient

Higher-level wrapper for common operations:

```python
from services.redis.stream_client import StreamClient

client = StreamClient(tenant_id="agentic-dev")

# Publish to agent
client.publish_to_agent("rag", {
    "action": "get_lead_context",
    "lead_id": "123"
})

# Wait for result
result = client.wait_for_result("rag", task_id, timeout=30)
```

### Key Builder

```python
from core.streams import build_stream_key

# Build stream keys
key = build_stream_key("agentic-dev", "agents", "rag", "tasks")
# Returns: "agentic-dev:agents:rag:tasks"
```

## Configuration

### Environment Variables

| Variable                | Default                    | Description    |
| ----------------------- | -------------------------- | -------------- |
| `REDIS_URL`             | `redis://localhost:6379/0` | Connection URL |
| `REDIS_PASSWORD`        | â€”                          | Auth password  |
| `REDIS_MAX_CONNECTIONS` | `10`                       | Pool size      |

### URL Format

```
redis://<REDACTED_REDIS_URL>

# Examples
redis://localhost:6379/0
redis://<REDACTED_REDIS_URL>
redis://<REDACTED_REDIS_URL>  # Docker service name
```

## File Structure

```
services/redis/
â”œâ”€â”€ __init__.py
â”œâ”€â”€ client.py          # Connection management
â”œâ”€â”€ stream_client.py   # High-level stream ops
â””â”€â”€ README.md
```

## Health Check

```python
def check_redis_health(redis) -> bool:
    """Check if Redis is responsive."""
    try:
        return redis.ping()
    except Exception:
        return False
```

## Error Handling

```python
from redis.exceptions import ConnectionError, TimeoutError

try:
    redis.xadd("stream", {"data": "..."})
except ConnectionError:
    logger.error("Redis connection failed")
    # Retry or fail gracefully
except TimeoutError:
    logger.error("Redis operation timed out")
```

## Related

- [Redis Streams Concept](../../concepts/redis-streams.md)
- [ADR-003: Redis Streams](../../architecture/decisions/003-redis-streams-over-queues.md)
- [Stream Keys Reference](../../reference/api/streams.md)

