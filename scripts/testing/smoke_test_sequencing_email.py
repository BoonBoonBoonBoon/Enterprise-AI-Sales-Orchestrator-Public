"""Smoke test: enqueue a single sequencing email task and wait for the matching result.

This uses the standard typed envelope codec (core.envelope) and Redis Streams.

Required env vars (via .env or process env):
- REDIS_URL
Optional:
- TENANT_ID (default: agentic-dev)
- SMOKE_TEST_TO_EMAIL (default: GMAIL_SENDER_EMAIL)
- GMAIL_SENDER_EMAIL (used as fallback recipient)

Note: This script prints envelope status and error fields but does not print secrets.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import redis
from dotenv import load_dotenv

# Ensure repo root is importable when running as a file: `python scripts/...py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.envelope import from_redis_message, task as make_task, to_redis_fields


def main() -> int:
    load_dotenv(dotenv_path=Path(".env"), override=False)

    redis_url = os.getenv("REDIS_URL")
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (check .env)")

    sender_email = (os.getenv("GMAIL_SENDER_EMAIL") or "").strip()
    recipient_email = (os.getenv("SMOKE_TEST_TO_EMAIL") or sender_email).strip()
    if not recipient_email:
        raise SystemExit(
            "No recipient configured. Set SMOKE_TEST_TO_EMAIL or GMAIL_SENDER_EMAIL in .env"
        )

    task_stream = f"{tenant_id}:agents:sequencing:tasks"
    result_stream = f"{tenant_id}:agents:sequencing:results"

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    client.ping()

    cursor_id = "$"  # only read results after enqueue
    task_id = str(uuid.uuid4())

    payload = {
        "tenant_id": tenant_id,
        "lead_id": None,
        "steps": [
            {
                "channel": "email",
                "to_email": recipient_email,
                "subject": "[Agentic System] Sequencer smoke test",
                "body": (
                    "Sequencer smoke test at "
                    + datetime.now(timezone.utc).isoformat()
                    + "\n\nExpect deliveries[].message_id on success."
                ),
            }
        ],
        "context": {"smoke_test": True},
    }

    env = make_task(
        source="manual_smoke_test",
        task_id=task_id,
        payload=payload,
        destination=task_stream,
        tenant_id=tenant_id,
    )

    xadd_id = client.xadd(task_stream, to_redis_fields(env))

    matched_env = None
    matched_redis_id = None

    end = time.time() + 30
    while time.time() < end:
        msgs = client.xread({result_stream: cursor_id}, block=2000, count=25)
        if not msgs:
            continue
        for _stream, entries in msgs:
            for msg_id, fields in entries:
                cursor_id = msg_id
                try:
                    out_env = from_redis_message(fields)
                except Exception:
                    continue
                if out_env.metadata.task_id == task_id:
                    matched_env = out_env
                    matched_redis_id = msg_id
                    break
            if matched_env:
                break
        if matched_env:
            break

    out = {
        "enqueued": {
            "task_id": task_id,
            "xadd_id": xadd_id,
            "task_stream": task_stream,
        },
        "matched_result": None,
    }

    if matched_env is None:
        out["matched_result"] = {
            "found": False,
            "note": "No matching result received within timeout. Is the channel_sequencer_agent running?",
        }
    else:
        out["matched_result"] = {
            "found": True,
            "result_stream": result_stream,
            "redis_message_id": matched_redis_id,
            "envelope_status": str(matched_env.status),
            "error_code": matched_env.error_code,
            "error": matched_env.error,
            "payload": matched_env.payload,
        }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
