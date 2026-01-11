"""Benchmark: enqueue N individual write tasks and measure time to completion.

Process:
- Publish a marker into the results stream to avoid missing early results.
- Enqueue N insert tasks (one per lead).
- Block-read the results stream until all task_ids are observed.
- Print total elapsed time and throughput (tasks/sec).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Set

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
from agent.utils.mock_leads import generate_leads, DEFAULT_CLIENT_IDS, DEFAULT_CAMPAIGN_ID


def read_new_results_until(r: RedisPubSub, start_id: str, wanted: Set[str], timeout: float = 60.0) -> Dict[str, Any]:
    last_id = start_id
    found: Set[str] = set()
    deadline = time.monotonic() + timeout
    while wanted - found and time.monotonic() < deadline:
        block_ms = int(max(0, min(1000, (deadline - time.monotonic()) * 1000))) or 1000
        res = r.xread({rconf.STREAM_RESULTS_WRITE: last_id}, count=100, block=block_ms)
        if not res:
            continue
        for _stream, entries in res:
            for msg_id, fields in entries:
                last_id = msg_id
                data = fields.get("data")
                try:
                    obj = json.loads(data) if isinstance(data, str) else data
                    tid = obj.get("task_id") if isinstance(obj, dict) else None
                    if isinstance(tid, str) and tid in wanted:
                        found.add(tid)
                except Exception:
                    continue
    return {"found": len(found), "remaining": len(wanted - found), "last_id": last_id}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--client-id", dest="client_id", action="append")
    args = ap.parse_args()

    client_ids = args.client_id or DEFAULT_CLIENT_IDS
    profiles = generate_leads(count=args.count, client_ids=client_ids, campaign_id=DEFAULT_CAMPAIGN_ID)

    r = RedisPubSub()

    # Insert a marker into results to establish a starting point
    batch_tag = os.urandom(6).hex()
    marker_fields = {"data": json.dumps({"marker": "start", "batch": batch_tag, "ts": time.time()})}
    marker_id = r.xadd(rconf.STREAM_RESULTS_WRITE, marker_fields, maxlen=int(os.getenv("STREAM_MAXLEN", "0") or 0) or None)

    # Enqueue individual tasks
    task_ids = []
    start = time.perf_counter()
    for prof in profiles:
        task_id = os.urandom(8).hex()
        task = {
            "task_id": task_id,
            "table": "leads",
            "op": "insert",
            "values": prof,
            "returning": True,
            "batch": batch_tag,
        }
        r.xadd(
            rconf.STREAM_TASKS_WRITE,
            {"data": json.dumps(task)},
            maxlen=int(os.getenv("STREAM_MAXLEN", "0") or 0) or None,
        )
        task_ids.append(task_id)

    # Wait for all results
    stats = read_new_results_until(r, marker_id, set(task_ids), timeout=args.timeout)
    end = time.perf_counter()
    r.close()

    elapsed = end - start
    throughput = (len(task_ids) / elapsed) if elapsed > 0 else None
    print(
        json.dumps(
            {
                "tasks": len(task_ids),
                "elapsed_sec": round(elapsed, 3),
                "tasks_per_sec": round(throughput, 2) if throughput is not None else None,
                "found": stats["found"],
                "remaining": stats["remaining"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
