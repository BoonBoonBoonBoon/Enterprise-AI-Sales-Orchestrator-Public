"""Enqueue a simple copy task and optionally wait for the result."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import task, to_redis_fields, Priority


def wait_for(correlation_id: str, r: RedisPubSub, timeout: float = 20.0) -> Dict[str, Any]:
    """Wait for a copy result with matching correlation_id on copy:results stream."""
    return {
        "received": bool(
            r.wait_for_stream(
                rconf.STREAM_RESULTS_COPY,
                predicate=lambda m: isinstance(m, dict) and m.get("correlation_id") == correlation_id,
                timeout=timeout,
                block_ms=1000,
            )
        )
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject-hint", default="Introducing our solution")
    ap.add_argument("--tone", default="friendly")
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()

    r = RedisPubSub()
    
    # Build task envelope with lead data, campaign context, and instructions
    envelope = task(
        task_id=os.urandom(8).hex(),
        payload={
            "lead_data": {
                "id": "lead_demo_001",
                "first_name": "Alex",
                "company_name": "Example Co",
                "email": "alex@example.co",
                "title": "CTO"
            },
            "campaign_context": {
                "campaign_name": "Demo Campaign",
                "step": 1,
                "previous_contact": None
            },
            "instructions": {
                "tone": args.tone,
                "subject_hint": args.subject_hint,
                "language": "en-US",
                "max_length": 200,
                "include_cta": True
            }
        },
        source="demo_script",
        destination=rconf.STREAM_TASKS_COPY,
        priority=Priority.NORMAL
    )
    
    mid = r.xadd(rconf.STREAM_TASKS_COPY, to_redis_fields(envelope), maxlen=rconf.STREAM_MAXLEN)
    print(json.dumps({
        "enqueued": True, 
        "message_id": mid, 
        "task_id": envelope.metadata.task_id,
        "correlation_id": envelope.metadata.correlation_id
    }))
    
    if args.wait:
        out = wait_for(envelope.metadata.correlation_id, r)
        print(json.dumps(out, indent=2))
    r.close()


if __name__ == "__main__":
    main()
