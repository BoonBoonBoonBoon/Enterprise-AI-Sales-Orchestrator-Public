# Redis Streams

Redis Streams is the messaging backbone for all inter-component communication in the Agentic System. This page explains how streams work and how we use them.

## Why Redis Streams?

| Feature                | Redis Streams | Pub/Sub | Kafka  |
| ---------------------- | ------------- | ------- | ------ |
| Message persistence    | ✅            | ❌      | ✅     |
| Consumer groups        | ✅            | ❌      | ✅     |
| Message acknowledgment | ✅            | ❌      | ✅     |
| Operational simplicity | ✅            | ✅      | ❌     |
| Latency                | ~1ms          | ~1ms    | 5-10ms |
| Message ordering       | ✅            | ❌      | ✅     |

Redis Streams provides the reliability of a proper message queue with the simplicity of Redis.

## Core Concepts

### Streams

A stream is an append-only log of messages:

```
Stream: "agentic-dev:agents:rag:tasks"

Messages:
  1705234567890-0 → {"data": "{\"task_id\": \"abc\", ...}"}
  1705234567891-0 → {"data": "{\"task_id\": \"def\", ...}"}
  1705234567892-0 → {"data": "{\"task_id\": \"ghi\", ...}"}
```

### Consumer Groups

Consumer groups allow multiple workers to share a stream:

```
Stream: agentic-dev:agents:persistence:tasks

┌─────────────────────────────────────────────┐
│               Consumer Group                │
│           "persistence_workers"             │
│                                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│   │ Worker 1 │  │ Worker 2 │  │ Worker 3 │ │
│   └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────┘
```

Each message goes to exactly one worker, enabling horizontal scaling.

### Message Acknowledgment

Messages must be acknowledged after processing:

```python
# Read message
messages = redis.xreadgroup("group", "consumer", {"stream": ">"}, count=1)

# Process message
result = process_task(messages[0])

# Acknowledge completion
redis.xack("stream", "group", message_id)
```

Unacknowledged messages can be reclaimed by other workers.

## Stream Naming Convention

All streams follow a strict naming pattern:

```
{tenant_id}:{tier_prefix}:{component_name}:{direction}
```

### Tier Prefixes

| Tier          | Prefix          | Example                                 |
| ------------- | --------------- | --------------------------------------- |
| Manager       | `manager`       | `agentic-dev:manager:tasks`             |
| Orchestrators | `orchestrators` | `agentic-dev:orchestrators:leads:tasks` |
| Agents        | `agents`        | `agentic-dev:agents:rag:tasks`          |

### Direction

| Direction | Purpose                |
| --------- | ---------------------- |
| `tasks`   | Incoming work requests |
| `results` | Outgoing responses     |

### Examples

```bash
# Manager
agentic-dev:manager:tasks
agentic-dev:manager:results

# Leads Orchestrator
agentic-dev:orchestrators:leads:tasks
agentic-dev:orchestrators:leads:results

# RAG Agent
agentic-dev:agents:rag:tasks
agentic-dev:agents:rag:results

# Persistence Agent
agentic-dev:agents:persistence:tasks
agentic-dev:agents:persistence:results
```

## Publishing Messages

### Basic Write

```python
import json
from services.redis.client import get_redis_client

redis = get_redis_client()

task = {
    "task_id": "unique-id",
    "tenant_id": "agentic-dev",
    "payload": {"action": "get_lead", "lead_id": "123"},
    "metadata": {"source": "leads_orchestrator"}
}

# Write to stream
message_id = redis.xadd(
    "agentic-dev:agents:rag:tasks",
    {"data": json.dumps(task)}
)
# Returns: "1705234567890-0"
```

### With Stream Client

```python
from core.streams import StreamClient

client = StreamClient(tenant_id="agentic-dev")

# Publish task
client.publish_task(
    target="rag",
    tier="agents",
    payload={"action": "get_lead", "lead_id": "123"}
)
```

## Consuming Messages

### Basic Read (Blocking)

