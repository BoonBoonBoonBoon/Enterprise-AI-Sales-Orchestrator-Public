"""ChannelSequencerAgent Redis Streams consumer."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import redis.asyncio as redis

from core.envelope import (
    error as create_error_envelope,
    from_redis_message,
    result as create_result_envelope,
    task as create_task_envelope,
    to_redis_fields,
)
from core.dlq import DeadLetterMessage, DLQ_SUFFIX, DLQ_MAX_RETRIES, DLQ_ENABLED
from core.streams import assert_agents_stream
from core.observability import start_metrics_server, start_redis_stream_metrics
from tiers.tier_3.channel_sequencer_agent.channel_sequencer_agent import (
    ChannelSequencerAgent,
)
from tiers.tier_3.channel_sequencer_agent.channel_sequencer_agent_harness import (
    ChannelSequencerAgentHarness,
)
from tiers.tier_3.channel_sequencer_agent.validators import SequenceRequest
from config.settings import validate_keys

logger = logging.getLogger(__name__)


class ChannelSequencerAgentConsumer:
    """Consume channel sequencing tasks and emit results."""

    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str,
        consumer_group: str = "sequencing-workers",
        consumer_name: Optional[str] = None,
    ) -> None:
        self.redis_client = redis_client
        self.tenant_id = tenant_id
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"worker_{id(self)}"

        # Use existing sequencing stream namespace in Redis
        self.task_stream = f"{tenant_id}:agents:sequencing:tasks"
        self.result_stream = f"{tenant_id}:agents:sequencing:results"
        self.dlq_stream = f"{self.task_stream}{DLQ_SUFFIX}"
        self.max_retries = DLQ_MAX_RETRIES

        self.harness = ChannelSequencerAgentHarness(agent=ChannelSequencerAgent())

    async def ensure_consumer_group(self) -> None:
        try:
            await self.redis_client.xgroup_create(
                name=self.task_stream,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
            logger.info(
                "Created channel sequencer consumer group",
                extra={"group": self.consumer_group, "stream": self.task_stream},
            )
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def process_task(self, message_id: str, message_data: Dict[str, bytes]) -> None:
        envelope = from_redis_message(message_data)
        context = {
            "request_id": envelope.metadata.task_id,
            "correlation_id": envelope.metadata.correlation_id,
            "tenant_id": self.tenant_id,
            "source": envelope.metadata.source,
        }

        result = await self.harness.execute(envelope.payload, context)

        if result.get("status") != "error":
            await self._persist_email_deliveries(
                envelope=envelope,
                sequence_payload=envelope.payload,
                sequence_result=result,
            )

        if result.get("status") == "error":
            result_envelope = create_error_envelope(
                original=envelope,
                error_msg=result.get("error", "Unknown channel sequencing error"),
                source="agents:sequencing",
                code="CHANNEL_SEQ_ERROR",
            )
        else:
            result_envelope = create_result_envelope(
                original=envelope,
                payload=result,
                source="agents:sequencing",
            )

        await self.redis_client.xadd(
            self.result_stream,
            to_redis_fields(result_envelope),
        )
        await self.redis_client.xack(self.task_stream, self.consumer_group, message_id)

    async def _get_delivery_count(self, message_id: str) -> int:
        try:
            pending = await self.redis_client.xpending_range(
                self.task_stream,
                self.consumer_group,
                min=message_id,
                max=message_id,
                count=1,
            )
            if pending:
                entry = pending[0]
                if isinstance(entry, dict):
                    return int(entry.get("times_delivered", 1))
                if isinstance(entry, (list, tuple)) and len(entry) >= 4:
                    return int(entry[3])
        except Exception:
            pass
        return 1

    async def _handle_failure(self, message_id: str, message_data: Dict[str, bytes], error: Exception) -> None:
        if not DLQ_ENABLED:
            return
        failure_count = await self._get_delivery_count(message_id)
        if failure_count < self.max_retries:
            return

        dlq_message = DeadLetterMessage(
            original_message=message_data,
            original_stream=self.task_stream,
            original_message_id=message_id,
            failure_reason="max_retries_exceeded",
            failure_count=failure_count,
            last_error=str(error),
            error_type=type(error).__name__,
            consumer_name=self.consumer_name,
            tenant_id=self.tenant_id,
        )
        await self.redis_client.xadd(self.dlq_stream, dlq_message.to_dict())
        await self.redis_client.xack(self.task_stream, self.consumer_group, message_id)

    async def _persist_email_deliveries(
        self,
        *,
        envelope,
        sequence_payload: Dict[str, Any],
        sequence_result: Dict[str, Any],
    ) -> None:
        """Persist outbound email deliveries by enqueuing a compound write."""

        deliveries = sequence_result.get("deliveries") or []
        if not deliveries:
            return

        try:
            request = SequenceRequest(**sequence_payload)
        except Exception as exc:
            logger.warning(
                "Skipping outbound persistence; invalid sequence payload",
                extra={
                    "task_id": envelope.metadata.task_id,
                    "error": str(exc),
                },
            )
            return

        tenant_id = request.tenant_id or self.tenant_id
        steps = request.steps or []
        if not steps:
            return

        for step, delivery in zip(steps, deliveries):
            if str(step.channel).lower() != "email":
                continue
            if delivery.get("status") != "sent":
                continue

            await self._enqueue_persistence_message(
                tenant_id=tenant_id,
                envelope=envelope,
                step=step,
                delivery=delivery,
                request_context=request.context or {},
                lead_id=request.lead_id,
            )

    async def _enqueue_persistence_message(
        self,
        *,
        tenant_id: str,
        envelope,
        step,
        delivery: Dict[str, Any],
        request_context: Dict[str, Any],
        lead_id: Optional[str],
    ) -> None:
        """Enqueue a PersistenceAgent task for a sent outbound email."""

        metadata = dict(step.metadata or {})
        effective_lead_id = metadata.get("lead_id") or lead_id
        if not effective_lead_id:
            logger.warning(
                "Skipping outbound persistence; missing lead_id",
                extra={"task_id": envelope.metadata.task_id},
            )
            return

        subject = step.subject or metadata.get("subject")
        thread_id = metadata.get("thread_id") or request_context.get("thread_id")
        conversation_id = (
            metadata.get("conversation_id")
            or request_context.get("conversation_id")
            or str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{tenant_id}:{effective_lead_id}:{thread_id or subject or step.to_email or 'conversation'}",
                )
            )
        )

        message_pk = str(uuid.uuid4())
        sent_at = datetime.utcnow().isoformat()
        smtp_message_id = delivery.get("message_id")

        metadata.update(
            {
                "to": delivery.get("to"),
                "from": delivery.get("from"),
                "subject": subject,
                "thread_id": thread_id,
                "message_id": smtp_message_id,
                "correlation_id": envelope.metadata.correlation_id,
                "sequence_task_id": envelope.metadata.task_id,
            }
        )
        metadata = {k: v for k, v in metadata.items() if v is not None}

        compound_payload = {
            "operation": "compound",
            "transaction_id": f"seq_outbound_{envelope.metadata.task_id}",
            "steps": [
                {
                    "step_name": "conversation",
                    "table": "conversations",
                    "operation": "upsert",
                    "data": {
                        "id": conversation_id,
                        "lead_id": effective_lead_id,
                        "thread_id": thread_id,
                        "subject": subject,
                        "channel": "email",
                        "status": "active",
                        "summary": subject or "",
                    },
                    "match_on": ["id"],
                },
                {
                    "step_name": "message",
                    "table": "messages",
                    "operation": "upsert",
                    "data": {
                        "id": message_pk,
                        "conversation_id": "$ref:conversation.id",
                        "sender_type": "agent",
                        "direction": "outbound",
                        "text_content": step.body or "",
                        "sent_at": sent_at,
                        "message_id": smtp_message_id,
                        "metadata": metadata or {},
                    },
                    "match_on": ["id"],
                },
            ],
        }

        stream = f"{tenant_id}:agents:persistence:tasks"
        try:
            assert_agents_stream(stream)
            persistence_envelope = create_task_envelope(
                source="channel_sequencer_agent",
                task_id=f"persist_outbound_{uuid.uuid4()}",
                payload=compound_payload,
                destination="persistence_agent",
                tenant_id=tenant_id,
                correlation_id=envelope.metadata.correlation_id,
            )
            await self.redis_client.xadd(stream, to_redis_fields(persistence_envelope))
        except Exception as exc:  # pragma: no cover - log path
            logger.error(
                "Failed to enqueue outbound persistence task",
                extra={"stream": stream, "error": str(exc)},
                exc_info=True,
            )

    async def run(self, block_ms: int = 5000, count: int = 10) -> None:
        await self.ensure_consumer_group()
        logger.info(
            "Channel sequencer consumer loop starting",
            extra={"stream": self.task_stream, "group": self.consumer_group},
        )

        while True:
            messages = await self.redis_client.xreadgroup(
                groupname=self.consumer_group,
                consumername=self.consumer_name,
                streams={self.task_stream: ">"},
                count=count,
                block=block_ms,
            )

            if not messages:
                pending = await self.redis_client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.task_stream: "0"},
                    count=count,
                    block=1,
                )
                if not pending:
                    continue
                messages = pending

            for _stream, stream_messages in messages:
                for message_id, message_data in stream_messages:
                    try:
                        await self.process_task(message_id, message_data)
                    except Exception as exc:  # pragma: no cover - log path
                        logger.error(
                            "Failed to process channel sequencing task",
                            extra={"message_id": message_id, "error": str(exc)},
                            exc_info=True,
                        )
                        await self._handle_failure(message_id, message_data, exc)


async def main() -> None:
    validate_keys(raise_on_missing=True)
    # Start metrics server for this component
    start_metrics_server(component="channel_sequencer_agent")
    
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for channel_sequencer_agent)")
    redis_client = redis.from_url(redis_url)

    start_redis_stream_metrics(
        redis_url=redis_url,
        tenant_id=tenant_id,
        component="channel_sequencer_agent",
        streams=[(f"{tenant_id}:agents:sequencing:tasks", "sequencing-workers")],
    )

    consumer = ChannelSequencerAgentConsumer(
        redis_client=redis_client,
        tenant_id=tenant_id,
    )
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
