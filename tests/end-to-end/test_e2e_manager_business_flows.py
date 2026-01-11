#!/usr/bin/env python
"""Manager-driven business-flow E2E tests.

Validates the three concrete scenarios requested:
1) Manager triggers a persistence write (create lead)
2) Manager triggers a persistence read (retrieve lead)
3) Manager retrieve + generate a reconnect email (via outbound/copywriter)

This script is intentionally deterministic-first:
- Manager routes to Tier-2 orchestrators by rules
- Leads/Outbound orchestrators execute explicit `payload.delegations` deterministically
- Tier-3 agents publish results to canonical `{tenant}:...:results` streams

Run (using existing consumers, e.g. Docker stack):
  python tests/end-to-end/test_e2e_manager_business_flows.py

Optionally override:
  REDIS_URL=redis://localhost:6379/0
  TENANT_ID=agentic-dev
"""

import os
import sys
import time
from datetime import datetime, timezone

import pytest
import redis
from dotenv import load_dotenv

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv()

from core.envelope import task as create_task_envelope, to_redis_fields, from_redis_message

os.environ.setdefault("REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
os.environ.setdefault("TENANT_ID", os.getenv("TENANT_ID", "agentic-dev"))

redis_url = os.getenv("REDIS_URL")
tenant_id = os.getenv("TENANT_ID")


# NOTE: These are true end-to-end tests that require live consumers for:
# - Tier 1 Manager
# - Tier 2 Leads + Outbound orchestrators
# - Tier 3 Persistence + Copywriter agents
# running against the configured Redis instance.
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_E2E") != "1",
    reason="Requires live Manager/Orchestrators/Agents (set RUN_LIVE_E2E=1)",
)


