r"""Peek recent entries in the Manager task stream.

Usage:
    .\.venv\Scripts\python.exe scripts\peek_manager_stream.py --tenant agentic-dev --count 5

Notes:
- Uses RedisStreamsClient which applies REDIS_NAMESPACE automatically.
- The stream name is built as: {tenant}:manager:tasks (before namespacing).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


# Allow running as a standalone script (adds repo root to sys.path).
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# Load .env so RedisStreamsClient connects to the intended Redis.
try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env", override=True)
except Exception:
    pass

from services.redis import RedisStreamsClient


def _to_str(value) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Peek {tenant}:manager:tasks stream")
    parser.add_argument("--tenant", default=os.getenv("TENANT_ID", "agentic-dev"))
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    client = RedisStreamsClient()
    stream = f"{args.tenant}:manager:tasks"

    # Use underlying redis-py client so we can call xrevrange.
    namespaced_stream = client._chan(stream)
    entries = client.client.xrevrange(namespaced_stream, count=args.count)

    print(f"Stream: {namespaced_stream}")
    print(f"Entries: {len(entries)}")
    for entry_id, fields in entries:
        # fields typically include {'data': '<json>'} due to to_redis_fields().
        decoded = {_to_str(k): _to_str(v) for k, v in fields.items()}
        payload = decoded
        if "data" in decoded:
            try:
                payload = json.loads(decoded["data"])
            except Exception:
                payload = decoded
        print("-")
        print(_to_str(entry_id))
        print(json.dumps(payload, indent=2) if isinstance(payload, (dict, list)) else str(payload))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
