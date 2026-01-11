"""
Leads Orchestrator Consumer

Redis Stream consumer that processes tasks from {tenant}:orchestrators:leads:tasks.
Results are published to {tenant}:orchestrators:leads:results.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Add project root to path
repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(repo_root / ".env")
except Exception:
    pass

from services.redis import RedisStreamsClient
from .leads_orchestrator_harness import LeadsOrchestratorHarness
from core.envelope import from_redis_message, to_redis_fields, result as create_result_envelope, error as create_error_envelope

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LeadsConsumer:
    """
    Consumer for Leads Orchestrator tasks.
    
    Listens to {tenant}:orchestrators:leads:tasks and delegates to LeadsOrchestratorHarness.
    
    Uses RedisStreamsClient which automatically prefixes stream names with namespace.
    """
    
    def __init__(
        self,
        redis_client: RedisStreamsClient,
        tenant_id: str = "default",
        consumer_group: str = "leads-workers",
        consumer_name: Optional[str] = None,
        environment: str = "development",
    ):
        """
        Initialize consumer.
        
        Args:
            redis_client: Redis client
            tenant_id: Tenant identifier
            consumer_group: Consumer group name
            consumer_name: Consumer instance name (defaults to hostname)
            environment: Environment (development/staging/production)
        """
        self.redis = redis_client  # This is now RedisStreamsClient, not raw redis
        self.tenant_id = tenant_id
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"leads-worker-{os.getpid()}"
        self.environment = environment
        self.shutdown_requested = False  # Graceful shutdown flag
        
        # Stream names - these will be prefixed by RedisStreamsClient with namespace
        self.task_stream = f"{tenant_id}:orchestrators:leads:tasks"
        self.result_stream = f"{tenant_id}:orchestrators:leads:results"
        
        # Create harness
        self.harness = LeadsOrchestratorHarness(
            redis_client=redis_client,
            tenant_id=tenant_id,
            environment=environment,
            enable_observability=(environment == "production"),
        )
        
        # Ensure consumer group exists
        self._ensure_consumer_group()
        
        logger.info(
            f"LeadsConsumer initialized: tenant={tenant_id}, "
            f"group={consumer_group}, name={self.consumer_name}"
        )
    
    def _ensure_consumer_group(self):
        """Create consumer group if it doesn't exist"""
        try:
            # RedisStreamsClient.xgroup_create returns False if group exists, True if created
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
        except Exception as e:
            logger.error(f"Error creating consumer group: {e}")
            raise
    
    async def process_task(self, message_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single task from the stream.
        
        Args:
            message_id: Redis stream message ID
            message_data: Message payload
            
        Returns:
            Execution result
        """
        try:
            # Parse typed envelope
            envelope = from_redis_message(message_data)
            task_data = envelope.payload
            task_id = envelope.metadata.task_id
            
            logger.info(f"[CONSUMER] Processing task {task_id} from message {message_id}")
            logger.info(f"[CONSUMER] Task data: {task_data}")
            
            # Execute through harness
            result = await self.harness.execute(task_data)
            
            logger.info(f"[CONSUMER] Task {task_id} execution result: {result}")
            
            # Create result envelope
            result_envelope = create_result_envelope(
                original=envelope,
                payload=result,
                source="leads_orchestrator"
            )
            
            # Publish result to result stream
            self.redis.xadd(
                self.result_stream,
                to_redis_fields(result_envelope)
            )
            
            # Acknowledge message
            self.redis.xack(self.task_stream, self.consumer_group, message_id)
            
            logger.info(f"Task {task_id} completed successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing task: {e}", exc_info=True)
            
            # Don't ack - let it retry or go to pending
            raise
    
    async def run(self, block_ms: int = 5000, count: int = 10):
        """
        Run consumer loop.
        
        Args:
            block_ms: Block timeout in milliseconds
            count: Max messages to read per batch
        """
        logger.info(f"Starting consumer loop on {self.task_stream}")
        
        while not self.shutdown_requested:
            try:
                # Read from stream using RedisStreamsClient which handles namespace
                messages = self.redis.xreadgroup(
                    group=self.consumer_group,
                    consumer=self.consumer_name,
                    streams={self.task_stream: ">"},
                    count=count,
                    block=block_ms,
                )
                
                if not messages:
                    continue
                
                # Process messages
                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        if self.shutdown_requested:
                            logger.info("Shutdown requested, stopping message processing")
                            return
                        try:
                            await self.process_task(message_id, message_data)
                        except Exception as e:
                            logger.error(f"Failed to process message {message_id}: {e}")
                            # Continue to next message
                            
            except KeyboardInterrupt:
                logger.info("Consumer interrupted by user (Ctrl+C)")
                self.shutdown_requested = True
                break
            except Exception as e:
                if not self.shutdown_requested:
                    logger.error(f"Error in consumer loop: {e}", exc_info=True)
                    await asyncio.sleep(1)  # Brief pause before retry
        
        logger.info("Consumer loop exited gracefully")


async def main():
    """Main entry point"""
    # Get configuration from environment
    tenant_id = os.getenv("TENANT_ID", "default")
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Connect to Redis - use RedisStreamsClient which handles namespace prefixing
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for leads_orchestrator)")

    redis_streams = RedisStreamsClient(url=redis_url)
    
    # Create consumer
    consumer = LeadsConsumer(
        redis_client=redis_streams,  # Pass the wrapper, not redis_streams.client
        tenant_id=tenant_id,
        environment=environment,
    )
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        consumer.shutdown_requested = True
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        await consumer.run()
    finally:
        logger.info("LeadsOrchestrator consumer shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
