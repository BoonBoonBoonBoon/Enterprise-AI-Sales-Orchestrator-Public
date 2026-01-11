"""
Reset the persistence consumer group to clear pending entries.
- Destroys group if exists, recreates it with id=0 (mkstream=True).
- Use this before starting the persistence consumer if tasks were stolen by ad-hoc xreadgroup tests.
"""
from __future__ import annotations

import os
import sys

import redis


def main() -> int:
    try:
        tenant_id = os.getenv("TENANT_ID", "agentic-dev")
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        group = os.getenv("PERSISTENCE_CONSUMER_GROUP", "persistence_workers")
        stream = f"{tenant_id}:agents:persistence:tasks"

        r = redis.from_url(redis_url, decode_responses=True)

        try:
            r.xgroup_destroy(stream, group)
            print(f"Destroyed consumer group '{group}' on '{stream}'")
        except redis.ResponseError as exc:  # noqa: BLE001
            if "NOGROUP" in str(exc) or "Key not found" in str(exc):
                print(f"Group '{group}' did not exist; continuing")
            else:
                raise

        r.xgroup_create(stream, group, id="0", mkstream=True)
        print(f"Created consumer group '{group}' on '{stream}' with id=0")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