def print_section(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def _stream_tail(client: redis.Redis, stream: str, count: int = 50):
    entries = client.xrevrange(stream, max="+", min="-", count=count)
    for msg_id, fields in entries:
        try:
            env = from_redis_message(fields)
        except Exception:
            continue
        yield msg_id, env


def wait_for_stream_len_increase(client: redis.Redis, stream: str, baseline: int, timeout_s: int = 30) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        cur = client.xlen(stream)
        if cur > baseline:
            return cur
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for stream len increase: {stream}")


def wait_for_task_result(client: redis.Redis, stream: str, task_id: str, timeout_s: int = 30):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for _msg_id, env in _stream_tail(client, stream, count=100):
            if env.metadata.task_id == task_id:
                return env
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for task_id={task_id} in {stream}")


def send_manager_task(client: redis.Redis, task_id: str, payload: dict) -> str:
    envelope = create_task_envelope(
        source="e2e_test",
        task_id=task_id,
        payload=payload,
        destination="manager_agent",
        tenant_id=tenant_id,
    )
    return client.xadd(f"{tenant_id}:manager:tasks", to_redis_fields(envelope))


@pytest.fixture(scope="session")
def client() -> redis.Redis:
    """Sync Redis client for E2E runs."""
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    r.ping()
    return r


@pytest.fixture(scope="session")
def lead_id(client: redis.Redis) -> str:
    created = test_manager_write_lead(client)
    return created["lead_id"]


@pytest.fixture(scope="session")
def lead_record(client: redis.Redis, lead_id: str) -> dict:
    return test_manager_read_lead(client, lead_id)


def test_manager_write_lead(client: redis.Redis) -> dict:
    print_section("E2E 1: Manager -> Leads -> Persistence (WRITE)")

    leads_results = f"{tenant_id}:orchestrators:leads:results"
    persistence_tasks = f"{tenant_id}:agents:persistence:tasks"
    persistence_results = f"{tenant_id}:agents:persistence:results"

    baseline = {
        "leads_results": client.xlen(leads_results),
        "persistence_tasks": client.xlen(persistence_tasks),
        "persistence_results": client.xlen(persistence_results),
    }
    print("Baseline:")
    for k, v in baseline.items():
        print(f"  {k}: {v}")

    task_id = f"e2e-manager-write-{int(time.time())}"
    lead = {
        "email": f"sam.reconnect.{int(time.time())}@example.com",
        "first_name": "Sam",
        "last_name": "Reconnect",
        "company": "ExampleCo",
        "job_title": "CTO",
    }

    payload = {
        "task_id": task_id,
        "goal": "Find leads and write a single lead record",
        "delegations": {
            "write_lead": lead,
        },
    }

    msg_id = send_manager_task(client, task_id, payload)
    print(f"Sent manager task: {task_id} (msg_id={msg_id})")

    wait_for_stream_len_increase(client, leads_results, baseline["leads_results"], timeout_s=30)

    # Find the newest Leads result and extract delegation output
    leads_env = next(_stream_tail(client, leads_results, count=10))[1]
    leads_payload = leads_env.payload or {}
    delegations = leads_payload.get("delegations") or {}
    write_out = delegations.get("write_lead") or {}

    lead_id = write_out.get("lead_id")
    persistence_task_id = write_out.get("persistence_task_id")

    if not lead_id or not persistence_task_id:
        raise RuntimeError(f"Leads write delegation output missing lead_id/persistence_task_id: {write_out}")

    print(f"Lead enqueued: lead_id={lead_id}")
    print(f"Persistence write task_id={persistence_task_id}")

    # Ensure persistence task was enqueued and completed
    wait_for_stream_len_increase(client, persistence_tasks, baseline["persistence_tasks"], timeout_s=30)
    pers_env = wait_for_task_result(client, persistence_results, persistence_task_id, timeout_s=30)
    pers_payload = pers_env.payload or {}

    if pers_payload.get("status") != "success":
        raise RuntimeError(f"Persistence write failed: {pers_payload}")

    stored = (pers_payload.get("result") or {})
    if stored.get("id") != lead_id:
        raise RuntimeError(f"Persistence stored id mismatch: expected={lead_id} got={stored.get('id')}")

    print("[OK] Manager-driven write completed")
    return {
        "lead_id": lead_id,
        "lead": lead,
    }


def test_manager_read_lead(client: redis.Redis, lead_id: str) -> dict:
    print_section("E2E 2: Manager -> Leads -> Persistence (READ)")

    leads_results = f"{tenant_id}:orchestrators:leads:results"
    persistence_results = f"{tenant_id}:agents:persistence:results"

    baseline = {
        "leads_results": client.xlen(leads_results),
        "persistence_results": client.xlen(persistence_results),
    }
    print("Baseline:")
    for k, v in baseline.items():
        print(f"  {k}: {v}")

    task_id = f"e2e-manager-read-{int(time.time())}"
    payload = {
        "task_id": task_id,
        "goal": "Find leads and retrieve a lead record by id",
        "delegations": {
            "read_lead": {"lead_id": lead_id},
        },
    }

    msg_id = send_manager_task(client, task_id, payload)
    print(f"Sent manager task: {task_id} (msg_id={msg_id})")

    wait_for_stream_len_increase(client, leads_results, baseline["leads_results"], timeout_s=30)

    leads_env = next(_stream_tail(client, leads_results, count=10))[1]
    leads_payload = leads_env.payload or {}
    delegations = leads_payload.get("delegations") or {}
    read_out = delegations.get("read_lead") or {}

    persistence_task_id = read_out.get("persistence_task_id")
    if not persistence_task_id:
        raise RuntimeError(f"Leads read delegation output missing persistence_task_id: {read_out}")

    pers_env = wait_for_task_result(client, persistence_results, persistence_task_id, timeout_s=30)
    pers_payload = pers_env.payload or {}

    if pers_payload.get("status") != "success":
        raise RuntimeError(f"Persistence read failed: {pers_payload}")

    record = pers_payload.get("result")
    if not isinstance(record, dict) or record.get("id") != lead_id:
        raise RuntimeError(f"Unexpected persistence read record: {record}")

    print("[OK] Manager-driven read completed")
    return record


def test_manager_retrieve_then_reconnect_email(client: redis.Redis, lead_record: dict) -> None:
    print_section("E2E 3: Manager retrieve -> outbound/copywriter reconnect email")

    copywriter_results = f"{tenant_id}:agents:copywriter:results"

    baseline = {
        "copywriter_results": client.xlen(copywriter_results),
    }
    print("Baseline:")
    for k, v in baseline.items():
        print(f"  {k}: {v}")

    lead_id = lead_record.get("id")
    recipient_name = lead_record.get("first_name") or "there"
    company_name = lead_record.get("company") or lead_record.get("company_name") or "your company"

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    task_id = f"e2e-manager-reconnect-email-{int(time.time())}"
    payload = {
        "task_id": task_id,
        # Use rule-matching keywords so Manager routes to outbound deterministically.
        "goal": "Write email follow up outreach to reconnect",
        "delegations": {
            "copywriter": {
                "campaign_id": "camp_e2e_reconnect_001",
                "lead_id": lead_id,
                "channel": "email",
                "tone": "friendly-professional",
                "goal": "reconnect",
                # Outbound orchestrator enqueues to copywriter; copywriter expects {type, context, tone, ...}
                "type": "email",
                "context": {
                    "recipient_name": recipient_name,
                    "company_name": company_name,
                    "value_prop": "a quick idea that could save your team time",
                    "call_to_action": "Would you be open to a 10-minute catch-up this week?",
                    "notes": f"We spoke previously; following up to reconnect. ({now_iso})",
                },
            }
        },
    }

    msg_id = send_manager_task(client, task_id, payload)
    print(f"Sent manager task: {task_id} (msg_id={msg_id})")

    # Copywriter path can take longer when outbound deep agent spins up, so allow a longer wait.
    wait_for_stream_len_increase(client, copywriter_results, baseline["copywriter_results"], timeout_s=120)

    copy_env = next(_stream_tail(client, copywriter_results, count=10))[1]
    copy_payload = copy_env.payload or {}
    if copy_payload.get("status") != "success":
        raise RuntimeError(f"Copywriter failed: {copy_payload}")

    copy = (copy_payload.get("copy") or {})
    subject = copy.get("subject") or ""
    body = copy.get("body") or ""

    if not subject or not body:
        raise RuntimeError(f"Copywriter returned empty email: {copy}")

    print("[OK] Reconnect email generated")
    print("--- SUBJECT ---")
    print(subject)
    print("--- BODY ---")
    print(body)


def main() -> None:
    print("\n" + "=" * 70)
    print("  AGENTIC SYSTEM - MANAGER BUSINESS-FLOW E2E")
    print("=" * 70)
    print(f"\nTenant: {tenant_id}")
    print(f"Redis: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")

    client = redis.Redis.from_url(redis_url, decode_responses=True)

    created = test_manager_write_lead(client)
    lead_id = created["lead_id"]

    record = test_manager_read_lead(client, lead_id)
    test_manager_retrieve_then_reconnect_email(client, record)

    print_section("SUMMARY")
    print("[OK] All three manager-driven business flows completed")


if __name__ == "__main__":
    main()
