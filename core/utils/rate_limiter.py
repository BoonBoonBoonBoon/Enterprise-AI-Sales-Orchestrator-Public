"""Rate Limiting for Workers and Streams.

Provides rate limiting capabilities to prevent worker overload and ensure
fair resource utilization across multiple streams and workers.

Supports:
- Token bucket algorithm (smooth rate limiting with bursts)
- Sliding window algorithm (strict rate limiting)
- Per-worker rate limits (individual worker capacity)
- Per-stream rate limits (shared across all consumers)
- Redis-backed distributed rate limiting (shared state)
- Local in-memory rate limiting (single process)

Usage:
    from agent.utils.rate_limiter import RateLimiter, RateLimitConfig
    
    # Create rate limiter
    config = RateLimitConfig(
        rate_per_second=10,  # 10 messages per second
        burst_size=20,       # Allow bursts up to 20
        algorithm="token_bucket"
    )
    limiter = RateLimiter(config, redis_client=redis)
    
    # Check if allowed (blocks until token available)
    if limiter.acquire(key="worker-123"):
        # Process message
        pass

Configuration:
    RATE_LIMIT_ENABLED: 1 | 0 (default: 0)
    RATE_LIMIT_ALGORITHM: token_bucket | sliding_window (default: token_bucket)
    RATE_LIMIT_PER_SECOND: int (default: 100)
    RATE_LIMIT_BURST_SIZE: int (default: 200)
    RATE_LIMIT_BACKEND: redis | memory (default: memory)

Examples:
    # Conservative: 5 msg/sec with small burst
    config = RateLimitConfig(rate_per_second=5, burst_size=10)
    
    # High throughput: 100 msg/sec with large burst
    config = RateLimitConfig(rate_per_second=100, burst_size=200)
    
    # Strict: No burst allowed
    config = RateLimitConfig(rate_per_second=10, burst_size=10, algorithm="sliding_window")
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional, Literal
from threading import Lock
import math


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    
    rate_per_second: float = 100.0  # Messages per second
    burst_size: int = 200  # Maximum burst size
    algorithm: Literal["token_bucket", "sliding_window"] = "token_bucket"
    backend: Literal["redis", "memory"] = "memory"
    enabled: bool = True
    
    @classmethod
    def from_env(cls) -> "RateLimitConfig":
        """Load configuration from environment variables."""
        return cls(
            rate_per_second=float(os.getenv("RATE_LIMIT_PER_SECOND", "100")),
            burst_size=int(os.getenv("RATE_LIMIT_BURST_SIZE", "200")),
            algorithm=os.getenv("RATE_LIMIT_ALGORITHM", "token_bucket"),  # type: ignore
            backend=os.getenv("RATE_LIMIT_BACKEND", "memory"),  # type: ignore
            enabled=os.getenv("RATE_LIMIT_ENABLED", "0") == "1"
        )


class TokenBucket:
    """Token bucket rate limiter (allows bursts)."""
    
    def __init__(self, rate: float, capacity: int):
        """Initialize token bucket.
        
        Args:
            rate: Tokens added per second
            capacity: Maximum tokens in bucket
        """
        if capacity < 0:
            raise ValueError("capacity must be >= 0")
        if rate < 0:
            raise ValueError("rate must be >= 0")
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.lock = Lock()
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        self.tokens = min(
            self.capacity,
            self.tokens + (elapsed * self.rate)
        )
        self.last_refill = now
    
    def acquire(self, tokens: int = 1, block: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            block: If True, block until tokens available
            timeout: Maximum time to block (None = infinite)
        
        Returns:
            True if tokens acquired, False otherwise
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                
                if not block:
                    return False
                
                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False
            
            # Sleep until tokens available
            time.sleep(min(wait_time, 0.1))  # Max 100ms sleep
    
    def available(self) -> float:
        """Get current available tokens."""
        with self.lock:
            self._refill()
            return self.tokens


class SlidingWindow:
    """Sliding window rate limiter (strict rate limit, no bursts)."""
    
    def __init__(self, rate: float, window_size: float = 1.0):
        """Initialize sliding window.
        
        Args:
            rate: Maximum requests per window
            window_size: Window size in seconds
        """
        self.rate = rate
        self.window_size = window_size
        self.requests: list[float] = []
        self.lock = Lock()
    
    def _cleanup(self, now: float):
        """Remove expired requests."""
        cutoff = now - self.window_size
        self.requests = [t for t in self.requests if t > cutoff]
    
    def acquire(self, block: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire a slot in the window.
        
        Args:
            block: If True, block until slot available
            timeout: Maximum time to block (None = infinite)
        
        Returns:
            True if slot acquired, False otherwise
        """
        start_time = time.time()
        
        while True:
            now = time.time()
            
            with self.lock:
                self._cleanup(now)
                
                if len(self.requests) < self.rate:
                    self.requests.append(now)
                    return True
                
                if not block:
                    return False
                
                # Calculate wait time until oldest request expires
                oldest = min(self.requests)
                wait_time = max(0, (oldest + self.window_size) - now)
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False
            
            # Sleep until slot available
            time.sleep(min(wait_time, 0.1))  # Max 100ms sleep
    
    def available(self) -> int:
        """Get current available slots."""
        with self.lock:
            self._cleanup(time.time())
            return int(self.rate - len(self.requests))


