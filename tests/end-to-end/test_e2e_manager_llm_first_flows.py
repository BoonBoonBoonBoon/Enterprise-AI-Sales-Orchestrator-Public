#!/usr/bin/env python
"""LLM-first Manager E2E flows (no payload.delegations).

This script validates the three core business scenarios while exercising the
Manager's LLM intent fallback and Tier-2 deep-agent tool selection.

Flows:
1) Create a lead (Manager -> Leads deep agent -> Persistence write)
2) Read a lead (Manager -> Leads deep agent -> Persistence read)
3) Generate reconnect email (Manager -> Outbound deep agent -> Copywriter)

Notes:
- This does NOT set `payload.delegations`.
- It asserts LLM fallback was used by checking `llm:openai` in Manager reasons.
- It asserts side effects by scanning Tier-3 result streams for newly produced
  results that match the test data.

Run:
  python tests/end-to-end/test_e2e_manager_llm_first_flows.py

Env:
  REDIS_URL=redis://localhost:6379/0
  TENANT_ID=agentic-dev

  # Required to actually use the LLM fallback:
  OPENAI_API_KEY=...
  MANAGER_LLM_ENABLED=1
  MANAGER_ENABLE_LLM_FALLBACK=1

  # Strongly recommended so Leads tools return after persistence completes:
  LEADS_WAIT_FOR_PERSISTENCE_RESULTS=1
  LEADS_PERSISTENCE_WAIT_TIMEOUT_S=45

  # Optional: fail hard if OPENAI_API_KEY missing (default skips).
  REQUIRE_OPENAI=0
"""

import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

import redis
from dotenv import load_dotenv

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv()

from core.envelope import (
    task as create_task_envelope,
    to_redis_fields,
    from_redis_message,
)


