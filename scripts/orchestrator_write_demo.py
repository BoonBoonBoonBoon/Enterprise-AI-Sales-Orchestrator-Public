"""Orchestrator demo for write path using Redis Streams.

Enqueues an insert task to the write tasks stream and waits synchronously for
the corresponding result by task_id on the write results stream.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.tools.redis.client import RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.mock_leads import generate_lead_profile
from agent.operational_agents.factory import create_persistence_agent


def main() -> None:
    enqueue_only = "--enqueue-only" in sys.argv
    task_id = os.urandom(8).hex()
    lead = generate_lead_profile()
    task = {
        "task_id": task_id,
        "table": "leads",
        "op": "insert",
        "values": lead,
        "returning": True,
    }
    r = RedisPubSub()
    # Enqueue the task
    mid = r.xadd(rconf.STREAM_TASKS_WRITE, {"data": json.dumps(task)}, maxlen=int(os.getenv("STREAM_MAXLEN", "0") or 0) or None)
    print(json.dumps({"enqueued": True, "message_id": mid, "task_id": task_id}))
    # Persist last task id for convenience
    try:
        (Path(__file__).parent / ".last_write_task_id").write_text(task_id, encoding="utf-8")
    except Exception:
        pass
    if enqueue_only:
        r.close()
        return
    # Wait for the result on the results stream that matches our task_id
    res = r.wait_for_stream(
        rconf.STREAM_RESULTS_WRITE,
        predicate=lambda m: isinstance(m, dict) and m.get("task_id") == task_id,
        timeout=15.0,
        block_ms=1000,
    )
    r.close()
    print(json.dumps({"received": bool(res), "result": res}, indent=2))

    # Read-back verification via PersistenceAgent
    try:
        email = None
        if isinstance(res, dict):
            row = res.get("row") or {}
            if isinstance(row, dict):
                email = row.get("email")
        if not email:
            email = lead.get("email")
        agent = create_persistence_agent(kind=os.environ.get("PERSIST_KIND", "supabase"))
        rows = agent.query("leads", filters={"email": email}, limit=1)
        print(json.dumps({"read_back": bool(rows), "email": email, "row": rows[0] if rows else None}, indent=2))
    except Exception as e:
        print(json.dumps({"read_back_error": str(e)}))


if __name__ == "__main__":
    main()
