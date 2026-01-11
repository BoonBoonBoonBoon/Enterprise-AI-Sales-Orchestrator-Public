"""
Inbound Orchestrator Redis Stream Consumer

Consumes inbound communication tasks from Redis streams and processes them
via the InboundOrchestratorHarness.
"""

import asyncio
import logging
from typing import Optional

from services.redis import RedisStreamsClient
from core.envelope import Envelope

from .inbound_orchestrator_harness import InboundOrchestratorHarness

logger = logging.getLogger(__name__)


class InboundConsumer:
    """
    Redis stream consumer for inbound orchestration tasks.
    
    Listens to: {tenant}:orchestrators:inbound:tasks
    Publishes to: {tenant}:orchestrators:inbound:results
    """

    def __init__(self, tenant: str = "default", redis_url: Optional[str] = None):
        """
        Initialize the inbound consumer.
        
        Args:
            tenant: Tenant identifier for stream namespacing
            redis_url: Full Redis URL (required in production)
        """
        self.tenant = tenant
        self.stream_name = f"{tenant}:orchestrators:inbound:tasks"
        self.result_stream = f"{tenant}:orchestrators:inbound:results"
        self.consumer_group = "inbound_orchestrator_group"
        self.consumer_name = "inbound_orchestrator_consumer"
        
        self.redis_client = RedisStreamsClient(url=redis_url)
        self.harness = InboundOrchestratorHarness()
        
        logger.info(f"InboundConsumer initialized for tenant: {tenant}")

    async def start(self):
        """
        Start consuming inbound tasks from Redis stream.
        """
        logger.info(f"Starting inbound consumer on stream: {self.stream_name}")
        
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
        Process a single inbound message.
        
        Args:
            message_id: Redis message ID
            data: Message data
        """
        try:
            # Deserialize envelope
            envelope = Envelope.from_dict(data)
            
            # Process via harness
            result_envelope = await self.harness.execute(envelope)
            
            # Publish result
            await self.redis_client.publish_to_stream(
                self.result_stream,
                result_envelope.to_dict()
            )
            
            # Acknowledge message
            await self.redis_client.ack_message(
                self.stream_name,
                self.consumer_group,
                message_id
            )
            
            logger.info(f"Processed inbound task: {envelope.task_id}")

        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}", exc_info=True)


def main():
    """
    Entry point for running the inbound consumer.
    """
    import os
    tenant = os.getenv("TENANT_ID", "default")
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for inbound_orchestrator)")

    consumer = InboundConsumer(tenant=tenant, redis_url=redis_url)
    
    asyncio.run(consumer.start())


if __name__ == "__main__":
    main()
