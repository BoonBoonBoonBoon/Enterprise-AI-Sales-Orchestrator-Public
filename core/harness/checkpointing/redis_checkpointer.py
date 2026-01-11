"""
Redis Checkpointer

Stores checkpoints in Redis with TTL.
Good for: Staging, short-lived checkpoints, fast recovery

Features:
- Fast in-memory storage
- Automatic expiration (TTL)
- Low latency
- Cheap for short-term storage
"""

import json
import logging
from typing import Dict, Any, Optional

from core.harness.interfaces import ICheckpointer, CheckpointError

logger = logging.getLogger(__name__)

# Try to import redis (optional dependency)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis not installed. Install with: pip install redis")


class RedisCheckpointer(ICheckpointer):
    """
    Redis-based checkpointing (fast, temporary).
    
    Stores execution state in Redis with configurable TTL.
    Perfect for short-lived checkpoints and fast recovery.
    
    Example:
        checkpointer = RedisCheckpointer(
            redis_client,
            ttl_seconds=86400,  # 24 hours
            key_prefix="checkpoint:"
        )
        
        # Save checkpoint
        await checkpointer.save("exec_123", {"state": "data", "progress": 50})
        
        # Load checkpoint
        state = await checkpointer.load("exec_123")
        
        # Delete checkpoint
        await checkpointer.delete("exec_123")
    """
    
    def __init__(
        self,
        redis_client,
        ttl_seconds: int = 86400,  # 24 hours
        key_prefix: str = "checkpoint:"
    ):
        """
        Initialize Redis checkpointer.
        
        Args:
            redis_client: Redis client instance
            ttl_seconds: Time-to-live in seconds (default: 86400 = 24 hours)
            key_prefix: Key prefix for checkpoints (default: "checkpoint:")
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis not installed. Install with: pip install redis")
        
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.key_prefix = key_prefix
        
        # Test connection
        try:
            self.redis.ping()
            logger.info(
                f"RedisCheckpointer initialized: ttl={ttl_seconds}s, "
                f"prefix={key_prefix}"
            )
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise CheckpointError(f"Redis connection failed: {e}") from e
    
    async def save(self, execution_id: str, state: Dict[str, Any]) -> bool:
        """
        Save execution state to Redis with TTL.
        
        Args:
            execution_id: Unique execution ID
            state: State dictionary to save
        
        Returns:
            True if save successful, False otherwise
        """
        key = f"{self.key_prefix}{execution_id}"
        
        try:
            # Serialize state to JSON
            serialized = json.dumps(state)
            
            # Save to Redis with TTL
            self.redis.setex(key, self.ttl, serialized)
            
            logger.debug(
                f"Checkpoint saved: {execution_id} "
                f"(size={len(serialized)} bytes, ttl={self.ttl}s)"
            )
            return True
            
        except Exception as e:
            logger.error(f"Checkpoint save failed for {execution_id}: {e}")
            return False
    
    async def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Load execution state from Redis.
        
        Args:
            execution_id: Unique execution ID
        
        Returns:
            State dictionary if found, None if not found
        """
        key = f"{self.key_prefix}{execution_id}"
        
        try:
            # Get from Redis
            data = self.redis.get(key)
            
            if data is None:
                logger.debug(f"Checkpoint not found: {execution_id}")
                return None
            
            # Deserialize from JSON
            state = json.loads(data)
            logger.debug(f"Checkpoint loaded: {execution_id}")
            return state
            
        except json.JSONDecodeError as e:
            logger.error(f"Checkpoint deserialization failed for {execution_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Checkpoint load failed for {execution_id}: {e}")
            return None
    
    async def delete(self, execution_id: str) -> bool:
        """
        Delete execution state from Redis.
        
        Args:
            execution_id: Unique execution ID
        
        Returns:
            True if deleted, False if not found
        """
        key = f"{self.key_prefix}{execution_id}"
        
        try:
            deleted = self.redis.delete(key)
            
            if deleted:
                logger.debug(f"Checkpoint deleted: {execution_id}")
                return True
            else:
                logger.debug(f"Checkpoint not found for deletion: {execution_id}")
                return False
                
        except Exception as e:
            logger.error(f"Checkpoint deletion failed for {execution_id}: {e}")
            return False
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"RedisCheckpointer(ttl={self.ttl}s, prefix={self.key_prefix})"
        )
