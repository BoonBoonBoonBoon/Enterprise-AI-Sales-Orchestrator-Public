import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.envelope import Envelope, task as create_task_envelope, to_redis_fields
from tiers.tier_3.channel_sequencer_agent.consumer import ChannelSequencerAgentConsumer
from tiers.tier_3.channel_sequencer_agent.channel_sequencer_agent import ChannelSequencerAgent
import tiers.tier_3.channel_sequencer_agent.channel_sequencer_agent as sequencer_module


@pytest.mark.asyncio
async def test_outbound_email_persists_via_persistence_agent(monkeypatch):
    # Stub SMTP send to avoid network and return deterministic message-id
    monkeypatch.setattr(sequencer_module, "send_email_via_gmail", lambda **_: "<msg-123>")

    redis_mock = AsyncMock()
    redis_mock.xadd = AsyncMock()
    redis_mock.xack = AsyncMock()

    payload = {
        "tenant_id": "agentic-dev",
        "lead_id": "lead-123",
        "steps": [
            {
                "channel": "email",
                "to_email": "lead@example.com",
                "subject": "Hello",
                "body": "Hi there",
                "from_email": "sales@example.com",
                "metadata": {
                    "conversation_id": "conv-123",
                    "thread_id": "thr-1",
                },
            }
        ],
        "context": {"campaign_id": "camp-1"},
    }

    envelope = create_task_envelope(
        source="manager",
        task_id="seq-task-1",
        payload=payload,
        destination="sequencing",
        tenant_id="agentic-dev",
        correlation_id="corr-123",
    )
    message_data = to_redis_fields(envelope)

    consumer = ChannelSequencerAgentConsumer(redis_client=redis_mock, tenant_id="agentic-dev")

    await consumer.process_task("1-0", message_data)

    streams = [call.args[0] for call in redis_mock.xadd.call_args_list]
    persistence_stream = "agentic-dev:agents:persistence:tasks"
    assert persistence_stream in streams

    persistence_call = next(call for call in redis_mock.xadd.call_args_list if call.args[0] == persistence_stream)
    persistence_env = Envelope.model_validate_json(persistence_call.args[1]["data"])

    assert persistence_env.payload["operation"] == "compound"
    steps = persistence_env.payload["steps"]
    assert steps[0]["table"] == "conversations"
    assert steps[1]["table"] == "messages"
    assert steps[1]["data"]["direction"] == "outbound"
    assert steps[1]["data"]["metadata"]["correlation_id"] == "corr-123"


def test_channel_sequencer_blocks_hard_stop(monkeypatch):
    def fail_send(**_):
        raise AssertionError("send_email_via_gmail should not be called on hard stop")

    monkeypatch.setattr(sequencer_module, "send_email_via_gmail", fail_send)

    payload = {
        "tenant_id": "agentic-dev",
        "steps": [
            {
                "channel": "email",
                "to_email": "lead@example.com",
                "subject": "Hello",
                "body": "Hi",
                "metadata": {"unsubscribe": True},
            }
        ],
        "context": {},
    }

    agent = ChannelSequencerAgent()
    result = agent.build_sequence(payload)

    assert result["deliveries"][0]["status"] == "blocked"
    assert result["deliveries"][0]["reason"].startswith("hard_stop:")


def test_channel_sequencer_throttles_new_thread(monkeypatch):
    monkeypatch.setenv("OUTBOUND_MAX_NEW_THREADS_PER_DAY", "1")
    monkeypatch.setenv("OUTBOUND_MAX_PER_HOUR", "0")
    monkeypatch.setenv("REDIS_URL", "redis://test")

    redis_mock = MagicMock()
    redis_mock.incr.return_value = 2
    redis_mock.expire.return_value = True

    monkeypatch.setattr(sequencer_module.redis, "from_url", lambda *_args, **_kwargs: redis_mock)

    payload = {
        "tenant_id": "agentic-dev",
        "steps": [
            {
                "channel": "email",
                "to_email": "lead@example.com",
                "subject": "Hello",
                "body": "Hi",
                "metadata": {},
            }
        ],
        "context": {},
    }

    agent = ChannelSequencerAgent()
    result = agent.build_sequence(payload)

    assert result["deliveries"][0]["status"] == "throttled"
    assert result["deliveries"][0]["reason"] == "throttle:new_thread_limit"
