"""Redis Streams smoke test: enqueue a simple message, then consume and ack.

Usage:
  python scripts/redis_stream_smoke.py --produce
  python scripts/redis_stream_smoke.py --consume --once

Respects env:
  REDIS_URL, REDIS_NAMESPACE, REDIS_STREAM_TASKS, REDIS_STREAM_RESULTS, REDIS_GROUP, REDIS_CONSUMER
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

from agent.tools.redis.client import RedisPubSub
from agent.tools.redis import config as rconf


def produce() -> None:
    r = RedisPubSub()
    payload = {"hello": "world", "pid": os.getpid()}
    mid = r.xadd(rconf.STREAM_TASKS, {"data": json.dumps(payload)}, maxlen=int(os.getenv("STREAM_MAXLEN", "0") or 0) or None)
    print(json.dumps({"enqueued": True, "message_id": mid, "stream": rconf.full_key(rconf.STREAM_TASKS)}))
    r.close()


def consume(once: bool = False) -> None:
    r = RedisPubSub()
    consumer = os.getenv("REDIS_CONSUMER") or f"smoke-{os.getpid()}"
    r.xgroup_create(rconf.STREAM_TASKS, rconf.GROUP_WORKERS, id="$", mkstream=True)
    print(f"listening on {rconf.full_key(rconf.STREAM_TASKS)} as {consumer} in group {rconf.GROUP_WORKERS}")
    while True:
        batches = r.xreadgroup(group=rconf.GROUP_WORKERS, consumer=consumer, streams={rconf.STREAM_TASKS: ">"}, count=1, block=2000)
        for _stream, entries in (batches or []):
            for mid, fields in entries:
                try:
                    data = json.loads(fields.get("data", "{}"))
                except Exception:
                    data = {"raw": fields.get("data")}
                print(json.dumps({"got": True, "message_id": mid, "data": data}))
                r.xack(rconf.STREAM_TASKS, rconf.GROUP_WORKERS, mid)
                if once:
                    r.close()
                    return


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--produce", action="store_true")
    p.add_argument("--consume", action="store_true")
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    if args.produce:
        produce()
    elif args.consume:
        consume(once=args.once)
    else:
        p.error("choose --produce or --consume")


if __name__ == "__main__":
    main()
