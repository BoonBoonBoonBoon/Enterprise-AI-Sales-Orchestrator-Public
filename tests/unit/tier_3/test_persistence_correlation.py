import types
from unittest.mock import MagicMock

import pytest

from core.envelope import task as create_task_envelope, to_redis_fields
from tiers.tier_3.persistence_agent import persistence_agent as pa_module
from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent


class DummyResult:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        if hasattr(self._payload, "model_dump"):
            return self._payload.model_dump()
        return self._payload


def test_compound_injects_correlation_into_messages(monkeypatch):
    captured_payload = {}

    def fake_execute_compound(payload, adapter):
        nonlocal captured_payload
        captured_payload = payload.model_dump() if hasattr(payload, "model_dump") else payload
        return DummyResult(payload)

    monkeypatch.setattr(pa_module, "execute_compound", fake_execute_compound)

    agent = PersistenceAgent(redis_client=MagicMock(), tenant_id="agentic-dev", service=MagicMock())

    compound = {
        "operation": "compound",
        "correlation_id": "corr-abc",
        "steps": [
            {
                "step_name": "conversation",
                "table": "conversations",
                "operation": "upsert",
                "data": {"id": "conv-1", "lead_id": "lead-1"},
            },
            {
                "step_name": "message",
                "table": "messages",
                "operation": "upsert",
                "data": {"id": "msg-1", "conversation_id": "conv-1", "metadata": {}},
            },
        ],
    }

    result = agent._handle_compound(compound)

    assert result["steps"][1]["data"]["metadata"]["correlation_id"] == "corr-abc"
    assert captured_payload["steps"][1]["data"]["metadata"]["correlation_id"] == "corr-abc"


def test_compound_infers_campaign_id_from_mailbox_map(monkeypatch):
    captured_payload = {}

    def fake_execute_compound(payload, adapter):
        nonlocal captured_payload
        captured_payload = payload.model_dump() if hasattr(payload, "model_dump") else payload
        return DummyResult(payload)

    monkeypatch.setattr(pa_module, "execute_compound", fake_execute_compound)
    monkeypatch.setenv(
        "MAILBOX_CAMPAIGN_ID_MAP",
        '{"inbox@agency.com": "11111111-1111-1111-1111-111111111111"}',
    )

    agent = PersistenceAgent(redis_client=MagicMock(), tenant_id="agentic-dev", service=MagicMock())

    compound = {
        "operation": "compound",
        "steps": [
            {
                "step_name": "staging_lead",
                "table": "staging_leads",
                "operation": "upsert",
                "data": {"id": "stg-1", "email": "lead@example.com"},
            },
            {
                "step_name": "staging_message",
                "table": "staging_messages",
                "operation": "upsert",
                "data": {
                    "id": "stg-msg-1",
                    "conversation_id": "stg-conv-1",
                    "metadata": {"to": "Agency Inbox <inbox@agency.com>"},
                },
            },
        ],
    }

    result = agent._handle_compound(compound)

    assert result["steps"][0]["data"]["campaign_id"] == "11111111-1111-1111-1111-111111111111"
    assert captured_payload["steps"][0]["data"]["campaign_id"] == "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_consumer_propagates_correlation_into_payload(monkeypatch):
    import tiers.tier_3.persistence_agent.consumer as consumer_module

    from tiers.tier_3.persistence_agent.consumer import PersistenceAgentConsumer

    dummy_agent_harness = MagicMock()
    dummy_agent_harness.execute = MagicMock(return_value={"status": "success"})

    monkeypatch.setattr(
        consumer_module,
        "PersistenceAgentHarness",
        MagicMock(return_value=dummy_agent_harness),
    )

    fake_result_envelope = MagicMock()

    async def fake_xadd(stream, fields):
        fake_result_envelope.stream = stream
        fake_result_envelope.fields = fields

    redis_mock = MagicMock()
    redis_mock.xgroup_create = MagicMock()
    redis_mock.xadd = fake_xadd
    redis_mock.xack = MagicMock()

    consumer = PersistenceAgentConsumer(redis_client=redis_mock, tenant_id="agentic-dev")

    envelope = create_task_envelope(
        source="manager",
        task_id="task-1",
        payload={"operation": "compound", "steps": []},
        destination="persistence_agent",
        tenant_id="agentic-dev",
        correlation_id="corr-xyz",
    )

    message_data = to_redis_fields(envelope)

    await consumer.process_task("1-0", message_data)

    args, kwargs = dummy_agent_harness.execute.call_args
    task_payload = args[0]
    assert task_payload.get("correlation_id") == "corr-xyz"
