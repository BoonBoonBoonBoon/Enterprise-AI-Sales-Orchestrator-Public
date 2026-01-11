"""ChannelSequencerAgent Redis Streams consumer."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import redis.asyncio as redis

from core.envelope import (
    error as create_error_envelope,
    from_redis_message,
    result as create_result_envelope,
    to_redis_fields,
)
from tiers.tier_3.channel_sequencer_agent.channel_sequencer_agent import (
    ChannelSequencerAgent,
)
from tiers.tier_3.channel_sequencer_agent.channel_sequencer_agent_harness import (
    ChannelSequencerAgentHarness,
)

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
                continue

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


async def main() -> None:
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for channel_sequencer_agent)")
    redis_client = redis.from_url(redis_url)

    consumer = ChannelSequencerAgentConsumer(
        redis_client=redis_client,
        tenant_id=tenant_id,
    )
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
