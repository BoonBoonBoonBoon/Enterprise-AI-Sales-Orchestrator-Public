"""Smoke enqueue tasks to exercise workers and emit Prometheus series.

This is intentionally lightweight: it enqueues a handful of tasks into Redis Streams
so the running docker-compose workers (manager/orchestrators/agents) process at least
one message. That makes latency/error histograms/counters appear in Prometheus.

Run (from repo root):
  python scripts/observability/smoke_enqueue_tasks.py

Env vars:
  TENANT_ID (default: agentic-dev)
  REDIS_URL (default: redis://localhost:6379/0)
"""

from __future__ import annotations

import os
import time
import uuid
import sys
from pathlib import Path

# Ensure repo root is importable when running as a script.
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Load environment variables from .env if present.
try:
    from dotenv import load_dotenv
    load_dotenv(repo_root / ".env")
except Exception:
    pass

from services.redis import RedisStreamsClient
from core.envelope import task as make_task, to_redis_fields


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4()}"


def main() -> None:
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    redis = RedisStreamsClient(url=redis_url)

    # Stream names (these are canonical and should NOT be namespace-prefixed).
    streams: list[tuple[str, dict, str]] = []

    # 1) Manager (Tier 1): should succeed via deterministic shortcut.
    streams.append(
        (
            f"{tenant_id}:manager:tasks",
            {"goal": "Run health check"},
            "manager",
        )
    )

    # 2) Leads Orchestrator (Tier 2): may fail depending on config; that's OK.
    streams.append(
        (
            f"{tenant_id}:orchestrators:leads:tasks",
            {"goal": "smoke", "data": {}},
            "leads_orchestrator",
        )
    )

    # 3) Outbound Orchestrator (Tier 2): deterministic path by providing reply_packet.
    reply_packet = {
        "lead_resolution": {"status": "found", "lead_id": "L1"},
        "inbound_email_event": {
            "from": "lead@example.com",
            "subject": "Re: Hello",
            "body": "Hi — quick smoke test.",
        },
        "facts": {"company": "Acme"},
        "conversation": {"recent_messages": []},
        "next": {"delegate_to": ["outbound"]},
    }
    streams.append(
        (
            f"{tenant_id}:orchestrators:outbound:tasks",
            {"reply_packet": reply_packet, "auto_send": False},
            "outreach_orchestrator",
        )
    )

    # 4) Tier 3 agents: enqueue minimal tasks (success is not required to emit metrics).
    streams.append(
        (
            f"{tenant_id}:agents:rag:tasks",
            {"goal": "smoke"},
            "rag_agent",
        )
    )
    streams.append(
        (
            f"{tenant_id}:agents:persistence:tasks",
            {"goal": "smoke"},
            "persistence_agent",
        )
    )
    streams.append(
        (
            f"{tenant_id}:agents:copywriter:tasks",
            {"goal": "smoke", "context": {"company": "Acme"}},
            "copywriter_agent",
        )
    )
    streams.append(
        (
            f"{tenant_id}:agents:sequencing:tasks",
            {"goal": "smoke"},
            "channel_sequencer_agent",
        )
    )
    streams.append(
        (
            f"{tenant_id}:agents:booking:tasks",
            {"goal": "smoke"},
            "scheduler_agent",
        )
    )

    enqueued = []
    for stream, payload, destination in streams:
        env = make_task(
            source="smoke_enqueue_tasks",
            task_id=_uid("task"),
            payload=payload,
            destination=destination,
            tenant_id=tenant_id,
        )
        msg_id = redis.xadd(stream, to_redis_fields(env))
        enqueued.append((stream, msg_id))

    print(f"Enqueued {len(enqueued)} tasks to Redis ({redis_url}) for tenant={tenant_id}:")
    for stream, msg_id in enqueued:
        print(f"  - {stream} => {msg_id}")

    # Give consumers a moment to pick them up.
    time.sleep(2)


if __name__ == "__main__":
    main()
