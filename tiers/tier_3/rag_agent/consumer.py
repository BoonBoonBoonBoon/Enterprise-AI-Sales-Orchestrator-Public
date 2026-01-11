"""
RAG Agent Consumer

Redis Stream consumer that processes RAG enrichment tasks.
Reads from {tenant}:agents:rag:tasks and publishes to {tenant}:agents:rag:results.
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

from services.redis import RedisStreamsClient
from .rag_agent_harness import RAGAgentHarness
from core.envelope import from_redis_message, to_redis_fields, result as create_result_envelope, error as create_error_envelope

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RAGConsumer:
    """
    Consumer for RAG Agent tasks.
    
    Listens to {tenant}:agents:rag:tasks stream.
    RAG enriches leads with external data (vector search, APIs).
    Results published to {tenant}:agents:rag:results stream.
    """
    
    def __init__(
        self,
        redis_client,
        tenant_id: str = "default",
        consumer_group: str = "rag-workers",
        consumer_name: Optional[str] = None,
        environment: str = "development",
    ):
        """
        Initialize RAG consumer.
        
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
        self.consumer_name = consumer_name or f"rag-worker-{os.getpid()}"
        self.environment = environment
        
        # Stream names - organized under agents namespace
        self.task_stream = f"{tenant_id}:agents:rag:tasks"
        self.result_stream = f"{tenant_id}:agents:rag:results"
        
        # Create harness
        self.harness = RAGAgentHarness(
            redis_client=redis_client,
            tenant_id=tenant_id,
            environment=environment,
            enable_observability=(environment == "production"),
            enable_checkpointing=True,  # RAG enrichment is expensive, cache results
        )
        
        # Ensure consumer group exists
        self._ensure_consumer_group()
        
        logger.info(
            f"RAGConsumer initialized: tenant={tenant_id}, "
            f"group={consumer_group}, name={self.consumer_name}"
        )
    
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
        Process a single RAG enrichment task.
        
        RAG receives enrichment requests from Leads Orchestrator and enriches
        lead data with external sources (vector search, APIs).
        
        Args:
            message_id: Redis stream message ID
            message_data: Message payload
            
        Returns:
            Execution result (enriched data with confidence scores)
        """
        try:
            # Parse typed envelope
            envelope = from_redis_message(message_data)
            task_data = envelope.payload
            task_id = envelope.metadata.task_id
            goal = task_data.get("goal", "")
            
            logger.info(f"Processing RAG task {task_id}: {goal}")
            
            # Execute through harness
            # RAG Deep Agent will analyze goal and use appropriate tools
            result = await self.harness.execute(task_data)
            
            # Serialize result (handle LangChain objects)
            serialized_result = self._serialize_result(result)
            
            # Create result envelope
            result_envelope = create_result_envelope(
                original=envelope,
                payload=serialized_result,
                source="rag_agent"
            )
            
            # Publish result to result stream
            self.redis.xadd(
                self.result_stream,
                to_redis_fields(result_envelope)
            )
            
            # Acknowledge message
            self.redis.xack(self.task_stream, self.consumer_group, message_id)
            
            logger.info(f"RAG task {task_id} completed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing RAG task: {e}", exc_info=True)
            
            # Create error envelope if we have the original envelope context, otherwise generic
            # Note: In a real scenario we might not have 'envelope' if parsing failed.
            # For simplicity, we'll assume parsing might have failed or execution failed.
            
            # If we can't even parse the envelope, we can't easily reply with a correlated error.
            # But if we have task_data/task_id from a partial parse, we could try.
            # Here we'll just log it, but if we had the envelope we'd send an error envelope.
            
            # Don't ack - let it retry or go to pending
            raise

    def _serialize_result(self, result: Any) -> Any:
        """
        Serialize results to minimal payload format.
        
        Optimization: Extract only essential fields to reduce stream size.
        """
        if isinstance(result, dict):
            # If already minimal format from RAGAgent, pass through
            if 'status' in result and 'task_id' in result:
                return {
                    'status': result.get('status'),
                    'task_id': result.get('task_id'),
                    'enriched_fields': result.get('enriched_fields', [])[:10],
                    'sources': result.get('sources', [])[:5],
                    'confidence': result.get('confidence', 0.0),
                    'duration_ms': result.get('duration_ms', 0),
                    'error': result.get('error', '')[:200] if result.get('error') else None,
                    'completeness_score': result.get('completeness_score'),
                    'missing_fields': result.get('missing_fields', [])[:5] if result.get('missing_fields') else None
                }
            # Otherwise serialize recursively but limit depth
            return {k: self._serialize_value(v) for k, v in list(result.items())[:20]}
        elif isinstance(result, list):
            return [self._serialize_value(item) for item in result[:20]]
        else:
            return self._serialize_value(result)
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize individual values, handling LangChain objects"""
        if value is None:
            return None
        elif isinstance(value, (str, int, float, bool)):
            return value
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in list(value.items())[:10]}
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value[:10]]
        elif hasattr(value, "dict"):  # Pydantic models
            return value.dict()
        elif hasattr(value, "content"):  # LangChain Messages
            return str(value.content)[:500]
        else:
            return str(value)[:500]
    
    async def _claim_pending_messages(self):
        """Claim and process old pending messages from dead consumers."""
        try:
            # Auto-claim messages idle for > 60 seconds
            claimed = self.redis.xautoclaim(
                self.task_stream, 
                self.consumer_group, 
                self.consumer_name,
                min_idle_time=60000,  # 60 seconds
                start_id='0-0',
                count=20
            )
            
            if claimed and len(claimed[1]) > 0:
                logger.info(f"Claimed {len(claimed[1])} pending messages from dead consumers")
                for message_id, message_data in claimed[1]:
                    try:
                        await self.process_task(message_id, message_data)
                    except Exception as e:
                        logger.error(f"Failed to process claimed message {message_id}: {e}")
        except Exception as e:
            logger.warning(f"Could not claim pending messages: {e}")
    
    async def run(self, block_ms: int = 5000, count: int = 10):
        """
        Run consumer loop.
        
        Args:
            block_ms: Block timeout in milliseconds
            count: Max messages to read per batch
        """
        logger.info(f"Starting RAG consumer loop on {self.task_stream}")
        
        # First, claim any old pending messages from dead consumers
        await self._claim_pending_messages()
        
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
                    continue
                
                # Process messages
                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        try:
                            await self.process_task(message_id, message_data)
                        except Exception as e:
                            logger.error(f"Failed to process message {message_id}: {e}")
                            # Continue to next message
                            
            except KeyboardInterrupt:
                logger.info("RAG consumer interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before retry


async def main():
    """Main entry point"""
    # Get configuration from environment
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Connect to Redis
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (required for rag_agent)")

    redis_pubsub = RedisStreamsClient(url=redis_url)
    redis_client = redis_pubsub.client
    
    # Create and run consumer
    consumer = RAGConsumer(
        redis_client=redis_client,
        tenant_id=tenant_id,
        environment=environment,
    )
    
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
