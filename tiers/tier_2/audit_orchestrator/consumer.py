"""
Audit Orchestrator Redis Stream Consumer

Consumes audit tasks from Redis streams and processes them via the
AuditOrchestratorHarness.
"""

import asyncio
import logging
from typing import Optional

from services.redis import RedisStreamsClient
from core.envelope import from_redis_message, to_redis_fields
from core.dlq import DeadLetterQueue
from config.settings import validate_keys

from .audit_orchestrator_harness import AuditOrchestratorHarness

logger = logging.getLogger(__name__)


class AuditConsumer:
    """
    Redis stream consumer for audit orchestration tasks.
    
    Listens to: {tenant}:orchestrators:audit:tasks
    Publishes to: {tenant}:orchestrators:audit:results
    """

    def __init__(self, tenant: str = "default"):
        """
        Initialize the audit consumer.
        
        Args:
            tenant: Tenant identifier for stream namespacing
        """
        self.tenant = tenant
        self.stream_name = f"{tenant}:orchestrators:audit:tasks"
        self.result_stream = f"{tenant}:orchestrators:audit:results"
        self.consumer_group = "audit_orchestrator_group"
        self.consumer_name = "audit_orchestrator_consumer"
		
        self.redis_client = RedisStreamsClient()
        self.dlq = DeadLetterQueue(self.redis_client, self.stream_name)
        self.harness = AuditOrchestratorHarness()
        
        logger.info(f"AuditConsumer initialized for tenant: {tenant}")

    async def start(self):
        """
        Start consuming audit tasks from Redis stream.
        """
        logger.info(f"Starting audit consumer on stream: {self.stream_name}")
        
        # Create consumer group if it doesn't exist
        try:
            await self.redis_client.create_consumer_group(
                self.stream_name,
                self.consumer_group
            )
        except Exception as e:
            logger.debug(f"Consumer group may already exist: {e}")

        while True:
            try:
                # Read from stream
                messages = await self.redis_client.read_group(
                    self.stream_name,
                    self.consumer_group,
                    self.consumer_name,
                    count=1,
                    block=5000
                )

                for message_id, data in messages:
                    await self._process_message(message_id, data)

            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _process_message(self, message_id: str, data: dict):
        """
        Process a single audit task message.
        
        Args:
            message_id: Redis message ID
            data: Message data
        """
        try:
            # Deserialize envelope
            envelope = from_redis_message(data)
            
            # Process via harness
            result_envelope = await self.harness.execute(envelope)
            
            # Publish result
            await self.redis_client.publish_to_stream(
                self.result_stream,
                to_redis_fields(result_envelope),
            )
            
            # Acknowledge message
            await self.redis_client.ack_message(
                self.stream_name,
                self.consumer_group,
                message_id
            )
            
            logger.info(f"Processed audit task: {envelope.metadata.task_id}")

        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}", exc_info=True)
            failure_count = self._get_delivery_count(message_id)
            if self.dlq.should_dlq(failure_count):
                self.dlq.send_to_dlq(
                    data,
                    message_id,
                    error=e,
                    failure_count=failure_count,
                    consumer_name=self.consumer_name,
                    tenant_id=self.tenant,
                )
                try:
                    await self.redis_client.ack_message(
                        self.stream_name,
                        self.consumer_group,
                        message_id,
                    )
                except Exception:
                    pass

    def _get_delivery_count(self, message_id: str) -> int:
        try:
            client = getattr(self.redis_client, "client", self.redis_client)
            pending = client.xpending_range(
                self.stream_name,
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


def main():
    """
    Entry point for running the audit consumer.
    """
    import os
    validate_keys(raise_on_missing=True)
    tenant = os.getenv("TENANT_ID", "default")
    consumer = AuditConsumer(tenant=tenant)
    
    asyncio.run(consumer.start())


if __name__ == "__main__":
    main()
