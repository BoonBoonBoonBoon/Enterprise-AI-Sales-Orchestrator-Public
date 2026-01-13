# Rate Limiting Implementation Guide

## Overview

Rate limiting prevents worker overload and ensures fair resource utilization across multiple streams and workers. The system supports both local (in-memory) and distributed (Redis-backed) rate limiting with multiple algorithms.

---

## Features

✅ **Token Bucket Algorithm** - Smooth rate limiting with configurable burst capacity  
✅ **Sliding Window Algorithm** - Strict rate limiting without bursts  
✅ **Per-Worker Limits** - Individual worker capacity controls  
✅ **Per-Stream Limits** - Shared limits across all consumers of a stream  
✅ **Redis-Backed** - Distributed rate limiting for multi-instance deployments  
✅ **Memory-Backed** - Local rate limiting for single-instance deployments  
✅ **Configurable** - Environment variable configuration  
✅ **Non-Blocking** - Optional timeout-based blocking

---

## Quick Start

### 1. Enable Rate Limiting

```bash
# Enable rate limiting
export RATE_LIMIT_ENABLED=1

# Configure rate (messages per second)
export RATE_LIMIT_PER_SECOND=100

# Configure burst size (maximum tokens)
export RATE_LIMIT_BURST_SIZE=200

# Choose algorithm (token_bucket or sliding_window)
export RATE_LIMIT_ALGORITHM=token_bucket

# Choose backend (redis or memory)
export RATE_LIMIT_BACKEND=memory
```

### 2. Workers Auto-Initialize

All workers automatically initialize rate limiting:

```python
# RAG Worker, Copywriter Worker, Persistence Worker
# All have rate limiting built-in (no code changes needed)
```

### 3. Test Rate Limiting

```bash
# Start worker with rate limiting
export RATE_LIMIT_ENABLED=1
export RATE_LIMIT_PER_SECOND=5
python -m agent.operational_agents.rag_agent.worker

# Send messages faster than limit
# You'll see: "[RAGWorker 12345] Rate limit timeout for message..."
```

---

## Configuration

### Environment Variables

| Variable                | Default        | Description                                   |
| ----------------------- | -------------- | --------------------------------------------- |
| `RATE_LIMIT_ENABLED`    | `0`            | Enable (`1`) or disable (`0`) rate limiting   |
| `RATE_LIMIT_PER_SECOND` | `100`          | Messages per second limit                     |
| `RATE_LIMIT_BURST_SIZE` | `200`          | Maximum burst size (token bucket only)        |
| `RATE_LIMIT_ALGORITHM`  | `token_bucket` | Algorithm: `token_bucket` or `sliding_window` |
| `RATE_LIMIT_BACKEND`    | `memory`       | Backend: `memory` or `redis`                  |

### Configuration Profiles

**Development (Permissive):**

```bash
RATE_LIMIT_ENABLED=0  # Disabled for dev speed
```

**Staging (Moderate):**

```bash
RATE_LIMIT_ENABLED=1
RATE_LIMIT_PER_SECOND=50
RATE_LIMIT_BURST_SIZE=100
RATE_LIMIT_ALGORITHM=token_bucket
RATE_LIMIT_BACKEND=redis
```

**Production (Conservative):**

```bash
RATE_LIMIT_ENABLED=1
RATE_LIMIT_PER_SECOND=20
RATE_LIMIT_BURST_SIZE=40
RATE_LIMIT_ALGORITHM=token_bucket
RATE_LIMIT_BACKEND=redis
```

**High Throughput:**

```bash
RATE_LIMIT_ENABLED=1
RATE_LIMIT_PER_SECOND=200
RATE_LIMIT_BURST_SIZE=400
RATE_LIMIT_ALGORITHM=token_bucket
RATE_LIMIT_BACKEND=redis
```

**Strict (No Bursts):**

```bash
RATE_LIMIT_ENABLED=1
RATE_LIMIT_PER_SECOND=10
RATE_LIMIT_BURST_SIZE=10  # Same as rate = no burst
RATE_LIMIT_ALGORITHM=sliding_window
RATE_LIMIT_BACKEND=redis
```

---

## Algorithms

### Token Bucket (Recommended)

**How it works:**

- Tokens added to bucket at fixed rate (e.g., 100/sec)
- Bucket has maximum capacity (e.g., 200 tokens)
- Each message consumes 1 token
- If no tokens available, request blocks/fails

**Pros:**

- Allows bursts (handles traffic spikes gracefully)
- Smooth long-term rate limiting
- Standard industry algorithm

**Cons:**

- Slightly more complex than sliding window

**Use when:**

- Traffic has bursts (user activity, batch jobs)
- Need to handle occasional spikes
- Long-term average rate is more important than instant rate

**Example:**

