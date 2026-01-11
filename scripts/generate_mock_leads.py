"""Generate mock lead profiles and (optionally) enqueue write tasks via Redis Streams.

Usage (PowerShell):
  # Print 5 mock leads as JSON to the console
  python scripts/generate_mock_leads.py --count 5

    # Enqueue 10 insert tasks to the write stream (requires write worker running)
    python scripts/generate_mock_leads.py --count 10 --enqueue

    # Use upsert instead of insert to avoid duplicate failures (conflict on email by default)
    python scripts/generate_mock_leads.py --count 10 --enqueue --op upsert --on-conflict email

Env:
  REDIS_URL, REDIS_NAMESPACE, REDIS_STREAM_TASKS_WRITE, REDIS_GROUP_WRITERS
  WRITE_ALLOWLIST (e.g., leads,lead_events)
"""
from __future__ import annotations

import argparse
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

from agent.utils.mock_leads import generate_leads, DEFAULT_CLIENT_IDS, DEFAULT_CAMPAIGN_ID

# Optional enqueue support via Streams write path
try:
    from agent.tools.redis.client import RedisPubSub
    from agent.tools.redis import config as rconf
    HAS_REDIS = True
except Exception:
    HAS_REDIS = False


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--enqueue", action="store_true", help="Enqueue insert tasks to write stream instead of printing")
    p.add_argument("--batch", action="store_true", help="Send one batch_insert task with all generated profiles")
    p.add_argument("--wait", action="store_true", help="When enqueueing, block until a result message for the task_id is observed")
    p.add_argument("--client-id", dest="client_id", action="append", help="Specific client_id(s) to sample from (can repeat)")
    p.add_argument("--op", choices=["insert", "upsert"], default="insert", help="Write operation for individual tasks (batch always uses batch_insert)")
    p.add_argument("--on-conflict", dest="on_conflict", default="email", help="Upsert conflict target/column (e.g., email)")
    args = p.parse_args()

    client_ids = args.client_id or DEFAULT_CLIENT_IDS
    profiles = generate_leads(count=args.count, client_ids=client_ids, campaign_id=DEFAULT_CAMPAIGN_ID)

    if not args.enqueue:
        print(json.dumps(profiles, indent=2))
        return

    if not HAS_REDIS:
        print("Redis client not available. Install 'redis' and ensure agent.tools.redis is importable.")
        return

    r = RedisPubSub()

    def wait_for_outcome(task_id: str, timeout: float = 30.0) -> dict:
        """Wait for either a success on results or an error on DLQ for this task_id.

        Returns a dict with keys: received(bool), source("results"|"dlq"|None), result(obj or None)
        """
        import time

        deadline = time.monotonic() + timeout
        last_ids = {rconf.STREAM_RESULTS_WRITE: "$", rconf.STREAM_DLQ_WRITE: "$"}
        while time.monotonic() < deadline:
            remaining = max(0, deadline - time.monotonic())
            block_ms = int(min(1000, remaining * 1000)) if remaining > 0 else 0
            try:
                res = r.xread(last_ids, count=10, block=block_ms)
            except Exception:
                res = []
            if not res:
                continue
            for stream_name, entries in res:
                # stream_name is namespaced; compare by suffix
                for msg_id, fields in entries:
                    last_ids_key = rconf.STREAM_RESULTS_WRITE if stream_name.endswith(rconf.STREAM_RESULTS_WRITE) else (
                        rconf.STREAM_DLQ_WRITE if stream_name.endswith(rconf.STREAM_DLQ_WRITE) else None
                    )
                    if last_ids_key:
                        last_ids[last_ids_key] = msg_id
                    data = fields.get("data")
                    try:
                        obj = json.loads(data) if isinstance(data, str) else data
                    except Exception:
                        obj = None
                    if obj is None:
                        continue
                    # Results path contains {task_id, success,...}
                    if stream_name.endswith(rconf.STREAM_RESULTS_WRITE) and isinstance(obj, dict) and obj.get("task_id") == task_id:
                        return {"received": True, "source": "results", "result": obj}
                    # DLQ path contains {task: {...}, error: str}
                    if stream_name.endswith(rconf.STREAM_DLQ_WRITE) and isinstance(obj, dict):
                        t = obj.get("task") if isinstance(obj.get("task"), dict) else None
                        if t and t.get("task_id") == task_id:
                            return {"received": True, "source": "dlq", "result": obj}
        return {"received": False, "source": None, "result": None}
    if args.batch:
        if args.op == "upsert":
            # We intentionally keep batch as batch_insert to leverage worker's batch path.
            # Upsert semantics are per-row; for batch upsert, prefer enqueuing individual upsert tasks.
            print("Note: --batch uses batch_insert; --op upsert is ignored in batch mode.")
        task_id = os.urandom(8).hex()
        task = {
            "task_id": task_id,
            "table": "leads",
            "op": "batch_insert",
            "values": profiles,
            "returning": True,
        }
        mid = r.xadd(
            rconf.STREAM_TASKS_WRITE,
            {"data": json.dumps(task)},
            maxlen=int(os.getenv("STREAM_MAXLEN", "0") or 0) or None,
        )
        print(json.dumps({"enqueued": True, "message_id": mid, "task_id": task_id, "count": len(profiles)}))
        if args.wait:
            outcome = wait_for_outcome(task_id)
            print(json.dumps(outcome, indent=2))
        r.close()
        return

    tasks = 0
    for prof in profiles:
        task_id = os.urandom(8).hex()
        task = {
            "task_id": task_id,
            "table": "leads",
            "op": args.op,
            "values": prof,
            "returning": True,
        }
        if args.op == "upsert":
            task["on_conflict"] = args.on_conflict
        mid = r.xadd(
            rconf.STREAM_TASKS_WRITE,
            {"data": json.dumps(task)},
            maxlen=int(os.getenv("STREAM_MAXLEN", "0") or 0) or None,
        )
        print(json.dumps({"enqueued": True, "message_id": mid, "task_id": task_id, "client_id": prof["client_id"]}))
        if args.wait:
            outcome = wait_for_outcome(task_id)
            print(json.dumps({"task_id": task_id, **outcome}))
        tasks += 1
    r.close()
    print(json.dumps({"total_enqueued": tasks}))


if __name__ == "__main__":
    main()
