"""
Jittered Exponential Backoff Retry Strategy

Delay pattern: Random around exponential (e.g., 0.7-1.3s, 1.4-2.6s, 2.8-5.2s...)
Good for: Production with multiple workers (prevents thundering herd)

Use this when:
- Multiple workers/instances retry simultaneously
- Need to prevent synchronized retries (thundering herd)
- Production environments with high concurrency
"""

import asyncio
import random
import logging
from typing import Any, Callable

from core.harness.interfaces import IRetryStrategy, RetryExhaustedError

logger = logging.getLogger(__name__)


class JitteredBackoffRetry(IRetryStrategy):
    """
    Jittered exponential backoff retry strategy.
    
    Adds randomness to exponential backoff to prevent thundering herd.
    
    Delay calculation:
    - base = base_delay * (exponential_base ^ attempt)
    - jitter = base * random.uniform(-jitter_factor, +jitter_factor)
    - final_delay = min(base + jitter, max_delay)
    
    This prevents multiple workers from retrying simultaneously,
    which can overload a recovering service.
    
    Examples:
        # Default: 3 retries, 1s base, 30% jitter
        retry = JitteredBackoffRetry()
        # Delays: ~0.7-1.3s, ~1.4-2.6s, ~2.8-5.2s
        
        # Production: 5 retries, 1s base, 50% jitter
        retry = JitteredBackoffRetry(
            max_retries=5,
            base_delay=1.0,
            jitter_factor=0.5
        )
        # Delays: ~0.5-1.5s, ~1-3s, ~2-6s, ~4-12s, ~8-24s
        
        # Conservative: 3 retries, 2s base, 20% jitter
        retry = JitteredBackoffRetry(
            max_retries=3,
            base_delay=2.0,
            jitter_factor=0.2
        )
        # Delays: ~1.6-2.4s, ~3.2-4.8s, ~6.4-9.6s
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter_factor: float = 0.3
    ):
        """
        Initialize jittered exponential backoff retry strategy.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds before first retry (default: 1.0)
            max_delay: Maximum delay between retries in seconds (default: 60.0)
            exponential_base: Exponential multiplier (default: 2.0)
            jitter_factor: Jitter randomness factor 0.0-1.0 (default: 0.3)
                          0.3 means +/- 30% randomness around the base delay
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter_factor = jitter_factor
        
        logger.info(
            f"JitteredBackoffRetry initialized: "
            f"max_retries={max_retries}, base_delay={base_delay}s, "
            f"max_delay={max_delay}s, exponential_base={exponential_base}, "
            f"jitter_factor={jitter_factor}"
        )
    
    async def execute_with_retry(
        self,
        func: Callable,
        args: tuple,
        execution_id: str
    ) -> Any:
        """
        Execute function with jittered exponential backoff retry logic.
        
        Args:
            func: Async or sync function to execute
            args: Arguments to pass to function
            execution_id: Unique execution ID for logging
        
        Returns:
            Result from successful execution
        
        Raises:
            RetryExhaustedError: If all retries exhausted
            Exception: Original exception from function if retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(
                    f"[{execution_id}] Attempt {attempt + 1}/{self.max_retries + 1}"
                )
                
                # Execute the function (handle both sync and async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args)
                else:
                    result = func(*args)
                
                # Success!
                if attempt > 0:
                    logger.info(
                        f"[{execution_id}] Success on attempt {attempt + 1} "
                        f"(after {attempt} retries)"
                    )
                else:
                    logger.debug(f"[{execution_id}] Success on first attempt")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Log the failure
                logger.warning(
                    f"[{execution_id}] Attempt {attempt + 1} failed: "
                    f"{type(e).__name__}: {e}"
                )
                
                # If this was the last attempt, raise
                if attempt == self.max_retries:
                    logger.error(
                        f"[{execution_id}] All {self.max_retries + 1} attempts exhausted"
                    )
                    raise RetryExhaustedError(
                        f"All {self.max_retries + 1} retry attempts exhausted. "
                        f"Last error: {type(e).__name__}: {e}"
                    ) from e
                
                # Calculate base exponential backoff
                base = self.base_delay * (self.exponential_base ** attempt)
                
                # Add jitter (randomness)
                jitter_range = base * self.jitter_factor
                jitter = random.uniform(-jitter_range, jitter_range)
                
                # Final delay with jitter, capped at max_delay
                delay = min(base + jitter, self.max_delay)
                
                logger.info(
                    f"[{execution_id}] Retrying in {delay:.2f}s "
                    f"(jittered exponential: base={base:.2f}s, "
                    f"jitter={jitter:+.2f}s, "
                    f"factor={self.jitter_factor})"
                )
                
                await asyncio.sleep(delay)
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        else:
            raise RetryExhaustedError("Retry logic error: no result and no exception")
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"JitteredBackoffRetry("
            f"max_retries={self.max_retries}, "
            f"base_delay={self.base_delay}s, "
            f"max_delay={self.max_delay}s, "
            f"exponential_base={self.exponential_base}, "
            f"jitter_factor={self.jitter_factor})"
        )
