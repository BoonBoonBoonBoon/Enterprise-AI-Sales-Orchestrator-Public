# Redis Operations & Monitoring

**Status:** Active  
**Last Updated:** January 2026

This guide covers operating and monitoring Redis Streams in production.

## Table of Contents

1. [Health Checks](#health-checks)
2. [Monitoring Streams](#monitoring-streams)
3. [Consumer Group Management](#consumer-group-management)
4. [Troubleshooting](#troubleshooting)
5. [Scaling](#scaling)

---

## Health Checks

### Basic Connectivity

```python
def check_redis_health(redis_client):
    try:
        redis_client.ping()
        return {"status": "healthy"}
    except redis.ConnectionError as e:
        return {"status": "unhealthy", "error": str(e)}
```

### Stream Health Script

```bash
# scripts/redis/redis_health.py
python -m scripts.redis.redis_health
```

---

## Monitoring Streams

### Stream Length

```python
def get_stream_lengths(redis_client, tenant_id: str):
    streams = [
        f"{tenant_id}:manager:tasks",
        f"{tenant_id}:orchestrators:leads:tasks",
        f"{tenant_id}:agents:rag:tasks",
        f"{tenant_id}:agents:persistence:tasks",
    ]

    lengths = {}
    for stream in streams:
        try:
            lengths[stream] = redis_client.xlen(stream)
        except redis.ResponseError:
            lengths[stream] = 0

    return lengths
```

### Pending Messages

```python
def get_pending_count(redis_client, stream: str, group: str):
    info = redis_client.xpending(stream, group)
    return info["pending"] if info else 0
```

### Key Metrics

| Metric        | Description          | Alert Threshold |
| ------------- | -------------------- | --------------- |
| Stream length | Messages waiting     | > 1000          |
| Pending count | Unacknowledged       | > 100           |
| Consumer lag  | Time since last read | > 60s           |
| DLQ length    | Failed messages      | > 10            |

---

## Consumer Group Management

### List Consumer Groups

```bash
redis-cli XINFO GROUPS agentic-dev:agents:rag:tasks
```

### Create Consumer Group

```python
redis_client.xgroup_create(
    "agentic-dev:agents:rag:tasks",
    "rag-agent-group",
    id="0",
    mkstream=True
)
```

### Reset Consumer Group

```python
# Start from beginning
redis_client.xgroup_setid(
    "agentic-dev:agents:rag:tasks",
    "rag-agent-group",
    id="0"
)

# Start from now (skip existing)
redis_client.xgroup_setid(
    "agentic-dev:agents:rag:tasks",
    "rag-agent-group",
    id="$"
)
```

### Cleanup Legacy Groups

```bash
python -m scripts.redis.cleanup_legacy_consumer_groups
```

---

## Troubleshooting

### Messages Not Being Processed

1. **Check consumer is running:**

   ```bash
   ps aux | grep "tier_3.*consumer"
   ```

2. **Check pending messages:**

   ```bash
   redis-cli XPENDING agentic-dev:agents:rag:tasks rag-agent-group
   ```

3. **Reclaim stuck messages:**
   ```python
   # Claim messages idle for > 60 seconds
   redis_client.xautoclaim(
       "agentic-dev:agents:rag:tasks",
       "rag-agent-group",
       "consumer-1",
       min_idle_time=60000,
       start_id="0"
   )
   ```

### High Stream Length

1. **Check if consumer is overwhelmed:**

   - Scale up consumers
   - Check for slow operations

2. **Trim old messages:**
   ```python
   # Keep only last 10000 messages
   redis_client.xtrim("agentic-dev:agents:rag:tasks", maxlen=10000)
   ```

### Connection Issues

1. **Check Redis is running:**

   ```bash
   redis-cli ping
   ```

2. **Check connection limits:**

   ```bash
   redis-cli INFO clients
   ```

3. **Check memory:**
   ```bash
   redis-cli INFO memory
   ```

---

## Scaling

### Horizontal Scaling (Consumers)

Add more consumers to the same group:

```bash
# Consumer 1
python -m tiers.tier_3.rag_agent.consumer --consumer-id=1

# Consumer 2
python -m tiers.tier_3.rag_agent.consumer --consumer-id=2

# Consumer 3
python -m tiers.tier_3.rag_agent.consumer --consumer-id=3
```

Redis automatically distributes messages across consumers in the same group.

### Vertical Scaling (Redis)

For high throughput:

- Increase `maxmemory`
- Use Redis Cluster for > 25GB data
- Consider Redis Cloud for managed scaling

### Kubernetes Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-agent-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-agent
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: External
      external:
        metric:
          name: redis_stream_pending
          selector:
            matchLabels:
              stream: rag-tasks
        target:
          type: AverageValue
          averageValue: "50"
```

---

## Useful Scripts

| Script                                            | Purpose                  |
| ------------------------------------------------- | ------------------------ |
| `scripts/redis/redis_health.py`                   | Check Redis connectivity |
| `scripts/redis/streams_health.py`                 | Check stream status      |
| `scripts/redis/cleanup_legacy_consumer_groups.py` | Remove old groups        |
| `scripts/redis/reset_consumer_groups.py`          | Reset group offsets      |

---

## See Also

- [Architecture Overview](overview.md)
- [Implementation Guide](implementation.md)
- [Deployment Guide](../../guides/deployment/)
