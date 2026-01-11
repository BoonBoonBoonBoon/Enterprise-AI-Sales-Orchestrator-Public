import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from core.envelope import task as create_task_envelope, to_redis_fields
from core.schemas.manager import ManagerDecision
from tiers.tier_1.manager.manager_agent import ManagerAgent
from tiers.tier_2.leads_orchestrator import leads_orchestrator


class DummyAgent:
    def invoke(self, messages):
        return {"messages": []}


class DummyRedis:
    def __init__(self):
        self.xadd_calls = []
        self._xrevrange_entries = []
        self.last_xrevrange_stream = None

    def set_xrevrange_entries(self, entries):
        self._xrevrange_entries = list(entries)

    def xrevrange(self, stream, max="+", min="-", count=50):  # noqa: A002 - follow redis signature
        self.last_xrevrange_stream = stream
        return list(self._xrevrange_entries)

    def xadd(self, stream, fields):
        self.xadd_calls.append((stream, fields))
        return "999-0"

    def ping(self):
        return True


@pytest.fixture
def patch_deep_agent(monkeypatch):
    # Avoid hitting real LLMs when constructing orchestrators
    monkeypatch.setattr(leads_orchestrator, "create_deep_agent", lambda **kwargs: DummyAgent())
    # Avoid starting metrics server in ManagerAgent init
    monkeypatch.setattr(
        "tiers.tier_1.manager.manager_agent.start_metrics_server",
        lambda: None,
        raising=False,
    )


def test_leads_builds_reply_packet(patch_deep_agent):
    dummy_redis = DummyRedis()
    orch = leads_orchestrator.LeadsOrchestrator(redis_client=dummy_redis, tenant_id="tenant")

    rag_payload = {
        "status": "success",
        "lead": {"id": "L1", "company": "Acme", "title": "CTO"},
        "conversations": [{"id": "C1", "summary": "Initial chat"}],
        "messages": [
            {"id": "m1", "created_at": "2024-01-01T00:00:00Z", "body": "Hello"},
            {"id": "m2", "created_at": "2024-01-02T00:00:00Z", "body": "Follow up"},
        ],
    }
    email_event = {"from": "lead@example.com", "subject": "Re: Pricing", "intent": "inquiry"}

    packet = orch._build_reply_packet_from_rag(
        rag_payload=rag_payload,
        email_event=email_event,
        goal="reply",
    )

    assert packet["lead_resolution"]["status"] == "found"
    assert packet["lead_resolution"]["lead_id"] == "L1"
    assert packet["conversation"]["recent_messages"]
    assert packet["facts"]["company"] == "Acme"
    assert packet["next"]["delegate_to"] == ["outbound"]
    assert packet["inbound_email_event"]["subject"] == "Re: Pricing"


def test_manager_chains_reply_packet_to_outbound(patch_deep_agent):
    dummy_redis = DummyRedis()

    # Build a fake leads result envelope containing the reply packet
    reply_packet = {"lead_resolution": {"status": "found", "lead_id": "L1"}}
    env = create_task_envelope(
        source="leads_orchestrator",
        task_id="task_leads",
        payload={"reply_packet": reply_packet},
        destination="manager",
        tenant_id="tenant",
        intent="reply_email",
    )
    dummy_redis.set_xrevrange_entries([("1-0", to_redis_fields(env))])

    mgr = ManagerAgent(redis_client=dummy_redis, tenant_id="tenant")

    enqueued = [
        {
            "stream": "tenant:orchestrators:leads:tasks",
            "id": "0-1",
            "task_id": "task_leads",
        }
    ]
    decision = ManagerDecision(
        intent="reply_email",
        confidence=0.9,
        reasons=[],
        used_fallback=False,
        context_depth="deep",
        orchestrators=["leads", "outbound"],
        tasks=[],
    )

    mgr._chain_leads_to_outbound(enqueued, decision, datetime.utcnow())

    assert any(
        ":orchestrators:outbound:tasks" in call[0] for call in dummy_redis.xadd_calls
    ), "Manager should enqueue outbound task when reply_packet is present"
    assert len(enqueued) == 2
    assert enqueued[-1].get("chained_from") == ["task_leads"]
    assert enqueued[-1]["stream"] == "tenant:orchestrators:outbound:tasks"
