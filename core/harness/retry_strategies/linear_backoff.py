"""
Linear Backoff Retry Strategy

Delay pattern: 2s, 4s, 6s, 8s, 10s...
Good for: Database locks, predictable recovery, slower systems

Use this when:
- Service recovery is predictable and linear
- Resource contention resolves over time
- Database locks that clear predictably
"""

import asyncio
import logging
from typing import Any, Callable

from core.harness.interfaces import IRetryStrategy, RetryExhaustedError

logger = logging.getLogger(__name__)


class LinearBackoffRetry(IRetryStrategy):
    """
    Linear backoff retry strategy.
    
    Each retry waits linearly longer:
    - Attempt 1: base_delay (e.g., 2s)
    - Attempt 2: base_delay + increment (e.g., 4s)
    - Attempt 3: base_delay + 2*increment (e.g., 6s)
    - Attempt 4: base_delay + 3*increment (e.g., 8s)
    
    Examples:
        # Default: 3 retries, 2s base, 2s increment
        retry = LinearBackoffRetry()
        # Pattern: 2s, 4s, 6s
        
        # Fast: 5 retries, 1s base, 1s increment
        retry = LinearBackoffRetry(
            max_retries=5,
            base_delay=1.0,
            increment=1.0
        )
        # Pattern: 1s, 2s, 3s, 4s, 5s
        
        # Slow: 3 retries, 5s base, 5s increment
        retry = LinearBackoffRetry(
            max_retries=3,
            base_delay=5.0,
            increment=5.0
        )
        # Pattern: 5s, 10s, 15s
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        increment: float = 2.0
    ):
        """
        Initialize linear backoff retry strategy.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds before first retry (default: 2.0)
            increment: Delay increment in seconds for each retry (default: 2.0)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.increment = increment
        
        logger.info(
            f"LinearBackoffRetry initialized: "
            f"max_retries={max_retries}, base_delay={base_delay}s, "
            f"increment={increment}s"
        )
    
    async def execute_with_retry(
        self,
        func: Callable,
        args: tuple,
        execution_id: str
    ) -> Any:
        """
        Execute function with linear backoff retry logic.
        
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
                
                # Calculate delay with linear backoff
                delay = self.base_delay + (attempt * self.increment)
                
                logger.info(
                    f"[{execution_id}] Retrying in {delay:.2f}s "
                    f"(linear backoff: base={self.base_delay}s + "
                    f"{attempt}*{self.increment}s)"
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
            f"LinearBackoffRetry("
            f"max_retries={self.max_retries}, "
            f"base_delay={self.base_delay}s, "
            f"increment={self.increment}s)"
        )
