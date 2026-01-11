# Redis Service

Provides Redis client utilities and stream management for inter-agent communication.

## Components

| Directory         | Purpose                             |
| ----------------- | ----------------------------------- |
| `consumer_group/` | Consumer group management utilities |
| `pubsub/`         | Pub/sub utilities                   |

## Usage

```python
from services.redis import get_redis_client

redis = get_redis_client()

# Write to agent stream
redis.xadd("agentic-dev:agents:rag:tasks", {"payload": json.dumps(data)})

# Read from stream with consumer group
messages = redis.xreadgroup(
    "rag-consumers",
    "consumer-1",
    {"agentic-dev:agents:rag:tasks": ">"},
    count=10
)
```

## Stream Naming Convention

```
{tenant}:manager:tasks              # Manager input
{tenant}:orchestrators:{name}:tasks # Orchestrator input
{tenant}:agents:{name}:tasks        # Agent input
```

## Configuration

```bash
REDIS_URL=redis://localhost:6379
# or
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=...
```

## See Also

- [Redis Architecture](../../docs/architecture/redis/)
- [Core Streams Utilities](../../core/streams.py)
