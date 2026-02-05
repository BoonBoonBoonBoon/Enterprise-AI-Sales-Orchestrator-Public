"""SchedulerAgent Redis Streams consumer."""
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
from core.dlq import DeadLetterMessage, DLQ_SUFFIX, DLQ_MAX_RETRIES, DLQ_ENABLED
from core.observability import start_metrics_server, start_redis_stream_metrics
from tiers.tier_3.scheduler_agent.scheduler_agent import SchedulerAgent
from tiers.tier_3.scheduler_agent.scheduler_agent_harness import SchedulerAgentHarness
from config.settings import validate_keys

logger = logging.getLogger(__name__)


class SchedulerAgentConsumer:
    """Consume schedule tasks and emit results."""

    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str,
        consumer_group: str = "booking-workers",
        consumer_name: Optional[str] = None,
    ) -> None:
        self.redis_client = redis_client
        self.tenant_id = tenant_id
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"worker_{id(self)}"

        # Use existing booking stream namespace in Redis
        self.task_stream = f"{tenant_id}:agents:booking:tasks"
        self.result_stream = f"{tenant_id}:agents:booking:results"
        self.dlq_stream = f"{self.task_stream}{DLQ_SUFFIX}"
        self.max_retries = DLQ_MAX_RETRIES

        self.harness = SchedulerAgentHarness(agent=SchedulerAgent())

    async def ensure_consumer_group(self) -> None:
        try:
            await self.redis_client.xgroup_create(
                name=self.task_stream,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
            logger.info(
                "Created scheduler consumer group",
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
                error_msg=result.get("error", "Unknown scheduler error"),
                source="agents:booking",
                code="SCHEDULER_ERROR",
            )
        else:
            result_envelope = create_result_envelope(
                original=envelope, payload=result, source="agents:booking"
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

    async def run(self, block_ms: int = 5000, count: int = 10) -> None:
        await self.ensure_consumer_group()
        logger.info(
            "Scheduler consumer loop starting",
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
                            "Failed to process scheduler task",
                            extra={"message_id": message_id, "error": str(exc)},
                            exc_info=True,
                        )
                        await self._handle_failure(message_id, message_data, exc)


async def main() -> None:
    validate_keys(raise_on_missing=True)
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")

    # Start metrics server for this component
    start_metrics_server(component="scheduler_agent")

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for scheduler_agent)")
    redis_client = redis.from_url(redis_url)

    start_redis_stream_metrics(
        redis_url=redis_url,
        tenant_id=tenant_id,
        component="scheduler_agent",
        streams=[(f"{tenant_id}:agents:booking:tasks", "booking-workers")],
    )

    consumer = SchedulerAgentConsumer(redis_client=redis_client, tenant_id=tenant_id)
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
