Redis Setup and Next Steps
==========================

This guide walks you through setting up Redis for queues in this project, verifying connectivity, and running workers against Redis Streams.

What you’ll configure
---------------------
- A Redis database (Redis Cloud or self‑hosted)
- Environment variables (.env) for connection and namespacing
- Queue backend selection (Redis vs. in‑memory)
- Health checks and a basic worker

1) Create a Redis database
--------------------------
Redis Cloud (recommended for dev):
- Create database (Essentials/free is fine)
- Note the public endpoint (Host, Port) and password
- Decide TLS vs non‑TLS
  - TLS → use rediss:// with the TLS port
  - Non‑TLS → use redis:// with the non‑TLS port (dev only)

2) Configure .env (don’t commit secrets)
---------------------------------------
Add the following to your `.env` (example shows non‑TLS; switch to TLS in prod):

```
# Redis connection URL (include user, password, host, port, and DB index)
REDIS_URL=redis://default:<PASSWORD>@<HOST>:<PORT>/0

# Key prefix to isolate environments (dev/test/prod)
REDIS_NAMESPACE=agentic-dev

# Optional: friendly name for the worker in consumer groups
REDIS_CONSUMER=agentic-worker-1

# Choose queue backend for workers: redis | memory
QUEUE_BACKEND=redis
```

Notes:
- If your password has special characters (@ : / #), URL‑encode it before inserting into the URL.
- For TLS: `REDIS_URL=rediss://default:<PASSWORD>@<HOST>:<TLS_PORT>/0`
- Keep `.env` out of version control; rotate credentials if already exposed.

3) Install dependencies
-----------------------
The adapter uses `redis` and env loading uses `python-dotenv`.

```
pip install redis python-dotenv
```

4) Verify connectivity
----------------------
Use the provided smoke test (runs PING and prints diagnostics):

```
python scripts/redis_smoke_test.py
```

Expected: `PING: True`

5) Quick producer/consumer check
--------------------------------
Start a consumer in one terminal:

```
python scripts/redis_queue_example.py --mode consume --topic orchestrate
```

Produce a message in another:

```
python scripts/redis_queue_example.py --mode produce --topic orchestrate
```

You should see the consumer print the received message and ack it.

6) Run a worker against Redis
-----------------------------
Launch a worker that consumes the `orchestrate` stream using the Redis backend:

```
python scripts/start_worker.py --backend redis --topic orchestrate --consumer agentic-worker-1
```

Then produce a message as above. The worker uses the project’s `Worker` class and a no‑op orchestrator for demonstration.

7) Health and visibility
------------------------
Inspect stream/group/consumers with:

```
python scripts/redis_health.py --topic orchestrate
```

This prints stream length, last ID, groups, and consumers in the group.

Operational next steps
----------------------
- Retention: decide on XTRIM policy to keep streams bounded (operate outside the app or add a small maintenance script).
- Retry & DLQ: add exponential backoff (e.g., 5s, 15s, 60s) and route exhausted jobs to `<topic>.dlq`. A replay tool can move messages back to the main stream.
- Rate limiting: implement a Redis token bucket per tenant and per operation (ingest, LLM, delivery) to prevent noisy neighbors.
- Metrics: expose counters (enqueue, dequeue, ack, retry, dlq) and lag gauges; consider a Redis exporter for Prometheus.
- TLS: in non‑dev environments, switch to the TLS endpoint (`rediss://`) and verify certificate settings.

Troubleshooting
---------------
- `SSL: WRONG_VERSION_NUMBER`: you used `rediss://` on a non‑TLS port. Switch to the TLS port (from Redis Cloud) or use `redis://` if you intend non‑TLS.
- `AuthenticationError`: verify user is `default` (or your ACL user) and the password is correct. URL‑encode special characters.
- No messages consumed: confirm the topic name, that the producer sent to the same topic, and that `REDIS_NAMESPACE` matches (keys are prefixed).
- Timeouts: ensure your firewall allows outbound traffic to the Redis Cloud port.

Where the code lives
--------------------
- Adapter: `agent/Infastructure/queue/adapters/redis_streams_queue.py`
- Factory (selects backend): `agent/Infastructure/queue/factory.py`
- Worker: `agent/Infastructure/worker/worker.py`
- Examples & health: `scripts/redis_queue_example.py`, `scripts/redis_smoke_test.py`, `scripts/redis_health.py`, `scripts/start_worker.py`

Security checklist (prod)
-------------------------
- Use `rediss://` with the TLS endpoint; do not use non‑TLS in production.
- Store secrets in a vault or CI secrets, not in `.env` committed to VCS.
- Use a distinct `REDIS_NAMESPACE` per environment to avoid collisions.
- Consider network policies (VPC peering/private link) if available from your provider.

Planned enhancements
--------------------
- Built‑in exponential backoff & DLQ wiring in the worker path
- Stream trimming helper
- Metrics integration (Prometheus/OpenTelemetry)
- Simple per‑tenant rate limiter utilities
