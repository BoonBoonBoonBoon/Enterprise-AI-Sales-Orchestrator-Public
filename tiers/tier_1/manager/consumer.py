"""
Manager Agent Consumer

Redis Stream consumer that processes tasks from {tenant}:manager:tasks stream.
Manager makes decisions and delegates to Leads/Outreach orchestrators.
Results are published to {tenant}:manager:results stream.
"""

import asyncio
import json
import logging
import os
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

from config.settings import validate_keys

try:
    from services.redis import RedisPubSub
except ImportError:
    # Fallback for migration phase
    from agent.tools.redis.client import RedisPubSub
from .manager_agent_harness import ManagerAgentHarness
from core.envelope import from_redis_message, to_redis_fields, result as create_result_envelope, error as create_error_envelope
from core.dlq import DeadLetterQueue
from core.observability import start_redis_stream_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ManagerConsumer:
    """
    Consumer for Manager Agent tasks.
    
    Listens to {tenant}:manager:tasks stream.
    Manager decides which orchestrators to delegate to.
    Results published to {tenant}:manager:results stream.
    """
    
    def __init__(
        self,
        redis_client,
        tenant_id: str = "default",
        consumer_group: str = "manager-workers",
        consumer_name: Optional[str] = None,
        environment: str = "development",
    ):
        """
        Initialize Manager consumer.
        
        Args:
            redis_client: Redis client
            tenant_id: Tenant identifier
            consumer_group: Consumer group name
            consumer_name: Consumer instance name (defaults to hostname)
            environment: Environment (development/staging/production)
        """
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"manager-worker-{os.getpid()}"
        self.environment = environment
        
        # Stream names
        self.task_stream = f"{tenant_id}:manager:tasks"
        self.result_stream = f"{tenant_id}:manager:results"
        self.dlq = DeadLetterQueue(redis_client, self.task_stream)
        
        # Create harness
        self.harness = ManagerAgentHarness(
            redis_client=redis_client,
            tenant_id=tenant_id,
            environment=environment,
            enable_observability=(environment == "production"),
            enable_checkpointing=True,  # Manager handles multi-step workflows
        )
        
        # Ensure consumer group exists
        self._ensure_consumer_group()
        
        logger.info(
            f"ManagerConsumer initialized: tenant={tenant_id}, "
            f"group={consumer_group}, name={self.consumer_name}"
        )

    def _get_delivery_count(self, message_id: str) -> int:
        try:
            pending = self.redis.xpending_range(
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
                        source="manager_agent",
                        code="MANAGER_ERROR",
                    )
                    self.redis.xadd(self.result_stream, to_redis_fields(error_envelope))
                except Exception as publish_exc:  # pragma: no cover
                    logger.error(f"Failed to publish error envelope: {publish_exc}", exc_info=True)
            self.redis.xack(self.task_stream, self.consumer_group, message_id)
    
    def _ensure_consumer_group(self):
        """Create consumer group if it doesn't exist"""
        try:
            self.redis.xgroup_create(
                name=self.task_stream,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
            logger.info(f"Created consumer group {self.consumer_group} on {self.task_stream}")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Consumer group {self.consumer_group} already exists")
            else:
                logger.error(f"Error creating consumer group: {e}")
                raise
    
    async def process_task(self, message_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single task from the stream.
        
        Manager receives high-level goals and decides which orchestrators to delegate to.
        
        Args:
            message_id: Redis stream message ID
            message_data: Message payload
            
        Returns:
            Execution result (orchestration result)
        """
        try:
            # Parse typed envelope
            envelope = from_redis_message(message_data)
            task_data = envelope.payload
            task_id = envelope.metadata.task_id
            goal = task_data.get("goal", "")
            
            logger.info(f"Processing Manager task {task_id}: {goal}")
            
            # Execute through harness
            # Manager Deep Agent analyzes goal and delegates
            result = await self.harness.execute(task_data)
            
            # Create result envelope
            result_envelope = create_result_envelope(
                original=envelope,
                payload=result,
                source="manager_agent"
            )
            
            # Publish result to result stream
            self.redis.xadd(
                self.result_stream,
                to_redis_fields(result_envelope)
            )
            
            # Acknowledge message
            self.redis.xack(self.task_stream, self.consumer_group, message_id)
            
            logger.info(f"Manager task {task_id} completed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing Manager task: {e}", exc_info=True)
            self._handle_failure(message_id, message_data, e, envelope=locals().get("envelope"))
            raise
    
    async def run(self, block_ms: int = 5000, count: int = 10):
        """
        Run consumer loop.
        
        Args:
            block_ms: Block timeout in milliseconds
            count: Max messages to read per batch
        """
        logger.info(f"Starting Manager consumer loop on {self.task_stream}")
        
        while True:
            try:
                # Read from stream
                messages = self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.task_stream: ">"},
                    count=count,
                    block=block_ms,
                )
                
                if not messages:
                    pending = self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.consumer_name,
                        streams={self.task_stream: "0"},
                        count=count,
                        block=1,
                    )
                    if not pending:
                        continue
                    messages = pending
                
                # Process messages
                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        try:
                            await self.process_task(message_id, message_data)
                        except Exception as e:
                            logger.error(f"Failed to process message {message_id}: {e}")
                            # Continue to next message
                            
            except KeyboardInterrupt:
                logger.info("Manager consumer interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before retry


async def main():
    """Main entry point"""
        validate_keys(raise_on_missing=True)
    # Get configuration from environment
    tenant_id = os.getenv("TENANT_ID", "default")
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Connect to Redis
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for manager)")

    redis_pubsub = RedisPubSub(url=redis_url)
    redis_client = redis_pubsub.client

    start_redis_stream_metrics(
        redis_url=redis_url,
        tenant_id=tenant_id,
        component="manager",
        streams=[(f"{tenant_id}:manager:tasks", "manager-workers")],
    )
    
    # Create and run consumer
    consumer = ManagerConsumer(
        redis_client=redis_client,
        tenant_id=tenant_id,
        environment=environment,
    )
    
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
