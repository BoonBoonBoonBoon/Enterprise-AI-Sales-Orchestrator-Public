"""
Direct PersistenceAgent compound write test (no Redis streams).
- Executes a compound payload that writes to staging tables in FK order.
- Prints normalized result.

Run: & ".venv/Scripts/python.exe" scripts/test_persistence_agent_direct.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import Any, Dict, List

import redis
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent


async def run_test() -> int:
    try:
        tenant_id = os.getenv("TENANT_ID", "agentic-dev")
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, tenant_id))
        unique = uuid.uuid4().hex[:8]

        sender_email = f"agent_direct_{unique}@example.com"
        thread_id = f"thread-{unique}"
        message_id = f"msg-{unique}"

        redis_client = redis.from_url(redis_url, decode_responses=False)

        agent = PersistenceAgent(
            redis_client=redis_client,
            tenant_id=tenant_id,
            model=os.getenv("PERSISTENCE_MODEL", "gpt-4o-mini"),
        )

        steps: List[Dict[str, Any]] = [
            {
                "step_name": "staging_lead",
                "table": "staging_leads",
                "operation": "upsert",
                "data": {"email": sender_email, "client_id": client_uuid},
                "match_on": ["email"],
            },
            {
                "step_name": "staging_conversation",
                "table": "staging_conversations",
                "operation": "upsert",
                "data": {
                    "staging_lead_id": "$ref:staging_lead.id",
                    "thread_id": thread_id,
                    "subject": "Debug direct test",
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
                    "content": "Hello from direct persistence agent test",
                    "sent_at": None,
                    "message_id": message_id,
                    "metadata": {},
                },
                "match_on": ["staging_conversation_id", "message_id"],
            },
        ]

        payload: Dict[str, Any] = {"operation": "compound", "steps": steps, "rollback_on_failure": True}

        print("[EXEC] PersistenceAgent.execute(compound)")
        result = await agent.execute(task_data_or_goal=payload, context={"tenant_id": tenant_id})
        print("[RESULT]", result)
        print("OK")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    return asyncio.run(run_test())


if __name__ == "__main__":
    raise SystemExit(main())
