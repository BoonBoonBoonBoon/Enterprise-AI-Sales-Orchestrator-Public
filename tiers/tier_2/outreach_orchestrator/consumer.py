"""
Outbound Orchestrator Consumer

Redis Stream consumer that processes tasks from {tenant}:orchestrators:outbound:tasks.
Results are published to {tenant}:orchestrators:outbound:results.
"""

import asyncio
import json
import logging
import os
import signal
from pathlib import Path
from typing import Dict, Any, Optional

from services.redis import RedisStreamsClient
from .outreach_orchestrator_harness import OutreachOrchestratorHarness
from core.envelope import (
    from_redis_message,
    to_redis_fields,
    result as create_result_envelope,
    error as create_error_envelope,
)
from core.dlq import DeadLetterQueue
from core.observability import start_metrics_server, start_redis_stream_metrics

# Load environment variables if present
try:
    from dotenv import load_dotenv

    repo_root = Path(__file__).resolve().parents[3]
    load_dotenv(repo_root / ".env")
except Exception:
    pass

from config.settings import validate_keys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _extract_copy_subject_body(copy_block: Dict[str, Any]) -> tuple[str, str]:
    """Best-effort extraction of subject/body from Copywriter output.

    Copywriter sometimes returns a JSON blob in the body (wrapped in ```json fences).
    For auto-send we want the plain email body.
    """
    subject = str(copy_block.get("subject") or "").strip()
    body = str(copy_block.get("body") or "").strip()

    if body.startswith("```") and "{" in body and "}" in body:
        # Strip code fences like ```json ... ```
        stripped = body
        if stripped.startswith("```json"):
            stripped = stripped[len("```json") :]
        elif stripped.startswith("```"):
            stripped = stripped[len("```") :]
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
        stripped = stripped.strip()

        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                parsed_subject = parsed.get("subject")
                parsed_body = parsed.get("body")
                if isinstance(parsed_subject, str) and parsed_subject.strip():
                    subject = parsed_subject.strip()
                if isinstance(parsed_body, str) and parsed_body.strip():
                    body = parsed_body.strip()
        except Exception:
            # Fall back to raw body if it isn't valid JSON.
            pass

    return subject, body


