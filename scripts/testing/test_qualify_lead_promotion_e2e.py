"""E2E: staging lead -> qualify_lead -> promote_staging_lead.

This is an opt-in smoke/E2E script that:
1) Writes a synthetic staging lead + staging conversation + staging message via PersistenceAgent (compound).
2) Sends a LeadsOrchestrator task with intent=qualify_lead for that staging_lead_id.
3) Waits for the LeadsOrchestrator result and asserts promotion occurred.

Run:
  $env:PYTHONIOENCODING='utf-8'
  & ./.venv/Scripts/python.exe scripts/testing/test_qualify_lead_promotion_e2e.py

Optional env:
  TENANT_ID (default: agentic-dev)
  REDIS_URL (default: from .env)
  E2E_TIMEOUT_S (default: 60)

Notes:
- Requires running consumers for: LeadsOrchestrator, RAG Agent, Persistence Agent.
- Uses the typed envelope format stored under the Redis field "data".
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

try:
    import redis  # type: ignore
except Exception as exc:  # pragma: no cover
    raise SystemExit("Missing dependency 'redis'. Install via requirements.txt") from exc

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.envelope import from_redis_message, task as create_task_envelope, to_redis_fields


@dataclass(frozen=True)
class Streams:
    tenant_id: str

    @property
    def leads_tasks(self) -> str:
        return f"{self.tenant_id}:orchestrators:leads:tasks"

    @property
    def leads_results(self) -> str:
        return f"{self.tenant_id}:orchestrators:leads:results"

    @property
    def persistence_tasks(self) -> str:
        return f"{self.tenant_id}:agents:persistence:tasks"

    @property
    def persistence_results(self) -> str:
        return f"{self.tenant_id}:agents:persistence:results"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def wait_for_task_payload(
    *,
    client: "redis.Redis",
    stream: str,
    task_id: str,
    timeout_s: int,
) -> Optional[Dict[str, Any]]:
    """Block until a typed-envelope message with matching task_id appears on stream."""

    deadline = time.time() + max(1, int(timeout_s))

    # Read from the stream tail to avoid scanning massive histories.
    last_id = "$"
    try:
        info = client.xinfo_stream(stream)
        if isinstance(info, dict) and info.get("last-generated-id"):
            last_id = info.get("last-generated-id")
    except Exception:
        last_id = "$"

    while time.time() < deadline:
        remaining_ms = int(max(0, (deadline - time.time())) * 1000)
        block_ms = min(500, remaining_ms) if remaining_ms else 0

        resp = client.xread({stream: last_id}, count=100, block=block_ms)
        if not resp:
            continue

        for _stream_name, messages in resp:
            for msg_id, fields in messages:
                last_id = msg_id
                try:
                    env = from_redis_message(fields)
                except Exception:
                    continue
                if getattr(env, "metadata", None) and env.metadata.task_id == task_id:
                    return env.payload

    return None


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    timeout_s = int(os.getenv("E2E_TIMEOUT_S", "60"))

    # Align with PersistenceAgent tenant→client UUID mapping.
    client_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, tenant_id))
    campaign_id = os.environ.get(
        "CAMPAIGN_ID_PLACEHOLDER",
        "9646f98a-e987-4a8c-b786-9b82ea985d38",
    )

    streams = Streams(tenant_id=tenant_id)

    client = redis.Redis.from_url(redis_url, decode_responses=True)

    print(f"[INFO] tenant={tenant_id}")
    print(f"[INFO] redis_url={'(set)' if bool(os.getenv('REDIS_URL')) else '(default localhost)'}")
    print(f"[INFO] timeout_s={timeout_s}")
    print(f"[INFO] client_id(uuid5)={client_id}")
    print(f"[INFO] campaign_id(placeholder)={campaign_id}")

    # ---------------------------------------------------------------------
    # 1) Write staging data (compound)
    # ---------------------------------------------------------------------
    staging_lead_id = str(uuid.uuid4())
    staging_conversation_id = str(uuid.uuid4())
    staging_message_id = str(uuid.uuid4())

    test_suffix = f"qualify-e2e-{int(time.time())}"
    lead_email = f"{test_suffix}@example-company.com"

    # Strong signals so the scorer promotes (>= 70) without needing email classification.
    staging_message_content = (
        "Hi — I'm the CEO at Example Company. We'd like to schedule a demo this week. "
        "Our budget is around $20k and timeline is ASAP. Can you share pricing and availability?"
    )

    compound_task_id = f"e2e_compound_{uuid.uuid4()}"

    compound_payload: Dict[str, Any] = {
        "operation": "compound",
        "rollback_on_failure": True,
        "continue_on_skip": True,
        "steps": [
            {
                "step_name": "staging_lead",
                "table": "staging_leads",
                "operation": "create",
                "data": {
                    "id": staging_lead_id,
                    "client_id": client_id,
                    "campaign_id": campaign_id,
                    "source": "inbound",
                    "email": lead_email,
                    "first_name": "Pat",
                    "last_name": "Smith",
                    "company_name": "Example Company",
                    "job_title": "CEO",
                    "phone_number": "",
                    "linkedin_url": "",
                    "website_url": "https://example-company.com",
                    "raw_data": {"e2e": True},
                },
            },
            {
                "step_name": "staging_conversation",
                "table": "staging_conversations",
                "operation": "create",
                "data": {
                    "id": staging_conversation_id,
                    "staging_lead_id": "$ref:staging_lead.id",
                    "status": "active",
                    "metadata": {"e2e": True},
                    "thread_id": f"thread-{test_suffix}",
                    "subject": "Demo request",
                    "channel": "email",
                },
            },
            {
                "step_name": "staging_message",
                "table": "staging_messages",
                "operation": "create",
                "data": {
                    "id": staging_message_id,
                    "staging_conversation_id": "$ref:staging_conversation.id",
                    "sender": lead_email,
                    "receiver": "sales@example.com",
                    "content": staging_message_content,
                    "metadata": {"e2e": True},
                    "message_id": f"msg-{test_suffix}",
                },
            },
        ],
    }

    compound_env = create_task_envelope(
        source="e2e_test",
        task_id=compound_task_id,
        payload=compound_payload,
        destination="persistence_agent",
        tenant_id=tenant_id,
    )

    print(f"[INFO] Enqueue staging compound write: task_id={compound_task_id}")
    client.xadd(streams.persistence_tasks, to_redis_fields(compound_env))
    print("[INFO] Waiting for persistence compound result...")
    compound_result = wait_for_task_payload(
        client=client,
        stream=streams.persistence_results,
        task_id=compound_task_id,
        timeout_s=timeout_s,
    )

    if not compound_result or compound_result.get("status") != "success":
        print("[FAIL] staging compound write failed")
        if compound_result:
            print(json.dumps(compound_result, indent=2)[:4000])
        else:
            print("No persistence result received (timeout)")
        return 2

    print("[OK] staging lead+thread created")

    # ---------------------------------------------------------------------
    # 2) Send qualify_lead to LeadsOrchestrator
    # ---------------------------------------------------------------------
    qualify_task_id = f"e2e_qualify_{uuid.uuid4()}"
    # Send intent/ids in multiple common shapes to avoid producer/consumer drift.
    qualify_payload: Dict[str, Any] = {
        "task_id": qualify_task_id,
        "intent": "qualify_lead",
        "staging_lead_id": staging_lead_id,
        "goal": "Qualify staging lead for promotion",
        # Some paths read context from `context`, older ones from `data`.
        "context": {"staging_lead_id": staging_lead_id},
        "data": {"staging_lead_id": staging_lead_id},
        # Some paths expect nested payload (Manager-style wrapping).
        "payload": {
            "intent": "qualify_lead",
            "staging_lead_id": staging_lead_id,
            "context": {"staging_lead_id": staging_lead_id},
            "goal": "Qualify staging lead for promotion",
        },
        "timestamp": _now_iso(),
    }

    qualify_env = create_task_envelope(
        source="e2e_test",
        task_id=qualify_task_id,
        payload=qualify_payload,
        destination="leads_orchestrator",
        tenant_id=tenant_id,
    )

    print(f"[INFO] Enqueue qualify_lead: task_id={qualify_task_id} staging_lead_id={staging_lead_id}")
    client.xadd(streams.leads_tasks, to_redis_fields(qualify_env))
    print("[INFO] Waiting for leads_orchestrator result...")

    leads_result = wait_for_task_payload(
        client=client,
        stream=streams.leads_results,
        task_id=qualify_task_id,
        timeout_s=timeout_s,
    )

    if not leads_result:
        print("[FAIL] no leads_orchestrator result received (timeout)")
        return 3

    if not leads_result.get("success"):
        print("[FAIL] leads_orchestrator returned error")
        print(json.dumps(leads_result, indent=2)[:4000])
        return 4

    if leads_result.get("path") != "qualify_lead":
        print("[FAIL] unexpected leads result path")
        print(json.dumps(leads_result, indent=2)[:4000])
        return 5

    promoted = bool(leads_result.get("promoted"))
    score = (leads_result.get("qualification") or {}).get("score")
    decision = (leads_result.get("qualification") or {}).get("decision")

    print(f"[OK] qualify_lead completed: promoted={promoted} score={score} decision={decision}")

    if not promoted:
        print("[FAIL] expected promotion but promote=False")
        print(json.dumps(leads_result, indent=2)[:4000])
        return 6

    promo = leads_result.get("promotion_result") or {}
    promo_status = promo.get("status") if isinstance(promo, dict) else None
    if promo_status and promo_status != "success":
        print("[FAIL] promotion_result not success")
        print(json.dumps(leads_result, indent=2)[:4000])
        return 7

    print("[PASS] staging lead promotion E2E")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