class RedisTokenBucket:
    """Distributed token bucket using Redis."""
    
    def __init__(self, redis_client, key_prefix: str, rate: float, capacity: int):
        """Initialize Redis-backed token bucket.
        
        Args:
            redis_client: Redis client instance
            key_prefix: Key prefix for rate limit data
            rate: Tokens added per second
            capacity: Maximum tokens in bucket
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.rate = rate
        self.capacity = capacity
    
    def _get_key(self, identifier: str) -> str:
        """Get Redis key for identifier."""
        return f"{self.key_prefix}:ratelimit:{identifier}"
    
    def acquire(self, identifier: str, tokens: int = 1, block: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire tokens using Redis Lua script.
        
        Args:
            identifier: Unique identifier (worker ID, stream name, etc.)
            tokens: Number of tokens to acquire
            block: If True, block until tokens available
            timeout: Maximum time to block
        
        Returns:
            True if tokens acquired, False otherwise
        """
        key = self._get_key(identifier)
        start_time = time.time()
        
        # Lua script for atomic token bucket operation
        script = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        
        local data = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(data[1]) or capacity
        local last_refill = tonumber(data[2]) or now
        
        -- Refill tokens based on elapsed time
        local elapsed = now - last_refill
        tokens = math.min(capacity, tokens + (elapsed * rate))
        
        -- Check if enough tokens available
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 60)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 60)
            return 0
        end
        """
        
        while True:
            now = time.time()
            result = self.redis.client.eval(
                script,
                1,
                key,
                self.rate,
                self.capacity,
                tokens,
                now
            )
            
            if result == 1:
                return True
            
            if not block:
                return False
            
            # Wait before retry
            time.sleep(0.1)
            
            # Check timeout
            if timeout is not None and (time.time() - start_time) > timeout:
                return False


class RateLimiter:
    """Rate limiter with multiple backend support."""
    
    def __init__(self, config: RateLimitConfig, redis_client=None, key_prefix: str = "agentic"):
        """Initialize rate limiter.
        
        Args:
            config: Rate limit configuration
            redis_client: Redis client (required if backend='redis')
            key_prefix: Key prefix for Redis keys
        """
        self.config = config
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        
        # Local limiters (for memory backend)
        self._local_limiters: dict[str, TokenBucket | SlidingWindow] = {}
        self._lock = Lock()
    
    def _get_local_limiter(self, identifier: str) -> TokenBucket | SlidingWindow:
        """Get or create local limiter for identifier."""
        with self._lock:
            if identifier not in self._local_limiters:
                if self.config.algorithm == "token_bucket":
                    self._local_limiters[identifier] = TokenBucket(
                        rate=self.config.rate_per_second,
                        capacity=self.config.burst_size
                    )
                else:
                    self._local_limiters[identifier] = SlidingWindow(
                        rate=self.config.rate_per_second,
                        window_size=1.0
                    )
            return self._local_limiters[identifier]
    
    def acquire(
        self,
        key: str,
        tokens: int = 1,
        block: bool = True,
        timeout: Optional[float] = None
    ) -> bool:
        """Acquire rate limit token.
        
        Args:
            key: Identifier (worker ID, stream name, etc.)
            tokens: Number of tokens to acquire
            block: If True, block until token available
            timeout: Maximum time to block
        
        Returns:
            True if acquired, False otherwise
        """
        if not self.config.enabled:
            return True
        
        if self.config.backend == "redis" and self.redis_client:
            if self.config.algorithm == "token_bucket":
                limiter = RedisTokenBucket(
                    self.redis_client,
                    self.key_prefix,
                    self.config.rate_per_second,
                    self.config.burst_size
                )
                return limiter.acquire(key, tokens, block, timeout)
            else:
                # Sliding window with Redis not implemented yet
                # Fall back to memory
                pass
        
        # Memory backend
        limiter = self._get_local_limiter(key)
        if isinstance(limiter, TokenBucket):
            return limiter.acquire(tokens, block, timeout)
        else:
            return limiter.acquire(block, timeout)
    
    def available(self, key: str) -> float:
        """Get available capacity for key.
        
        Args:
            key: Identifier to check
        
        Returns:
            Available tokens/slots
        """
        if not self.config.enabled:
            return float('inf')
        
        limiter = self._get_local_limiter(key)
        return limiter.available()


# Global rate limiter instance (initialized by workers)
_rate_limiter: Optional[RateLimiter] = None


def init_rate_limiter(config: Optional[RateLimitConfig] = None, redis_client=None) -> RateLimiter:
    """Initialize global rate limiter.
    
    Args:
        config: Rate limit configuration (None = load from env)
        redis_client: Redis client for distributed rate limiting
    
    Returns:
        Initialized rate limiter
    """
    global _rate_limiter
    
    if config is None:
        config = RateLimitConfig.from_env()
    
    _rate_limiter = RateLimiter(config, redis_client)
    
    if config.enabled:
        print(f"[RateLimiter] Initialized: {config.algorithm} @ {config.rate_per_second}/sec (burst: {config.burst_size})")
    else:
        print(f"[RateLimiter] Disabled")
    
    return _rate_limiter


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance.
    
    Returns:
        Rate limiter instance
    
    Raises:
        RuntimeError: If rate limiter not initialized
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        # Auto-initialize with defaults
        init_rate_limiter()
    
    return _rate_limiter


__all__ = [
    "RateLimitConfig",
    "RateLimiter",
    "TokenBucket",
    "SlidingWindow",
    "RedisTokenBucket",
    "init_rate_limiter",
    "get_rate_limiter",
]
