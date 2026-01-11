"""
Publish a test compound task to the persistence task stream.
- Uses core envelope helpers to stay consistent with production format.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List

import redis
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.envelope import task as create_task_envelope, to_redis_fields


def main() -> int:
    try:
        tenant_id = os.getenv("TENANT_ID", "agentic-dev")
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        stream = f"{tenant_id}:agents:persistence:tasks"

        r = redis.from_url(redis_url, decode_responses=False)

        uniq = uuid.uuid4().hex[:8]
        sender_email = f"publish_test_{uniq}@example.com"
        thread_id = f"thread-{uniq}"
        message_id = f"msg-{uniq}"

        steps: List[Dict[str, Any]] = [
            {
                "step_name": "staging_lead",
                "table": "staging_leads",
                "operation": "upsert",
                "data": {"email": sender_email},
                "match_on": ["email"],
            },
            {
                "step_name": "staging_conversation",
                "table": "staging_conversations",
                "operation": "upsert",
                "data": {
                    "staging_lead_id": "$ref:staging_lead.id",
                    "thread_id": thread_id,
                    "subject": "Publish test",
                    "channel": "email",
                    "status": "open",
                    "metadata": {},
                },
                "match_on": ["staging_lead_id", "thread_id"],
            },
            {
                "step_name": "staging_message",
                "table": "staging_messages",
                "operation": "upsert",
                "data": {
                    "staging_conversation_id": "$ref:staging_conversation.id",
                    "sender": sender_email,
                    "receiver": "support@example.com",
                    "content": "Hello from publish_test_compound",
                    "sent_at": datetime.utcnow().isoformat(),
                    "message_id": message_id,
                    "metadata": {},
                },
                "match_on": ["staging_conversation_id", "message_id"],
            },
        ]

        payload: Dict[str, Any] = {
            "operation": "compound",
            "steps": steps,
            "delegated_by": "debug_publish",
            "timestamp": datetime.utcnow().isoformat(),
        }

        task_id = f"persist_compound_{uuid.uuid4()}"
        envelope = create_task_envelope(
            source="debug_publish",
            task_id=task_id,
            payload=payload,
            destination="persistence_agent",
            tenant_id=tenant_id,
        )

        msg_id = r.xadd(stream, to_redis_fields(envelope))
        print(f"Published task_id={task_id} to {stream} msg_id={msg_id.decode() if isinstance(msg_id, bytes) else msg_id}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
