"""
Check lengths of persistence task/result streams and print the latest result (if any).
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

import redis


def main() -> int:
    try:
        tenant_id = os.getenv("TENANT_ID", "agentic-dev")
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        task_stream = f"{tenant_id}:agents:persistence:tasks"
        result_stream = f"{tenant_id}:agents:persistence:results"

        r = redis.from_url(redis_url, decode_responses=False)

        tasks_len = r.xlen(task_stream)
        results_len = r.xlen(result_stream)
        print(f"tasks={tasks_len} results={results_len}")

        if results_len:
            latest = r.xrevrange(result_stream, count=1)
            for msg_id, data in latest:
                print(f"latest result msg_id={msg_id.decode() if isinstance(msg_id, bytes) else msg_id}")
                if b"data" in data:
                    try:
                        env: Dict[str, Any] = json.loads(data[b"data"])
                        print(json.dumps(env, indent=2))
                    except Exception as exc:  # noqa: BLE001
                        print(f"failed to parse envelope: {exc}")
                else:
                    print(f"raw: {data}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