```python
while True:
    # Block until message available
    result = redis.xreadgroup(
        groupname="rag_workers",
        consumername="worker-1",
        streams={"agentic-dev:agents:rag:tasks": ">"},
        count=1,
        block=5000  # 5 second timeout
    )

    if result:
        stream, messages = result[0]
        for msg_id, data in messages:
            task = json.loads(data["data"])

            try:
                response = process_task(task)
                publish_result(response)
                redis.xack(stream, "rag_workers", msg_id)
            except Exception as e:
                # Message will be reclaimed after timeout
                log_error(e)
```

### With Agent Harness

```python
from core.harness.agent_harness import AgentHarness

class RAGAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="rag",
            consumer_group="rag_workers"
        )

    def process_task(self, task: dict) -> dict:
        # Your logic - harness handles ACK
        return {"status": "success", "result": {...}}

# Run consumer
harness = RAGAgentHarness("agentic-dev")
harness.run()  # Blocks, handles messages
```

## Message Lifecycle

```
1. PRODUCER publishes task
   ┌───────────────┐
   │  xadd(stream, │──────▶ Stream
   │     {data})   │
   └───────────────┘

2. CONSUMER reads task
                              Consumer Group
   Stream ──────────▶ ┌───────────────┐
                      │  xreadgroup() │
                      └───────┬───────┘
                              │
                              ▼
                        ┌─────────┐
                        │ Process │
                        └────┬────┘
                             │
3. CONSUMER acknowledges     │
                             ▼
                      ┌───────────────┐
                      │   xack()      │──────▶ Removed from
                      │               │        Pending Entries
                      └───────────────┘
```

## Error Handling

### Unacknowledged Messages

Messages not ACK'd become "pending" and can be reclaimed:

```python
# Check pending messages
pending = redis.xpending("stream", "group")

# Claim old messages (stuck > 60s)
claimed = redis.xclaim(
    "stream",
    "group",
    "new-consumer",
    min_idle_time=60000,  # 60 seconds
    message_ids=["1705234567890-0"]
)
```

### Dead Letter Queue

For messages that fail repeatedly:

```python
MAX_RETRIES = 3

# Get detailed pending info
pending = redis.xpending_range("stream", "group", "-", "+", count=10)

for msg in pending:
    if msg["times_delivered"] > MAX_RETRIES:
        # Move to dead letter
        redis.xadd("stream:dead-letter", original_message)
        redis.xack("stream", "group", msg["message_id"])
```

## Monitoring

### Stream Length

```python
length = redis.xlen("agentic-dev:agents:rag:tasks")
print(f"Pending tasks: {length}")
```

### Consumer Lag

```python
# Get consumer group info
info = redis.xinfo_groups("stream")
for group in info:
    print(f"Group: {group['name']}, Pending: {group['pending']}")
```

### Stream Info

```bash
# Redis CLI
XINFO STREAM agentic-dev:agents:rag:tasks
XINFO GROUPS agentic-dev:agents:rag:tasks
XINFO CONSUMERS agentic-dev:agents:rag:tasks group-name
```

## Best Practices

1. **Use consumer groups** — Enables scaling and fault tolerance
2. **Always ACK** — Prevents message reprocessing
3. **Set block timeout** — Allows graceful shutdown
4. **Monitor pending** — Detect stuck messages
5. **Trim old messages** — Prevent memory bloat
6. **Use correlation IDs** — Link requests and responses

## Stream Trimming

Prevent unbounded growth:

```python
# Keep only last 10,000 messages
redis.xtrim("stream", maxlen=10000, approximate=True)

# Or trim in producer
redis.xadd("stream", {"data": "..."}, maxlen=10000)
```

## Related

- [ADR-003: Redis Streams](../architecture/decisions/003-redis-streams-over-queues.md)
- [Envelope Schema](../reference/api/envelope.md)
- [Three-Tier Architecture](three-tier-architecture.md)
- [Troubleshooting](../guides/ops/troubleshooting.md)