class OutreachConsumer:
    """
    Consumer for Outbound Orchestrator tasks.

    Listens to {tenant}:orchestrators:outbound:tasks and delegates to OutreachOrchestratorHarness.
    """

    def __init__(
        self,
        redis_client: RedisStreamsClient,
        tenant_id: str = "default",
        consumer_group: str = "outbound-workers",
        consumer_name: Optional[str] = None,
        environment: str = "development",
    ):
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"outbound-worker-{os.getpid()}"
        self.environment = environment
        self.shutdown_requested = False

        self.task_stream = f"{tenant_id}:orchestrators:outbound:tasks"
        self.result_stream = f"{tenant_id}:orchestrators:outbound:results"
        self.copywriter_result_stream = f"{tenant_id}:agents:copywriter:results"
        self.dlq = DeadLetterQueue(redis_client, self.task_stream)

        self.harness = OutreachOrchestratorHarness(
            redis_client=redis_client,
            tenant_id=tenant_id,
            environment=environment,
            enable_observability=(environment == "production"),
            enable_checkpointing=(environment != "development"),
        )

        self._ensure_consumer_group()
        self._ensure_copywriter_group()

        logger.info(
            f"OutreachConsumer initialized: tenant={tenant_id}, "
            f"group={consumer_group}, name={self.consumer_name}"
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
                        error=str(error),
                        source="outbound_orchestrator",
                    )
                    self.redis.xadd(self.result_stream, to_redis_fields(error_envelope))
                except Exception as publish_exc:  # pragma: no cover - best effort
                    logger.error(f"Failed to publish error envelope: {publish_exc}", exc_info=True)
            self.redis.xack(self.task_stream, self.consumer_group, message_id)

    def _ensure_consumer_group(self):
        try:
            created = self.redis.xgroup_create(
                stream=self.task_stream,
                group=self.consumer_group,
                id="0",
                mkstream=True,
            )
            if created:
                logger.info(f"Created consumer group {self.consumer_group} on {self.task_stream}")
            else:
                logger.info(f"Consumer group {self.consumer_group} already exists")
        except Exception as exc:
            logger.error(f"Error creating consumer group: {exc}")
            raise

    def _ensure_copywriter_group(self):
        try:
            created = self.redis.xgroup_create(
                stream=self.copywriter_result_stream,
                group=self.consumer_group,
                id="0",
                mkstream=True,
            )
            if created:
                logger.info(
                    f"Created copywriter result consumer group {self.consumer_group} on {self.copywriter_result_stream}"
                )
            else:
                logger.info(
                    f"Copywriter result consumer group {self.consumer_group} already exists"
                )
        except Exception as exc:
            logger.error(f"Error creating copywriter consumer group: {exc}")
            raise

    async def process_task(self, message_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            envelope = from_redis_message(message_data)
            task_data = envelope.payload
            task_id = envelope.metadata.task_id

            logger.info(f"[OUTBOUND] Processing task {task_id} from message {message_id}")
            logger.info(f"[OUTBOUND] Task data: {task_data}")

            result = await self.harness.execute(task_data)

            result_envelope = create_result_envelope(
                original=envelope,
                payload=result,
                source="outbound_orchestrator",
            )

            self.redis.xadd(self.result_stream, to_redis_fields(result_envelope))
            self.redis.xack(self.task_stream, self.consumer_group, message_id)

            logger.info(f"Task {task_id} completed successfully")
            return result

        except Exception as exc:
            logger.error(f"Error processing task: {exc}", exc_info=True)

            self._handle_failure(message_id, message_data, exc, envelope=locals().get("envelope"))

            raise

    async def process_copywriter_result(self, message_id: str, message_data: Dict[str, Any]) -> None:
        """Handle copywriter completion and auto-send via sequencer when configured."""
        try:
            # Guard: older stream entries may not be typed envelopes.
            if not ("data" in message_data or b"data" in message_data):
                logger.warning(
                    "Skipping non-envelope copywriter result message (missing data field)",
                    extra={"stream": self.copywriter_result_stream, "message_id": message_id},
                )
                self.redis.xack(self.copywriter_result_stream, self.consumer_group, message_id)
                return

            envelope = from_redis_message(message_data)
            task_id = envelope.metadata.task_id
            payload = envelope.payload or {}

            raw_ctx = self.redis.client.hget(self.harness.orchestrator._auto_send_hash, task_id)
            if not raw_ctx:
                # No auto-send registered; just ack and ignore.
                self.redis.xack(self.copywriter_result_stream, self.consumer_group, message_id)
                return

            try:
                auto_ctx = json.loads(raw_ctx)
            except Exception:
                logger.exception("Failed to decode auto-send context; dropping entry")
                self.redis.client.hdel(self.harness.orchestrator._auto_send_hash, task_id)
                self.redis.xack(self.copywriter_result_stream, self.consumer_group, message_id)
                return

            copy_block = payload.get("copy") or {}
            subject, body = _extract_copy_subject_body(copy_block)
            if not subject:
                subject = auto_ctx.get("subject_fallback") or "Re:"

            if not body:
                # Emit error result
                error_envelope = create_error_envelope(
                    original=envelope,
                    error="copywriter returned empty body; cannot auto-send",
                    source="outbound_orchestrator",
                )
                self.redis.xadd(self.result_stream, to_redis_fields(error_envelope))
                self.redis.client.hdel(self.harness.orchestrator._auto_send_hash, task_id)
                self.redis.xack(self.copywriter_result_stream, self.consumer_group, message_id)
                return

            seq_request = {
                "lead_id": auto_ctx.get("lead_id"),
                "campaign_id": auto_ctx.get("campaign_id"),
                "steps": [
                    {
                        "channel": "email",
                        "to_email": auto_ctx.get("to_email"),
                        "subject": subject,
                        "body": body,
                        "delay_minutes": 0,
                        "metadata": {
                            "copywriter_task_id": task_id,
                            "copy_model": (copy_block.get("metadata") or {}).get("model"),
                            "auto_send": True,
                        },
                    }
                ],
                "context": {
                    "reply_packet": auto_ctx.get("reply_packet"),
                },
            }

            from_email = (auto_ctx.get("from_email") or "").strip()
            if from_email:
                seq_request["steps"][0]["from_email"] = from_email

            seq_result = self.harness.orchestrator._enqueue_sequencing(seq_request)

            result_payload = {
                "status": "sent_enqueued",
                "copywriter_task_id": task_id,
                "sequencer": seq_result,
            }
            result_envelope = create_result_envelope(
                original=envelope,
                payload=result_payload,
                source="outbound_orchestrator",
            )
            self.redis.xadd(self.result_stream, to_redis_fields(result_envelope))

            # Cleanup and ack
            self.redis.client.hdel(self.harness.orchestrator._auto_send_hash, task_id)
            self.redis.xack(self.copywriter_result_stream, self.consumer_group, message_id)
            logger.info(f"Auto-sent via sequencer for copy task {task_id}")
        except Exception as exc:
            logger.error(f"Error handling copywriter result: {exc}", exc_info=True)
            try:
                self.redis.xack(self.copywriter_result_stream, self.consumer_group, message_id)
            except Exception:
                logger.exception("Failed to ack copywriter result after error")

    async def run(self, block_ms: int = 5000, count: int = 10):
        logger.info(f"Starting consumer loop on {self.task_stream}")

        while not self.shutdown_requested:
            try:
                messages = self.redis.xreadgroup(
                    group=self.consumer_group,
                    consumer=self.consumer_name,
                    streams={
                        self.task_stream: ">",
                        self.copywriter_result_stream: ">",
                    },
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

                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        if self.shutdown_requested:
                            return
                        try:
                            if stream_name == self.task_stream:
                                await self.process_task(message_id, message_data)
                            elif stream_name == self.copywriter_result_stream:
                                await self.process_copywriter_result(message_id, message_data)
                        except Exception as exc:
                            logger.error(f"Failed to process message {message_id}: {exc}")

            except KeyboardInterrupt:
                logger.info("Consumer interrupted by user")
                self.shutdown_requested = True
                break
            except Exception as exc:
                if not self.shutdown_requested:
                    logger.error(f"Error in consumer loop: {exc}", exc_info=True)
                    await asyncio.sleep(1)


async def main():
    validate_keys(raise_on_missing=True)
    tenant_id = os.getenv("TENANT_ID", "default")
    environment = os.getenv("ENVIRONMENT", "development")

    # Start metrics server for this component
    start_metrics_server(component="outreach_orchestrator")

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for outreach_orchestrator)")

    redis_streams = RedisStreamsClient(url=redis_url)

    start_redis_stream_metrics(
        redis_url=redis_url,
        tenant_id=tenant_id,
        component="outreach_orchestrator",
        streams=[(f"{tenant_id}:orchestrators:outbound:tasks", "outbound-workers")],
    )

    consumer = OutreachConsumer(
        redis_client=redis_streams,
        tenant_id=tenant_id,
        environment=environment,
    )

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        consumer.shutdown_requested = True

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await consumer.run()
    finally:
        logger.info("Outbound orchestrator consumer shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
