"""
Redis Token Bucket Quota Manager

Distributed token bucket algorithm using Redis + Lua script.
Good for: Production with multiple workers, fair rate limiting

Features:
- Atomic operations (Lua script)
- Distributed across workers
- Token refill over time
- Configurable burst size
"""

import logging
import time
from typing import Dict, Optional

from core.harness.interfaces import IQuotaManager, QuotaExceededError

logger = logging.getLogger(__name__)

# Try to import redis (optional dependency)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis not installed. Install with: pip install redis")


# Lua script for atomic token bucket operations
TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

-- Get current bucket state
local state = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(state[1]) or capacity
local last_refill = tonumber(state[2]) or now

-- Calculate tokens to add based on time passed
local time_passed = now - last_refill
local tokens_to_add = time_passed * refill_rate

-- Update token count (capped at capacity)
tokens = math.min(capacity, tokens + tokens_to_add)

-- Check if we have enough tokens
if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)  -- 1 hour TTL
    return {1, tokens}  -- Success, remaining tokens
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return {0, tokens}  -- Failure, remaining tokens
end
"""


class RedisTokenBucket(IQuotaManager):
    """
    Distributed token bucket rate limiter using Redis.
    
    Implements fair rate limiting across multiple workers.
    Tokens refill over time based on configured rate.
    
    Token Bucket Algorithm:
        - Bucket has capacity (max tokens)
        - Tokens refill at constant rate
        - Requests consume tokens
        - If not enough tokens, request denied
        - Allows bursts up to capacity
    
    Example:
        # Allow 1000 requests per hour with burst of 100
        quota = RedisTokenBucket(
            redis_client,
            capacity=100,  # burst size
            refill_rate=1000/3600,  # tokens per second
            key_prefix="quota:"
        )
        
        # Check if execution allowed
        if await quota.can_execute("LeadsOrchestrator"):
            # Execute task
            await quota.record_execution("LeadsOrchestrator")
        else:
            raise QuotaExceededError("Rate limit exceeded")
    """
    
    def __init__(
        self,
        redis_client,
        capacity: int = 100,
        refill_rate: float = 1.0,  # tokens per second
        key_prefix: str = "quota:",
        cost_per_execution: int = 1
    ):
        """
        Initialize Redis token bucket.
        
        Args:
            redis_client: Redis client instance
            capacity: Maximum tokens (burst size)
            refill_rate: Tokens added per second
            key_prefix: Redis key prefix
            cost_per_execution: Tokens consumed per execution
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis not installed. Install with: pip install redis")
        
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.key_prefix = key_prefix
        self.cost_per_execution = cost_per_execution
        
        # Register Lua script
        try:
            self.script = self.redis.register_script(TOKEN_BUCKET_SCRIPT)
            logger.info(
                f"RedisTokenBucket initialized: capacity={capacity}, "
                f"refill_rate={refill_rate}/s"
            )
        except Exception as e:
            logger.error(f"Redis script registration failed: {e}")
            raise QuotaExceededError(f"Redis quota initialization failed: {e}") from e
    
    async def can_execute(self, agent_id: str) -> bool:
        """
        Check if agent can execute (has quota).
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            True if execution allowed, False otherwise
        """
        key = f"{self.key_prefix}{agent_id}"
        now = time.time()
        
        try:
            # Execute Lua script atomically
            result = self.script(
                keys=[key],
                args=[
                    self.capacity,
                    self.refill_rate,
                    now,
                    self.cost_per_execution
                ]
            )
            
            success, remaining = result
            
            if success:
                logger.debug(
                    f"Quota check passed for {agent_id}: "
                    f"{remaining:.2f} tokens remaining"
                )
                return True
            else:
                logger.warning(
                    f"Quota exceeded for {agent_id}: "
                    f"{remaining:.2f} tokens remaining"
                )
                return False
                
        except Exception as e:
            logger.error(f"Quota check failed for {agent_id}: {e}")
            # Fail open (allow execution on error)
            return True
    
    async def record_execution(self, agent_id: str) -> None:
        """
        Record execution (consume tokens).
        
        Note: Token consumption happens in can_execute().
        This method is a no-op for token bucket.
        
        Args:
            agent_id: Agent identifier
        """
        # Token bucket consumes tokens in can_execute()
        # This is here to satisfy IQuotaManager interface
        pass
    
    async def get_remaining_quota(self, agent_id: str) -> Dict[str, float]:
        """
        Get remaining quota for agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Dictionary with 'tokens' and 'capacity'
        """
        key = f"{self.key_prefix}{agent_id}"
        now = time.time()
        
        try:
            # Get current state
            state = self.redis.hmget(key, 'tokens', 'last_refill')
            
            tokens = float(state[0]) if state[0] else self.capacity
            last_refill = float(state[1]) if state[1] else now
            
            # Calculate refilled tokens
            time_passed = now - last_refill
            tokens_to_add = time_passed * self.refill_rate
            current_tokens = min(self.capacity, tokens + tokens_to_add)
            
            return {
                'tokens': current_tokens,
                'capacity': self.capacity,
                'percentage': (current_tokens / self.capacity) * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to get quota for {agent_id}: {e}")
            return {
                'tokens': self.capacity,
                'capacity': self.capacity,
                'percentage': 100.0
            }
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"RedisTokenBucket(capacity={self.capacity}, "
            f"refill_rate={self.refill_rate}/s)"
        )
