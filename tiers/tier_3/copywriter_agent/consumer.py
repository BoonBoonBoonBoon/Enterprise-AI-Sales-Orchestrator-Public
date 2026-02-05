"""
Copywriter Agent Redis Streams Consumer

Handles:
- Consuming tasks from hierarchical Redis stream: {tenant}:agents:copywriter:tasks
- Publishing results to: {tenant}:agents:copywriter:results
- Typed envelope parsing and serialization
- Agent execution through harness
"""

import asyncio
import logging
import redis.asyncio as redis
from typing import Optional, Dict, Any
from datetime import datetime

from .copywriter import CopywriterAgent
from .copywriter_agent_harness import CopywriterAgentHarness
from core.envelope import Envelope, from_redis_message, task as create_task_envelope, result as create_result_envelope, error as create_error_envelope, to_redis_fields
from core.dlq import DeadLetterMessage, DLQ_SUFFIX, DLQ_MAX_RETRIES, DLQ_ENABLED
from core.observability import start_metrics_server, start_redis_stream_metrics
from config.settings import validate_keys

logger = logging.getLogger(__name__)


class CopywriterAgentConsumer:
    """
    Redis Streams consumer for Copywriter Agent.
    
    Implements hierarchical stream naming:
    - Task stream: {tenant}:agents:copywriter:tasks
    - Result stream: {tenant}:agents:copywriter:results
    
    Uses global typed envelope for all messages.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str,
        consumer_group: str = "copywriter-workers",
        consumer_name: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Copywriter Agent Consumer.
        
        Args:
            redis_client: Redis client instance
            tenant_id: Tenant identifier
            consumer_group: Consumer group name (default: 'copywriter_workers')
            consumer_name: Consumer name (default: generated)
            llm_config: Optional LLM configuration
        """
        self.redis_client = redis_client
        self.tenant_id = tenant_id
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"worker_{id(self)}"
        
        # Hierarchical stream naming
        self.task_stream = f"{tenant_id}:agents:copywriter:tasks"
        self.result_stream = f"{tenant_id}:agents:copywriter:results"
        self.dlq_stream = f"{self.task_stream}{DLQ_SUFFIX}"
        self.max_retries = DLQ_MAX_RETRIES
        
        # Initialize agent and harness
        agent = CopywriterAgent(llm_config=llm_config)
        self.harness = CopywriterAgentHarness(agent=agent)
        
        logger.info(
            f"Copywriter consumer initialized for tenant '{tenant_id}'",
            extra={
                "tenant_id": tenant_id,
                "task_stream": self.task_stream,
                "result_stream": self.result_stream,
                "consumer_group": self.consumer_group,
                "consumer_name": self.consumer_name
            }
        )

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

    async def _handle_failure(self, message_id: str, message_data: Dict[str, bytes], error: Exception, envelope=None) -> None:
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

        if envelope is not None:
            try:
                error_envelope = create_error_envelope(
                    original=envelope,
                    error_msg=str(error),
                    source="agents:copywriter",
                    code="COPYWRITER_ERROR",
                )
                await self.redis_client.xadd(self.result_stream, to_redis_fields(error_envelope))
            except Exception:
                pass

        await self.redis_client.xack(self.task_stream, self.consumer_group, message_id)
    
    async def ensure_consumer_group(self):
        """Create consumer group if it doesn't exist."""
        desired = self.consumer_group
        legacy_groups = ["copywriter_workers"]

        try:
            existing = []
            try:
                existing = await self.redis_client.xinfo_groups(self.task_stream)
            except Exception:
                existing = []

            existing_names = set()
            legacy_last_delivered: Optional[str] = None
            for g in existing or []:
                name = None
                try:
                    name = g.get("name")
                except Exception:
                    name = None
                if isinstance(name, (bytes, bytearray)):
                    name = name.decode("utf-8", errors="ignore")
                if isinstance(name, str):
                    existing_names.add(name)
                    if name in legacy_groups and legacy_last_delivered is None:
                        last_id = g.get("last-delivered-id")
                        if isinstance(last_id, (bytes, bytearray)):
                            last_id = last_id.decode("utf-8", errors="ignore")
                        if isinstance(last_id, str) and last_id:
                            legacy_last_delivered = last_id

            if desired in existing_names:
                logger.debug(
                    "Consumer group already exists",
                    extra={"group": desired, "stream": self.task_stream},
                )
                return

            start_id = legacy_last_delivered or "0"

            await self.redis_client.xgroup_create(
                name=self.task_stream,
                groupname=desired,
                id=start_id,
                mkstream=True,
            )
            logger.info(
                "Created consumer group",
                extra={"group": desired, "stream": self.task_stream, "start_id": start_id},
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"Error creating consumer group: {e}")
                raise
            logger.debug(f"Consumer group '{desired}' already exists")
    
    async def process_task(self, message_id: str, message_data: Dict[str, bytes]):
        """
        Process a single task message.
        
        Args:
            message_id: Redis message ID
            message_data: Raw message data from Redis
        """
        try:
            # Parse typed envelope
            envelope = from_redis_message(message_data)
            
            logger.info(
                f"Processing copywriting task: {envelope.metadata.task_id}",
                extra={
                    "message_id": message_id,
                    "task_id": envelope.metadata.task_id,
                    "correlation_id": envelope.metadata.correlation_id,
                    "source": envelope.metadata.source
                }
            )
            
            # Extract task data from payload
            task_data = envelope.payload
            
            # Build execution context
            context = {
                "request_id": envelope.metadata.task_id,
                "correlation_id": envelope.metadata.correlation_id,
                "tenant_id": self.tenant_id,
                "source": envelope.metadata.source
            }
            
            # Execute through harness
            result = await self.harness.execute(task_data, context)
            
            # Create result envelope
            if result.get("status") == "error":
                result_envelope = create_error_envelope(
                    original=envelope,
                    error_msg=result.get("error", "Unknown error"),
                    source="agents:copywriter",
                    code="COPYWRITER_ERROR"
                )
            else:
                result_envelope = create_result_envelope(
                    original=envelope,
                    payload=result,
                    source="agents:copywriter"
                )

            # Debug/demo: print the generated email (if present) to stdout so we can see drafts live.
            try:
                payload = result_envelope.payload or {}
                email_body = None
                email_subject = None
                # Common fields used by copywriter worker
                if isinstance(payload, dict):
                    email_body = payload.get("email_body") or payload.get("body") or payload.get("text")
                    email_subject = payload.get("subject")
                print("\n=== COPYWRITER DRAFT ===")
                if email_subject:
                    print(f"Subject: {email_subject}")
                if email_body:
                    print(email_body)
                else:
                    print(payload)
                print("========================\n")
            except Exception:
                # Non-fatal debug helper
                pass
            
            # Publish result
            await self.redis_client.xadd(
                self.result_stream,
                to_redis_fields(result_envelope)
            )
            
            logger.info(
                f"Published copywriting result: {envelope.metadata.task_id}",
                extra={
                    "task_id": envelope.metadata.task_id,
                    "result_stream": self.result_stream,
                    "status": result.get("status")
                }
            )
            
            # Acknowledge message
            await self.redis_client.xack(
                self.task_stream,
                self.consumer_group,
                message_id
            )
            
        except Exception as e:
            logger.error(
                f"Error processing copywriting task: {e}",
                extra={"message_id": message_id},
                exc_info=True
            )
            await self._handle_failure(message_id, message_data, e, envelope=locals().get("envelope"))
    
    async def run(self, block_ms: int = 5000):
        """
        Run consumer loop.
        
        Args:
            block_ms: Block time in milliseconds (default: 5000)
        """
        # Ensure consumer group exists
        await self.ensure_consumer_group()
        
        logger.info(
            f"Starting copywriter consumer loop",
            extra={
                "consumer_group": self.consumer_group,
                "consumer_name": self.consumer_name,
                "task_stream": self.task_stream
            }
        )
        
        while True:
            try:
                # Read from stream
                messages = await self.redis_client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.task_stream: ">"},
                    count=1,
                    block=block_ms
                )
                
                if not messages:
                    pending = await self.redis_client.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.consumer_name,
                        streams={self.task_stream: "0"},
                        count=1,
                        block=1,
                    )
                    if not pending:
                        continue
                    messages = pending
                
                # Process messages
                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        await self.process_task(message_id, message_data)
                        
            except asyncio.CancelledError:
                logger.info("Copywriter consumer shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in copywriter consumer loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on errors


async def main():
    """Main entry point for running Copywriter Agent consumer."""
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    validate_keys(raise_on_missing=True)
    
    # Configuration
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    
    # Start metrics server for this component
    start_metrics_server(component="copywriter_agent")
    
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for copywriter_agent)")

    redis_client = redis.from_url(redis_url, decode_responses=False)
    connection_desc = redis_url.split("@")[-1]

    start_redis_stream_metrics(
        redis_url=redis_url,
        tenant_id=tenant_id,
        component="copywriter_agent",
        streams=[(f"{tenant_id}:agents:copywriter:tasks", "copywriter-workers")],
    )
    
    try:
        # Test connection
        await redis_client.ping()
        logger.info(f"Connected to Redis at {connection_desc}")
        
        # Create and run consumer
        consumer = CopywriterAgentConsumer(
            redis_client=redis_client,
            tenant_id=tenant_id
        )
        
        await consumer.run()
        
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    asyncio.run(main())