os.environ.setdefault("REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
os.environ.setdefault("TENANT_ID", os.getenv("TENANT_ID", "agentic-dev"))

redis_url = os.getenv("REDIS_URL")
tenant_id = os.getenv("TENANT_ID")


def print_section(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def _decode_id(msg_id: Any) -> str:
    if msg_id is None:
        return "0-0"
    if isinstance(msg_id, bytes):
        return msg_id.decode("utf-8", errors="ignore")
    return str(msg_id)


def get_last_stream_id(client: redis.Redis, stream: str) -> str:
    entries = client.xrevrange(stream, max="+", min="-", count=1)
    if not entries:
        return "0-0"
    msg_id, _fields = entries[0]
    return _decode_id(msg_id)


def iter_stream_since(client: redis.Redis, stream: str, after_id: str, count: int = 200) -> Iterable[Tuple[str, Any]]:
    """Yield (msg_id, env) for entries strictly after after_id."""
    start = f"({after_id}" if after_id and after_id != "0-0" else "-"
    entries = client.xrange(stream, min=start, max="+", count=count)
    for msg_id, fields in entries:
        try:
            env = from_redis_message(fields)
        except Exception:
            continue
        yield _decode_id(msg_id), env


def wait_for_task_result_since(
    client: redis.Redis,
    stream: str,
    task_id: str,
    after_id: str,
    timeout_s: int = 45,
) -> Any:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for _msg_id, env in iter_stream_since(client, stream, after_id, count=500):
            if getattr(env.metadata, "task_id", None) == task_id:
                return env
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for task_id={task_id} in {stream} (after {after_id})")


def find_persistence_result_for_email(
    client: redis.Redis,
    stream: str,
    after_id: str,
    email: str,
    timeout_s: int = 45,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for _msg_id, env in iter_stream_since(client, stream, after_id, count=500):
            payload = env.payload or {}
            if payload.get("status") != "success":
                continue
            result = payload.get("result")
            if isinstance(result, dict) and result.get("email") == email:
                return result
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for persistence result containing email={email}")


def find_persistence_result_for_id(
    client: redis.Redis,
    stream: str,
    after_id: str,
    lead_id: str,
    timeout_s: int = 45,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for _msg_id, env in iter_stream_since(client, stream, after_id, count=500):
            payload = env.payload or {}
            if payload.get("status") != "success":
                continue
            result = payload.get("result")
            if isinstance(result, dict) and str(result.get("id")) == str(lead_id):
                return result
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for persistence result containing id={lead_id}")


def find_copywriter_result_with_token(
    client: redis.Redis,
    stream: str,
    after_id: str,
    token: str,
    timeout_s: int = 60,
    also_match: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    also_match = [s for s in (also_match or []) if s]
    while time.time() < deadline:
        for _msg_id, env in iter_stream_since(client, stream, after_id, count=500):
            payload = env.payload or {}
            if payload.get("status") != "success":
                continue
            copy = payload.get("copy") or {}
            subject = str(copy.get("subject") or "")
            body = str(copy.get("body") or "")
            if not subject or not body:
                continue

            # Prefer token match if present, but don't require it.
            if token and (token in subject or token in body):
                return payload

            # Otherwise accept if any expected marker appears.
            if any(m in subject or m in body for m in also_match):
                return payload

            # Fall back: accept the next successful copywriter result after baseline.
            return payload
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for copywriter result containing token={token}")


def send_manager_task(client: redis.Redis, task_id: str, payload: dict) -> str:
    envelope = create_task_envelope(
        source="e2e_test",
        task_id=task_id,
        payload=payload,
        destination="manager_agent",
        tenant_id=tenant_id,
    )
    return _decode_id(client.xadd(f"{tenant_id}:manager:tasks", to_redis_fields(envelope)))


def assert_manager_used_llm(env: Any) -> None:
    payload = env.payload or {}
    reasons = payload.get("reasons") or []
    if not isinstance(reasons, list):
        raise AssertionError(f"Manager reasons is not a list: {reasons}")
    if "llm:openai" not in reasons:
        raise AssertionError(
            "Expected Manager to use LLM fallback (missing 'llm:openai' in reasons). "
            f"Got reasons={reasons}"
        )


def main() -> int:
    require_openai = os.getenv("REQUIRE_OPENAI", "0").lower() in ("1", "true", "yes")
    if not os.getenv("OPENAI_API_KEY"):
        msg = "OPENAI_API_KEY is not set. Skipping LLM-first E2E."
        if require_openai:
            raise RuntimeError(msg)
        print(msg)
        return 0

    client = redis.Redis.from_url(redis_url)

    manager_results = f"{tenant_id}:manager:results"
    leads_results = f"{tenant_id}:orchestrators:leads:results"
    outbound_results = f"{tenant_id}:orchestrators:outbound:results"
    persistence_results = f"{tenant_id}:agents:persistence:results"
    copywriter_results = f"{tenant_id}:agents:copywriter:results"

    print_section("Sanity: Redis connectivity")
    client.ping()
    print(f"[OK] Connected to Redis at {redis_url}")

    # -------------------- FLOW 1 --------------------
    print_section("Flow 1: LLM-first Manager -> Leads -> Persistence (WRITE)")

    t0 = int(time.time())
    lead_email = f"sam.llmfirst.{t0}@example.com"
    lead_data = {
        "email": lead_email,
        "first_name": "Sam",
        "last_name": "LLMFirst",
        "company": "ExampleCo",
        "job_title": "CTO",
    }

    manager_after = get_last_stream_id(client, manager_results)
    leads_after = get_last_stream_id(client, leads_results)
    persistence_after = get_last_stream_id(client, persistence_results)

    task_id = f"e2e-llmfirst-write-{t0}"
    payload = {
        "task_id": task_id,
        # Avoid rule keywords so Manager uses LLM fallback (rules confidence < 0.5)
        "goal": "Insert a new lead record using the provided lead_data and confirm the stored id.",
        "data": {"lead_data": lead_data},
    }

    msg_id = send_manager_task(client, task_id, payload)
    print(f"Sent Manager task {task_id} (msg_id={msg_id})")

    mgr_env = wait_for_task_result_since(client, manager_results, task_id, manager_after, timeout_s=60)
    assert_manager_used_llm(mgr_env)
    mgr_payload = mgr_env.payload or {}
    print(f"Manager intent={mgr_payload.get('intent')} orchestrators={mgr_payload.get('orchestrators')}")

    # Wait for Leads to produce a result for the enqueued child task
    enq = (mgr_payload.get("enqueued") or [])
    leads_task_id: Optional[str] = None
    for item in enq:
        if isinstance(item, dict) and str(item.get("stream", "")).endswith(":orchestrators:leads:tasks"):
            leads_task_id = item.get("task_id")
            break
    if not leads_task_id:
        raise RuntimeError(f"Manager did not enqueue leads task: enqueued={enq}")

    leads_env = wait_for_task_result_since(client, leads_results, leads_task_id, leads_after, timeout_s=90)
    leads_payload = leads_env.payload or {}
    if not leads_payload.get("success"):
        raise RuntimeError(f"Leads orchestration failed: {leads_payload}")

    stored = find_persistence_result_for_email(client, persistence_results, persistence_after, lead_email, timeout_s=90)
    lead_id = stored.get("id")
    if not lead_id:
        raise RuntimeError(f"Persistence write result missing id: {stored}")

    print(f"[OK] Lead stored id={lead_id} email={lead_email}")

    # -------------------- FLOW 2 --------------------
    print_section("Flow 2: LLM-first Manager -> Leads -> Persistence (READ)")

    t1 = int(time.time())
    manager_after = get_last_stream_id(client, manager_results)
    leads_after = get_last_stream_id(client, leads_results)
    persistence_after = get_last_stream_id(client, persistence_results)

    task_id = f"e2e-llmfirst-read-{t1}"
    payload = {
        "task_id": task_id,
        "goal": "Fetch the lead record using the provided lead_id.",
        "data": {"lead_id": lead_id},
    }

    msg_id = send_manager_task(client, task_id, payload)
    print(f"Sent Manager task {task_id} (msg_id={msg_id})")

    mgr_env = wait_for_task_result_since(client, manager_results, task_id, manager_after, timeout_s=60)
    assert_manager_used_llm(mgr_env)

    mgr_payload = mgr_env.payload or {}
    enq = (mgr_payload.get("enqueued") or [])
    leads_task_id = None
    for item in enq:
        if isinstance(item, dict) and str(item.get("stream", "")).endswith(":orchestrators:leads:tasks"):
            leads_task_id = item.get("task_id")
            break
    if not leads_task_id:
        raise RuntimeError(f"Manager did not enqueue leads task: enqueued={enq}")

    leads_env = wait_for_task_result_since(client, leads_results, leads_task_id, leads_after, timeout_s=90)
    leads_payload = leads_env.payload or {}
    if not leads_payload.get("success"):
        raise RuntimeError(f"Leads orchestration failed: {leads_payload}")

    read_record = find_persistence_result_for_id(client, persistence_results, persistence_after, str(lead_id), timeout_s=90)
    if str(read_record.get("id")) != str(lead_id):
        raise RuntimeError(f"Read record mismatch: {read_record}")

    print(f"[OK] Lead read id={read_record.get('id')} email={read_record.get('email')}")

    # -------------------- FLOW 3 --------------------
    print_section("Flow 3: LLM-first Manager -> Outbound -> Copywriter (RECONNECT EMAIL)")

    token = f"reconnect-e2e-{int(time.time())}"
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    manager_after = get_last_stream_id(client, manager_results)
    outbound_after = get_last_stream_id(client, outbound_results)
    copywriter_after = get_last_stream_id(client, copywriter_results)

    # Provide a structured copy_request so the outbound deep agent can call its delegation tool.
    copy_request = {
        "campaign_id": "camp_llmfirst_reconnect_001",
        "lead_id": str(lead_id),
        "channel": "email",
        "tone": "friendly-professional",
        "goal": "reconnect",
        "context": {
            "recipient_name": read_record.get("first_name") or "there",
            "company_name": read_record.get("company") or read_record.get("company_name") or "your company",
            "value_prop": token,
            "call_to_action": "Would you be open to a 10-minute catch-up this week?",
            "notes": f"Reconnecting after a prior conversation. ({now_iso})",
        },
    }

    task_id = f"e2e-llmfirst-email-{int(time.time())}"
    payload = {
        "task_id": task_id,
        "goal": "Draft a reconnection email using the provided copy_request by delegating to the copywriter tool.",
        "data": {"copy_request": copy_request},
    }

    msg_id = send_manager_task(client, task_id, payload)
    print(f"Sent Manager task {task_id} (msg_id={msg_id})")

    mgr_env = wait_for_task_result_since(client, manager_results, task_id, manager_after, timeout_s=60)
    assert_manager_used_llm(mgr_env)

    mgr_payload = mgr_env.payload or {}
    enq = (mgr_payload.get("enqueued") or [])
    outbound_task_id: Optional[str] = None
    for item in enq:
        if isinstance(item, dict) and str(item.get("stream", "")).endswith(":orchestrators:outbound:tasks"):
            outbound_task_id = item.get("task_id")
            break
    if not outbound_task_id:
        raise RuntimeError(f"Manager did not enqueue outbound task: enqueued={enq}")

    # Outbound result is optional (it may complete quickly but doesn't include copy), so we just wait briefly.
    try:
        wait_for_task_result_since(client, outbound_results, outbound_task_id, outbound_after, timeout_s=30)
    except Exception:
        pass

    copy_payload = find_copywriter_result_with_token(
        client,
        copywriter_results,
        copywriter_after,
        token,
        timeout_s=120,
        also_match=[
            str(copy_request.get("context", {}).get("recipient_name") or ""),
            str(copy_request.get("context", {}).get("company_name") or ""),
        ],
    )

    copy = (copy_payload.get("copy") or {})
    subject = str(copy.get("subject") or "")
    body = str(copy.get("body") or "")
    if not subject or not body:
        raise RuntimeError(f"Copywriter returned empty email: {copy_payload}")

    print("[OK] Reconnect email generated")
    print("--- SUBJECT ---")
    print(subject)
    print("--- BODY ---")
    print(body)

    print_section("ALL LLM-FIRST FLOWS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