```
Rate: 10/sec, Burst: 20
- Can handle 20 messages instantly
- Then throttles to 10/sec
- Tokens refill over time
```

### Sliding Window

**How it works:**

- Tracks timestamps of recent requests
- Only allows N requests per window (e.g., 1 second)
- Strictly enforces rate limit

**Pros:**

- Simple and predictable
- Strict rate enforcement
- No burst allowance

**Cons:**

- Doesn't handle bursts well
- Can reject valid requests after sudden traffic

**Use when:**

- Need strict rate enforcement
- No tolerance for bursts
- Protecting rate-limited external APIs

**Example:**

```
Rate: 10/sec
- Exactly 10 messages per second
- No bursts allowed
- Requests evenly distributed
```

---

## Backends

### Memory (Default)

**How it works:**

- Rate limits stored in-memory (per process)
- Each worker has independent limits
- Fast, no network overhead

**Pros:**

- Zero latency
- No external dependencies
- Simple to configure

**Cons:**

- Not shared across workers
- Lost on restart
- Doesn't scale across instances

**Use when:**

- Single worker instance
- Development/testing
- No distributed deployment

### Redis (Recommended for Production)

**How it works:**

- Rate limits stored in Redis
- Shared across all workers
- Uses Lua scripts for atomicity

**Pros:**

- Shared state across workers
- Scales to multiple instances
- Survives worker restarts

**Cons:**

- Slight network latency (1-2ms)
- Requires Redis dependency

**Use when:**

- Multiple worker instances
- Kubernetes/Docker Compose deployments
- Need consistent rate limiting across cluster

---

## Worker Integration

All workers automatically initialize rate limiting:

```python
# RAG Worker
class RAGWorker(TracedWorker):
    def __init__(self, kind: str = "supabase"):
        # ... existing code ...
        self.rate_limiter = init_rate_limiter(redis_client=self.redis)

    def process(self, msg_id: str, fields: Dict[str, Any]) -> None:
        # Rate limiting: acquire token before processing
        worker_key = f"worker:{self.worker_id}"
        if not self.rate_limiter.acquire(worker_key, block=True, timeout=30.0):
            print(f"[RAGWorker {self.worker_id}] Rate limit timeout, will retry")
            return  # Don't ACK, message will be retried

        # ... process message ...
```

**Key Points:**

- Each worker has unique key: `worker:{pid}`
- Blocks up to 30 seconds waiting for token
- If timeout, message is re-queued (not ACKed)
- Works automatically with zero configuration

---

## Monitoring

### Logs

Rate limiting events are logged:

```
[RateLimiter] Initialized: token_bucket @ 100.0/sec (burst: 200)
[RAGWorker 12345] Rate limit timeout for message 1730000000000-0, will retry
```

### Metrics (Future)

Planned Prometheus metrics:

```
# Rate limiter state
rate_limiter_tokens_available{worker="rag-worker-12345"} 150.0
rate_limiter_requests_blocked_total{worker="rag-worker-12345"} 5

# Worker throughput
worker_messages_processed_total{worker="rag-worker-12345"} 1000
worker_rate_limit_waits_total{worker="rag-worker-12345"} 10
```

### Manual Inspection

Check available capacity:

```python
from agent.utils.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()
available = limiter.available("worker:12345")
print(f"Available tokens: {available}")
```

---

## Performance Impact

### Latency

**Memory Backend:**

- ~0.01ms overhead per message
- Negligible impact

**Redis Backend:**

- ~1-2ms overhead per message
- Acceptable for most workloads

### Throughput

**Without Rate Limiting:**

- Limited by database/LLM API speed
- Can overload downstream services

**With Rate Limiting:**

- Controlled throughput
- Prevents cascading failures
- Better resource utilization

### Example Impact

**Before:**

```
Worker processes messages as fast as possible
→ Database gets overwhelmed
→ Queries start timing out
→ DLQ fills up
→ System degrades
```

**After:**

```
Worker processes at controlled rate (e.g., 100/sec)
→ Database load is stable
→ Queries succeed consistently
→ DLQ stays empty
→ System stays healthy
```

---

## Troubleshooting

### Issue: Messages Taking Too Long

**Symptoms:**

```
[RAGWorker 12345] Rate limit timeout for message...
```

**Cause:** Rate limit too aggressive for workload

**Solution:**

```bash
# Increase rate or burst size
export RATE_LIMIT_PER_SECOND=200
export RATE_LIMIT_BURST_SIZE=400
```

### Issue: Workers Not Rate Limited

**Symptoms:**

- Workers processing at full speed
- No rate limit logs

**Cause:** Rate limiting disabled

**Solution:**

```bash
export RATE_LIMIT_ENABLED=1
```

### Issue: Inconsistent Rate Limiting

**Symptoms:**

- Some workers throttled, others not
- Rate varies across workers

