"""Live inbound E2E smoke script.

Starts the Tier-2 Inbound Orchestrator consumer, publishes a few inbound email
examples into Redis Streams, prints the resulting classification + routing,
and then shuts the consumer down.

Prereqs:
- Redis reachable via REDIS_URL (default: redis://localhost:6379/0)

Usage (PowerShell):
  $env:REDIS_URL='redis://localhost:6380/0'
  $env:TENANT_ID='agentic-dev'
  & '.venv/Scripts/python.exe' scripts/testing/inbound_e2e_live.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any, Dict, Tuple

import redis

# Ensure project root on sys.path when run as a script.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.envelope import from_redis_message, task as create_task_envelope, to_redis_fields


def _python_executable() -> str:
    venv_python = os.path.join(REPO_ROOT, ".venv", "Scripts", "python.exe")
    return venv_python if os.path.exists(venv_python) else sys.executable


def _get_last_id(client: redis.Redis, stream: str) -> str:
    entries = client.xrevrange(stream, max="+", min="-", count=1)
    if not entries:
        return "0-0"
    msg_id, _fields = entries[0]
    return msg_id.decode("utf-8", errors="ignore") if isinstance(msg_id, bytes) else str(msg_id)


def _wait_for_result(
    client: redis.Redis,
    stream: str,
    task_id: str,
    after_id: str,
    timeout_s: int = 20,
) -> Tuple[str, Any]:
    deadline = time.time() + timeout_s
    start = f"({after_id}" if after_id and after_id != "0-0" else "-"

    while time.time() < deadline:
        for msg_id, fields in client.xrange(stream, min=start, max="+", count=200):
            try:
                env = from_redis_message(fields)
            except Exception:
                continue
            if getattr(env.metadata, "task_id", None) == task_id:
                decoded_id = msg_id.decode("utf-8", errors="ignore") if isinstance(msg_id, bytes) else str(msg_id)
                return decoded_id, env
        time.sleep(0.25)

    raise TimeoutError(f"Timed out waiting for task_id={task_id} in {stream}")


def _send_inbound(
    client: redis.Redis,
    *,
    tenant_id: str,
    stream: str,
    task_id: str,
    from_email: str,
    subject: str,
    body: str,
    pre_filter: Dict[str, Any] | None = None,
) -> str:
    inbound_payload = {
        "task_id": task_id,
        "intent": "inbound",
        "context": {
            "email_event": {
                "message_id": f"msg-{task_id}",
                "thread_id": f"thread-{task_id}",
                "from_email": from_email,
                "subject": subject,
                "body": body,
            },
            "pre_filter": pre_filter or {"category": None, "confidence": 0.0, "reason": "e2e"},
        },
    }

    # InboundOrchestratorHarness expects the incoming envelope payload to contain a
    # nested `payload` (the original request payload).
    payload = {"payload": inbound_payload}

    env = create_task_envelope(
        source="inbound_e2e",
        task_id=task_id,
        payload=payload,
        destination="inbound_orchestrator",
        tenant_id=tenant_id,
    )

    msg_id = client.xadd(stream, to_redis_fields(env))
    return msg_id.decode("utf-8", errors="ignore") if isinstance(msg_id, bytes) else str(msg_id)


def main() -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    tenant_id = os.environ.get("TENANT_ID", "agentic-dev")

    inbound_tasks = f"{tenant_id}:orchestrators:inbound:tasks"
    inbound_results = f"{tenant_id}:orchestrators:inbound:results"

    print(f"[E2E] REDIS_URL={redis_url}")
    print(f"[E2E] TENANT_ID={tenant_id}")

    # Start consumer.
    python_exe = _python_executable()
    print("[E2E] Starting inbound consumer...")
    proc = subprocess.Popen(
        [python_exe, "-m", "tiers.tier_2.inbound_orchestrator.consumer"],
        cwd=REPO_ROOT,
        env={**os.environ, "REDIS_URL": redis_url, "TENANT_ID": tenant_id},
    )

    try:
        # Give it a moment to create group + start loop.
        time.sleep(2.0)

        r = redis.Redis.from_url(redis_url, decode_responses=True)
        r.ping()
        print("[E2E] Connected to Redis")
        print(f"[E2E] Streams:\n  tasks={inbound_tasks}\n  results={inbound_results}")

        after_id = _get_last_id(r, inbound_results)

        t0 = int(time.time())
        task_ids = [
            f"inbound-personal-{t0}",
            f"inbound-marketing-{t0}",
            f"inbound-bounce-{t0}",
        ]

        sent = _send_inbound(
            r,
            tenant_id=tenant_id,
            stream=inbound_tasks,
            task_id=task_ids[0],
            from_email="prospect@company.com",
            subject="Re: Pricing question",
            body="Hi — can we schedule a quick call to discuss pricing and timeline?",
        )
        print(f"[E2E] Sent {task_ids[0]} -> {sent}")

        sent = _send_inbound(
            r,
            tenant_id=tenant_id,
            stream=inbound_tasks,
            task_id=task_ids[1],
            from_email="promo@vendor.com",
            subject="Limited-time offer: 50% off",
            body="Redeem now! Unsubscribe anytime.",
            pre_filter={"category": "marketing", "confidence": 0.9, "reason": "list_unsubscribe+x_mailer"},
        )
        print(f"[E2E] Sent {task_ids[1]} -> {sent}")

        sent = _send_inbound(
            r,
            tenant_id=tenant_id,
            stream=inbound_tasks,
            task_id=task_ids[2],
            from_email="mailer-daemon@example.com",
            subject="Delivery Status Notification (Failure)",
            body="Your message could not be delivered.",
            pre_filter={"category": "bounce", "confidence": 0.95, "reason": "mailer-daemon"},
        )
        print(f"[E2E] Sent {task_ids[2]} -> {sent}")

        print("[E2E] Waiting for results...")

        for tid in task_ids:
            msg_id, env = _wait_for_result(r, inbound_results, tid, after_id=after_id, timeout_s=20)
            payload = env.payload or {}
            routing = payload.get("routing") or {}
            classification = payload.get("classification") or {}

            print("\n" + "-" * 70)
            print(f"Result for {tid} (msg_id={msg_id})")
            print(f"  classification.category: {classification.get('category')}")
            print(f"  classification.action:   {classification.get('action')}")
            print(f"  routing.action:          {routing.get('action')}")
            print(f"  routing.category:        {routing.get('category')}")

            if routing.get("action") == "delegate":
                delegate = routing.get("delegate") or {}
                ctx = delegate.get("context") or {}
                print(f"  delegate.orchestrator:   {delegate.get('orchestrator')}")
                print(f"  actions_allowed:         {ctx.get('actions_allowed')}")

            if routing.get("action") == "dropped":
                print(f"  drop.reason:             {routing.get('reason')}")

        print("\n[OK] Inbound E2E completed")
        return 0

    finally:
        print("\n[E2E] Stopping inbound consumer...")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
