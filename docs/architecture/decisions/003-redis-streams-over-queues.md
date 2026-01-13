# ADR-003: Redis Streams over Message Queues

**Status:** ✅ Accepted  
**Date:** October 2025

## Context

We needed a messaging infrastructure for inter-agent communication with these requirements:

1. **Ordered delivery** — Tasks must be processed in order
2. **Persistence** — Messages survive restarts
3. **Consumer groups** — Multiple consumers can share load
4. **Acknowledgment** — Explicit ACK to prevent message loss
5. **Replay** — Ability to reprocess historical messages
6. **Low latency** — Sub-millisecond in-datacenter
7. **Simplicity** — Minimal operational overhead

Options considered: Redis Streams, RabbitMQ, Apache Kafka, AWS SQS, NATS.

## Decision

We use **Redis Streams** as the messaging backbone for all inter-agent communication.

### Stream Key Convention

```
{tenant}:manager:tasks           # Manager input
{tenant}:manager:results         # Manager output
{tenant}:orchestrators:{name}:tasks    # Orchestrator input
{tenant}:orchestrators:{name}:results  # Orchestrator output
{tenant}:agents:{name}:tasks     # Agent input
{tenant}:agents:{name}:results   # Agent output
```

### Consumer Group Pattern

```python
# Consumer setup
redis.xgroup_create(stream_key, group_name, mkstream=True)

# Blocking read
messages = redis.xreadgroup(
    groupname=group_name,
    consumername=consumer_id,
    streams={stream_key: ">"},
    block=5000
)

# Acknowledge after processing
redis.xack(stream_key, group_name, message_id)
```

## Consequences

### Positive

- **Single infrastructure** — Redis already used for caching, now also messaging
- **Ordered delivery** — Messages delivered in insertion order
- **Consumer groups** — Built-in load balancing across consumers
- **Persistence** — Messages stored on disk (AOF/RDB)
- **Replay** — Can read from any point in stream history
- **Low latency** — Sub-millisecond for local Redis
- **Simple operations** — Redis is well-understood, easy to monitor
- **Dead letter handling** — Pending entries list (PEL) tracks unacked messages

### Negative

- **Single point of failure** — Redis availability is critical (mitigate with Sentinel/Cluster)
- **Memory pressure** — Streams consume memory; need XTRIM policies
- **No routing** — Unlike RabbitMQ, no built-in topic routing (we handle in code)
- **Limited ecosystem** — Fewer management tools than Kafka/RabbitMQ

### Neutral

- **Stream length management** — Use MAXLEN or MINID to bound stream size
- **Monitoring** — Use XINFO for stream health checks

## Alternatives Considered

### Option A: RabbitMQ

Full-featured message broker with routing, exchanges, queues.

- **Pros:** Mature, rich routing, management UI, plugins
- **Cons:** Additional infrastructure, more complex, higher latency
- **Why rejected:** Overkill for our needs, adds operational burden

### Option B: Apache Kafka

Distributed streaming platform for high-throughput.

- **Pros:** Massive scale, strong ordering, retention
- **Cons:** Complex to operate, high resource usage, overkill for our scale
- **Why rejected:** Too heavy for current requirements

### Option C: AWS SQS

Managed queue service.

- **Pros:** Fully managed, no operations
- **Cons:** Higher latency, no ordering guarantees (FIFO limited), vendor lock-in
- **Why rejected:** Latency and ordering requirements not met

### Option D: NATS

Lightweight messaging system.

- **Pros:** Very fast, simple, cloud-native
- **Cons:** Less mature streaming (JetStream newer), smaller ecosystem
- **Why rejected:** Redis already in stack, JetStream less proven

## Implementation Details

### Stream Operations Used

| Operation    | Purpose                                  |
| ------------ | ---------------------------------------- |
| `XADD`       | Publish message to stream                |
| `XREADGROUP` | Consumer group blocking read             |
| `XACK`       | Acknowledge processed message            |
| `XPENDING`   | Check pending (unacked) messages         |
| `XCLAIM`     | Claim stuck messages from dead consumers |
| `XTRIM`      | Bound stream length                      |
| `XINFO`      | Stream metadata and health               |

### Dead Letter Queue Pattern

```python
# Check for stuck messages older than 5 minutes
pending = redis.xpending_range(stream, group, min="-", max="+", count=100)
for msg in pending:
    if msg.idle > 300000:  # 5 minutes
        # Move to DLQ or retry
        redis.xclaim(stream, group, "dlq-consumer", 0, [msg.id])
```

## References

- [Redis Streams Documentation](https://redis.io/docs/data-types/streams/)
- [Redis Streams Tutorial](https://redis.io/docs/data-types/streams-tutorial/)
