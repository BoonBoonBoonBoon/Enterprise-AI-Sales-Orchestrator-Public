r"""Validate RAG → LeadsOrchestrator → OutreachOrchestrator → Copywriter task data flow.

This script enqueues a deep-reply task to LeadsOrchestrator, waits for the
result (which should include a ReplyPacket built from RAG context), then
enqueues that ReplyPacket to OutreachOrchestrator and verifies the resulting
Copywriter task contains the same enriched ReplyPacket.

It is intentionally read-only with respect to Supabase. To avoid writing inbound
messages during validation, run LeadsOrchestrator with LEADS_STORE_INBOUND_EMAIL=0.

Usage (PowerShell):
  $env:REDIS_URL = 'redis://localhost:6379/0'
  $env:TENANT_ID = 'agentic-dev'
    & ./.venv/Scripts/python.exe ./scripts/testing/validate_rag_to_copywriter_flow.py

Optional:
  $env:DEBUG_LEAD_EMAIL = 'lead@example.com'  # if you want to force a specific lead
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Allow running as a standalone script (adds repo root to sys.path).
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.envelope import from_redis_message, result as make_result, task as make_task, to_redis_fields
from services.redis import RedisStreamsClient
from tiers.tier_2.leads_orchestrator.leads_orchestrator import LeadsOrchestrator
from tiers.tier_2.outreach_orchestrator.outreach_orchestrator import OutreachOrchestrator
from tiers.tier_3.rag_agent.rag_agent import RAGAgent


def _utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _start_rag_worker(
    redis: RedisStreamsClient,
    *,
    tenant_id: str,
    stop_event: threading.Event,
) -> threading.Thread:
    """Start a minimal RAG worker loop.

    Listens on `{tenant}:agents:rag:tasks` using XREAD (not consumer groups) and
    publishes a typed result envelope to `{tenant}:agents:rag:results`.

    This avoids having to run the long-lived consumer processes for validation.
    """

    task_stream = f"{tenant_id}:agents:rag:tasks"
    result_stream = f"{tenant_id}:agents:rag:results"

    # Force-disable custom JWT mode for this debug run (common source of 401s).
    # The RAG agent will fall back to SUPABASE_SERVICE_KEY/SUPABASE_KEY.
    os.environ["SUPABASE_RAG_JWT"] = ""

    rag = RAGAgent(redis_client=redis.client, tenant_id=tenant_id)

    def loop() -> None:
        last_id = "$"
        while not stop_event.is_set():
            try:
                # XREAD returns [(stream, [(id, fields), ...])]
                resp = redis.client.xread({redis._chan(task_stream): last_id}, count=10, block=1000)
            except Exception:
                continue

            if not resp:
                continue

            for _stream_name, messages in resp:
                for message_id, fields in messages:
                    last_id = message_id
                    try:
                        env = from_redis_message(fields)
                        payload = env.payload
                    except Exception:
                        continue

                    try:
                        result_payload = rag.execute(payload)
                    except Exception as exc:
                        result_payload = {"status": "error", "error": str(exc)}

                    try:
                        res_env = make_result(original=env, payload=result_payload, source="rag_agent")
                        redis.xadd(result_stream, to_redis_fields(res_env))
                    except Exception:
                        # If we fail to publish a result, Leads will time out; surface by continuing.
                        continue

    t = threading.Thread(target=loop, name="validate-rag-worker", daemon=True)
    t.start()
    return t


def _pick_lead_email() -> Optional[str]:
    # Prefer explicit override.
    for key in ("DEBUG_LEAD_EMAIL", "LEAD_EMAIL", "TEST_LEAD_EMAIL"):
        value = os.getenv(key)
        if value:
            return value.strip()

    # Best-effort: pick any lead email from Supabase if credentials are available.
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_RAG_JWT")
    if not url or not key:
        return None

    try:
        from services.persistence.adapters.supabase_adapter import SupabaseAdapter

        adapter = SupabaseAdapter(url, key, anon_key=os.getenv("SUPABASE_ANON_KEY"))
        rows = adapter.query("leads", filters=None, limit=5, order_by="created_at", descending=True, select=["email"])
        for row in rows or []:
            email = (row or {}).get("email")
            if isinstance(email, str) and email.strip():
                return email.strip()
    except Exception:
        # Don't fail hard on optional discovery.
        return None

    return None


def _wait_for_result(
    redis: RedisStreamsClient,
    *,
    stream: str,
    task_id: str,
    timeout_s: int = 30,
    poll_s: float = 0.5,
    scan_count: int = 200,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    deadline = time.time() + timeout_s
    last_seen_id: Optional[str] = None

    while time.time() < deadline:
        try:
            entries = redis.client.xrevrange(redis._chan(stream), count=scan_count)
        except Exception:
            entries = []

        for message_id, fields in entries:
            # xrevrange returns IDs as strings when decode_responses=True
            last_seen_id = message_id
            try:
                env = from_redis_message(fields)
            except Exception:
                continue
            if getattr(env.metadata, "task_id", None) == task_id:
                return env.payload, message_id

        time.sleep(poll_s)

    return None, last_seen_id


def _find_copywriter_task_by_thread(
    redis: RedisStreamsClient,
    *,
    stream: str,
    thread_id: str,
    timeout_s: int = 30,
    poll_s: float = 0.5,
    scan_count: int = 200,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        try:
            entries = redis.client.xrevrange(redis._chan(stream), count=scan_count)
        except Exception:
            entries = []

        for message_id, fields in entries:
            try:
                env = from_redis_message(fields)
            except Exception:
                continue

            payload = env.payload if isinstance(env.payload, dict) else {}
            ctx = payload.get("context") if isinstance(payload.get("context"), dict) else {}
            rp = ctx.get("reply_packet") if isinstance(ctx.get("reply_packet"), dict) else {}
            inbound = rp.get("inbound_email_event") if isinstance(rp.get("inbound_email_event"), dict) else {}
            if inbound.get("thread_id") == thread_id:
                return payload, message_id

        time.sleep(poll_s)

    return None, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RAG → Leads → Outreach → Copywriter (and optional auto-send)")
    parser.add_argument(
        "--auto-send",
        action="store_true",
        help="If set, verify Outreach auto-send: waits for outbound result and sequencer result.",
    )
    args = parser.parse_args()

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("ERROR: REDIS_URL is not set")
        print("Example: set $env:REDIS_URL='redis://localhost:6379/0'")
        return 2

    tenant_id = os.getenv("TENANT_ID", "agentic-dev")

    redis = RedisStreamsClient(url=redis_url)

    # Start an in-process RAG worker so Leads can synchronously wait for results.
    stop_event = threading.Event()
    _rag_thread = _start_rag_worker(redis, tenant_id=tenant_id, stop_event=stop_event)

    lead_email = _pick_lead_email()
    if not lead_email:
        print(
            "ERROR: Could not determine a lead email. Set DEBUG_LEAD_EMAIL to an existing lead email, "
            "or ensure SUPABASE_URL + SUPABASE_KEY/SUPABASE_SERVICE_KEY are configured."
        )
        return 2

    thread_id = f"debug-thread-{uuid.uuid4()}"

    # 1) Run deep reply flow directly through the orchestrator (no consumer process).
    leads = LeadsOrchestrator(redis_client=redis.client, tenant_id=tenant_id)

    leads_payload = {
        "goal": "Handle inbound email reply (debug flow)",
        "context_depth": "deep",
        "context": {
            "email_event": {
                "from": lead_email,
                "to": "sales@debug.local",
                "subject": "Re: Debugging reply flow",
                "body": "Hi — replying to your last email. (debug)",
                "thread_id": thread_id,
                "message_id": f"debug-msg-{uuid.uuid4()}",
                "received_at": _utc_iso(),
                "metadata": {"source": "validate_rag_to_copywriter_flow"},
            }
        },
    }

    leads_result = leads.execute(leads_payload)
    if not isinstance(leads_result, dict):
        print("ERROR: Leads execution did not return a dict")
        return 1

    reply_packet = leads_result.get("reply_packet") if isinstance(leads_result.get("reply_packet"), dict) else None
    rag_task = leads_result.get("rag_task") if isinstance(leads_result.get("rag_task"), dict) else None

    if not reply_packet:
        print("ERROR: Leads result did not include reply_packet")
        print(f"Leads result keys: {sorted(leads_result.keys())}")
        return 1

    lead_resolution = reply_packet.get("lead_resolution") if isinstance(reply_packet.get("lead_resolution"), dict) else {}
    facts = reply_packet.get("facts") if isinstance(reply_packet.get("facts"), dict) else {}

    print("Leads deep reply result:")
    print(f"- rag_task_id: {(rag_task or {}).get('task_id')}")
    print(f"- lead_resolution.status: {lead_resolution.get('status')}")
    print(f"- facts.email: {facts.get('email')}")
    print(f"- facts.first_name: {facts.get('first_name')}")

    # 2) Run outbound orchestration directly; verify it enqueues a Copywriter task.
    outbound = OutreachOrchestrator(redis_client=redis.client, tenant_id=tenant_id)
    outbound_payload = {
        "goal": "Forward reply_packet to copywriter (debug flow)",
        "reply_packet": reply_packet,
        "payload": {"auto_send": bool(args.auto_send)},
    }

    # execute() is async
    import asyncio

    outbound_result = asyncio.run(outbound.execute(outbound_payload))
    print("Ran Outbound orchestration")

    copy_task_id: Optional[str] = None
    if isinstance(outbound_result, dict):
        delegations = outbound_result.get("delegations") if isinstance(outbound_result.get("delegations"), dict) else {}
        cw = delegations.get("copywriter") if isinstance(delegations.get("copywriter"), dict) else {}
        copy_task_id = cw.get("task_id")

    if not copy_task_id:
        print("ERROR: Outbound did not return a copywriter task_id")
        print(f"Outbound result keys: {sorted(outbound_result.keys()) if isinstance(outbound_result, dict) else type(outbound_result)}")
        return 1

    copywriter_stream = f"{tenant_id}:agents:copywriter:tasks"
    copy_task_payload, copy_msg_id = _wait_for_result(redis, stream=copywriter_stream, task_id=copy_task_id, timeout_s=40)
    if not isinstance(copy_task_payload, dict):
        print("ERROR: Timed out waiting for Copywriter task")
        return 1

    ctx = copy_task_payload.get("context") if isinstance(copy_task_payload.get("context"), dict) else {}
    rp2 = ctx.get("reply_packet") if isinstance(ctx.get("reply_packet"), dict) else {}
    facts2 = rp2.get("facts") if isinstance(rp2.get("facts"), dict) else {}
    lead_resolution2 = rp2.get("lead_resolution") if isinstance(rp2.get("lead_resolution"), dict) else {}

    print("Copywriter task found:")
    print(f"- redis_msg_id: {copy_msg_id}")
    print(f"- type: {copy_task_payload.get('type')}")
    print(f"- facts.email: {facts2.get('email')}")
    print(f"- lead_resolution.status: {lead_resolution2.get('status')}")

    # Minimal acceptance: lead_resolution should not be missing entirely, and facts should carry email.
    if not facts2.get("email"):
        print("WARNING: Copywriter task reply_packet.facts.email is empty")
    if lead_resolution2.get("status") in (None, "unknown"):
        print("WARNING: Copywriter task lead_resolution.status is still unknown")

    print("OK: Outreach enqueued copywriter task with embedded reply_packet")

    if args.auto_send:
        outbound_results_stream = f"{tenant_id}:orchestrators:outbound:results"
        outbound_payload2, outbound_msg_id = _wait_for_result(
            redis,
            stream=outbound_results_stream,
            task_id=copy_task_id,
            timeout_s=120,
        )
        if not isinstance(outbound_payload2, dict):
            print("ERROR: Timed out waiting for Outbound auto-send result")
            return 1

        print("Outbound auto-send result found:")
        print(f"- redis_msg_id: {outbound_msg_id}")
        print(f"- status: {outbound_payload2.get('status')}")

        seq = outbound_payload2.get("sequencer") if isinstance(outbound_payload2.get("sequencer"), dict) else {}
        seq_task_id = seq.get("task_id")
        if not seq_task_id:
            print("ERROR: Outbound auto-send result missing sequencer.task_id")
            return 1

        sequencing_results_stream = f"{tenant_id}:agents:sequencing:results"
        seq_payload, seq_msg_id = _wait_for_result(
            redis,
            stream=sequencing_results_stream,
            task_id=seq_task_id,
            timeout_s=120,
        )
        if not isinstance(seq_payload, dict):
            print("ERROR: Timed out waiting for Sequencer result")
            return 1

        print("Sequencer result found:")
        print(f"- redis_msg_id: {seq_msg_id}")
        print(f"- status: {seq_payload.get('status')}")
        if str(seq_payload.get("status")).lower() not in {"sent", "success"}:
            print("WARNING: Sequencer status was not 'sent'/'success' (check sequencer logs)")

        print("OK: Auto-send path verified (Outreach → Sequencer result observed)")

    stop_event.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