**Cause:** Using memory backend with multiple workers

**Solution:**

```bash
# Switch to Redis backend for shared state
export RATE_LIMIT_BACKEND=redis
```

### Issue: Rate Limiting Too Strict

**Symptoms:**

- High message latency
- Messages backing up in streams

**Cause:** Rate limit lower than required throughput

**Solution:**

1. Measure required throughput
2. Set rate 20% higher than peak
3. Set burst 2x rate

```bash
# If peak is 80 msg/sec
export RATE_LIMIT_PER_SECOND=100  # 20% buffer
export RATE_LIMIT_BURST_SIZE=200  # 2x rate
```

---

## Best Practices

### 1. Set Rate Based on Downstream Capacity

**Don't:**

```bash
# Arbitrary limit
RATE_LIMIT_PER_SECOND=50
```

**Do:**

```bash
# Based on database capacity
# DB handles 200 qps, we have 2 workers
# Set to 100/sec per worker
RATE_LIMIT_PER_SECOND=100
```

### 2. Allow Bursts in Production

**Don't:**

```bash
# No burst capacity
RATE_LIMIT_PER_SECOND=10
RATE_LIMIT_BURST_SIZE=10
```

**Do:**

```bash
# 2x burst capacity for spikes
RATE_LIMIT_PER_SECOND=10
RATE_LIMIT_BURST_SIZE=20
```

### 3. Use Redis in Multi-Instance Deployments

**Don't:**

```bash
# Memory backend with 5 workers
# Effective rate: 500/sec (5 workers × 100/sec)
RATE_LIMIT_BACKEND=memory
RATE_LIMIT_PER_SECOND=100
```

**Do:**

```bash
# Redis backend with 5 workers
# Effective rate: 100/sec (shared across workers)
RATE_LIMIT_BACKEND=redis
RATE_LIMIT_PER_SECOND=100
```

### 4. Monitor and Adjust

```bash
# Start conservative
RATE_LIMIT_PER_SECOND=50

# Monitor for a day
# If no issues, increase by 20%
RATE_LIMIT_PER_SECOND=60

# Repeat until optimal
```

### 5. Test Before Production

```bash
# Load test with rate limiting
export RATE_LIMIT_ENABLED=1
export RATE_LIMIT_PER_SECOND=100

# Send 1000 messages
python scripts/load_test.py --count 1000

# Check:
# - Are messages processed at target rate?
# - Are workers healthy?
# - Are there timeout errors?
```

---

## API Reference

### RateLimitConfig

```python
@dataclass
class RateLimitConfig:
    rate_per_second: float = 100.0
    burst_size: int = 200
    algorithm: Literal["token_bucket", "sliding_window"] = "token_bucket"
    backend: Literal["redis", "memory"] = "memory"
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "RateLimitConfig":
        """Load from environment variables."""
```

### RateLimiter

```python
class RateLimiter:
    def acquire(
        self,
        key: str,
        tokens: int = 1,
        block: bool = True,
        timeout: Optional[float] = None
    ) -> bool:
        """Acquire rate limit token.

        Args:
            key: Identifier (worker ID, stream name, etc.)
            tokens: Number of tokens to acquire
            block: If True, block until token available
            timeout: Maximum time to block (seconds)

        Returns:
            True if acquired, False if timeout
        """

    def available(self, key: str) -> float:
        """Get available capacity for key."""
```

### Global Functions

```python
def init_rate_limiter(
    config: Optional[RateLimitConfig] = None,
    redis_client=None
) -> RateLimiter:
    """Initialize global rate limiter."""

def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
```

---

## Migration Guide

### From No Rate Limiting

**Before:**

```python
# worker.py
def process(self, msg_id, fields):
    # Process immediately
    result = do_work(fields)
```

**After:**

```python
# worker.py (automatic via base implementation)
# No changes needed! Rate limiting added automatically.
```

**Configuration:**

```bash
# Enable in environment
export RATE_LIMIT_ENABLED=1
export RATE_LIMIT_PER_SECOND=100
```

### From Custom Rate Limiting

**Before:**

```python
# Custom rate limiter
import time
last_request = time.time()

def process(self, msg_id, fields):
    now = time.time()
    if now - last_request < 0.01:  # 100/sec
        time.sleep(0.01 - (now - last_request))
    last_request = now
    # ... process ...
```

**After:**

```python
# Remove custom code, use built-in
# Rate limiting happens automatically
```

---

## Related Documentation

- [Architecture Documentation](../architecture/overview.md) - System architecture
- [Enhancements](../updates/ENHANCEMENTS.md) - Ops notes and system changes
- [Incident Playbooks](../INCIDENT_PLAYBOOKS.md) - Troubleshooting guide

---

**Status:** ✅ Production Ready

**Last Updated:** October 27, 2025
