DEPRECATED — Use Streams-first workers and client
=================================================

This adapter and examples are deprecated. Use the Redis Streams workers and client instead:

- agent/tools/redis/config.py — namespaces, key builders, stream/group names
- agent/tools/redis/client.py — RedisPubSub wrapper (xadd, xreadgroup, xack)
- agent/operational_agents/persistence_agent/write_worker.py — persist:tasks → DB → persist:results
- agent/operational_agents/rag_agent/worker.py — rag:tasks → rag:results
- scripts/streams_health.py, scripts/streams_group_reset.py, scripts/streams_write_benchmark.py

Legacy reference below is retained for historical context only.

---

Redis Streams Queue Adapter
===========================

Files
-----
- `redis_streams_queue.py` — Implements `QueueInterface` using Redis Streams.
- `scripts/redis_queue_example.py` — Simple producer/consumer example.

Key Design
----------
- Stream per topic: `<namespace>:stream:<topic>`
- Consumer group per topic: `<namespace>:grp:<topic>`
- Messages are JSON encoded in a single field `data`.
- `job_id` is the Redis entry ID (e.g. `1716234567890-0`).
- Delayed requeue backed by sorted set `<namespace>:delayed:<topic>` (ETA in ms).

Environment
-----------
- `REDIS_URL` (default `redis://localhost:6379/0`)
- `REDIS_NAMESPACE` (default `agentic`)
- `REDIS_CONSUMER` (auto-generated if not set)

Basic Usage
-----------
```
from agent.Infastructure.queue.adapters.redis_streams_queue import RedisStreamsQueue
q = RedisStreamsQueue()
jid = q.enqueue('orchestrate', {'job_id':'x','run_id':'r1','orchestrator':'lead_sync','payload':{},'meta':{'flow':'orchestrate'}})
msg = q.dequeue('orchestrate', timeout=5.0)
q.ack(msg['job_id'])
```

Delayed Requeue
---------------
```
q.requeue(job, delay=10.0)  # seconds
```

Operational Notes
-----------------
- Use one consumer group per worker pool; set unique `consumer_name` per process.
- Consider `XTRIM` policies outside of app if streams grow large.
- For per-tenant fairness, choose topic or partitioning key accordingly.
