"""Classifier Agent Redis Streams Consumer.

Consumes tasks from `{tenant}:agents:classifier:tasks` and publishes results to
`{tenant}:agents:classifier:results`.

Run with:
    python -m tiers.tier_3.classifier_agent.consumer
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add project root to path
repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from dotenv import load_dotenv

    load_dotenv(repo_root / ".env")
except Exception:
    pass

from config.settings import validate_keys

from services.redis import RedisStreamsClient
from core.envelope import from_redis_message, to_redis_fields, result as create_result_envelope, error as create_error_envelope
from core.dlq import DeadLetterQueue
from core.observability import start_metrics_server
from .classifier_agent_harness import ClassifierAgentHarness

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ClassifierConsumer:
    """Consumer for classifier agent tasks."""

    def __init__(
        self,
        redis_client: RedisStreamsClient,
        tenant_id: str,
        consumer_group: str = "classifier-workers",
        consumer_name: Optional[str] = None,
    ):
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"classifier-worker-{os.getpid()}"

        self.task_stream = f"{tenant_id}:agents:classifier:tasks"
        self.result_stream = f"{tenant_id}:agents:classifier:results"
        self.dlq = DeadLetterQueue(redis_client, self.task_stream)

        self.harness = ClassifierAgentHarness()

        self._ensure_consumer_group()

        logger.info(
            "ClassifierConsumer initialized: tenant=%s group=%s name=%s",
            tenant_id,
            consumer_group,
            self.consumer_name,
        )

    def _get_delivery_count(self, message_id: str) -> int:
        try:
            client = getattr(self.redis, "client", self.redis)
            pending = client.xpending_range(
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

    def _handle_failure(self, message_id: str, message_data: Dict[str, Any], error: Exception, envelope=None) -> None:
        failure_count = self._get_delivery_count(message_id)
        if self.dlq.should_dlq(failure_count):
            self.dlq.send_to_dlq(
                message_data,
                message_id,
                error=error,
                failure_count=failure_count,
                consumer_name=self.consumer_name,
                tenant_id=self.tenant_id,
            )
            if envelope is not None:
                try:
                    error_envelope = create_error_envelope(
                        original=envelope,
                        error_msg=str(error),
                        source="agents:classifier",
                        code="CLASSIFIER_ERROR",
                    )
                    self.redis.xadd(self.result_stream, to_redis_fields(error_envelope))
                except Exception as publish_exc:  # pragma: no cover
                    logger.error("Failed to publish error envelope: %s", publish_exc, exc_info=True)
            self.redis.xack(self.task_stream, self.consumer_group, message_id)

    def _ensure_consumer_group(self) -> None:
        created = self.redis.xgroup_create(
            stream=self.task_stream,
            group=self.consumer_group,
            id="0",
            mkstream=True,
        )
        if created:
            logger.info("Created consumer group %s on %s", self.consumer_group, self.task_stream)

    async def process_message(self, message_id: str, message_data: Dict[str, Any]) -> None:
        envelope = from_redis_message(message_data)
        task_data = envelope.payload

        try:
            result = await self.harness.execute(task_data, context={
                "task_id": envelope.metadata.task_id,
                "correlation_id": envelope.metadata.correlation_id,
                "tenant_id": self.tenant_id,
                "source": envelope.metadata.source,
            })

            result_envelope = create_result_envelope(
                original=envelope,
                payload=result,
                source="agents:classifier",
            )

            self.redis.xadd(self.result_stream, to_redis_fields(result_envelope))
            self.redis.xack(self.task_stream, self.consumer_group, message_id)
        except Exception as e:
            logger.error("Classifier task failed: %s", e, exc_info=True)
            self._handle_failure(message_id, message_data, e, envelope=envelope)

    async def run(self, block_ms: int = 5000, count: int = 10) -> None:
        logger.info("Starting classifier consumer loop on %s", self.task_stream)
        while True:
            try:
                messages = self.redis.xreadgroup(
                    group=self.consumer_group,
                    consumer=self.consumer_name,
                    streams={self.task_stream: ">"},
                    count=count,
                    block=block_ms,
                )
                if not messages:
                    pending = self.redis.xreadgroup(
                        group=self.consumer_group,
                        consumer=self.consumer_name,
                        streams={self.task_stream: "0"},
                        count=count,
                        block=1,
                    )
                    if not pending:
                        continue
                    messages = pending

                for _stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        await self.process_message(message_id, message_data)
            except KeyboardInterrupt:
                logger.info("Classifier consumer interrupted; exiting")
                break
            except Exception as e:
                logger.error("Error in classifier consumer loop: %s", e, exc_info=True)
                await asyncio.sleep(1)


async def main() -> None:
    validate_keys(raise_on_missing=True)
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    
    # Start metrics server for this component
    start_metrics_server(component="classifier_agent")
    
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for classifier_agent)")

    redis_streams = RedisStreamsClient(url=redis_url)
    consumer = ClassifierConsumer(redis_client=redis_streams, tenant_id=tenant_id)
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
