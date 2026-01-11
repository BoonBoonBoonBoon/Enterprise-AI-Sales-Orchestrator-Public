"""
Exponential Backoff Retry Strategy

Delay pattern: 1s, 2s, 4s, 8s, 16s, 32s...
Good for: LLM rate limits, transient network errors, API throttling

Use this when:
- Service recovery time is unpredictable
- Rate limits need gradual backoff
- Default choice for most scenarios
"""

import asyncio
import logging
from typing import Any, Callable

from core.harness.interfaces import IRetryStrategy, RetryExhaustedError

logger = logging.getLogger(__name__)


class ExponentialBackoffRetry(IRetryStrategy):
    """
    Exponential backoff retry strategy.
    
    Each retry waits exponentially longer:
    - Attempt 1: base_delay (e.g., 1s)
    - Attempt 2: base_delay * 2^1 (e.g., 2s)
    - Attempt 3: base_delay * 2^2 (e.g., 4s)
    - Attempt 4: base_delay * 2^3 (e.g., 8s)
    
    Delay is capped at max_delay to prevent excessive waiting.
    
    Examples:
        # Default: 3 retries, 1s base, max 60s
        retry = ExponentialBackoffRetry()
        
        # Aggressive: 5 retries, 0.5s base, max 30s
        retry = ExponentialBackoffRetry(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0
        )
        
        # Conservative: 2 retries, 2s base, max 120s
        retry = ExponentialBackoffRetry(
            max_retries=2,
            base_delay=2.0,
            max_delay=120.0
        )
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        """
        Initialize exponential backoff retry strategy.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds before first retry (default: 1.0)
            max_delay: Maximum delay between retries in seconds (default: 60.0)
            exponential_base: Exponential multiplier (default: 2.0)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        
        logger.info(
            f"ExponentialBackoffRetry initialized: "
            f"max_retries={max_retries}, base_delay={base_delay}s, "
            f"max_delay={max_delay}s, exponential_base={exponential_base}"
        )
    
    async def execute_with_retry(
        self,
        func: Callable,
        args: tuple,
        execution_id: str
    ) -> Any:
        """
        Execute function with exponential backoff retry logic.
        
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
                
                # Calculate delay with exponential backoff
                delay = min(
                    self.base_delay * (self.exponential_base ** attempt),
                    self.max_delay
                )
                
                logger.info(
                    f"[{execution_id}] Retrying in {delay:.2f}s "
                    f"(exponential backoff: base={self.base_delay}s, "
                    f"multiplier={self.exponential_base}^{attempt})"
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
            f"ExponentialBackoffRetry("
            f"max_retries={self.max_retries}, "
            f"base_delay={self.base_delay}s, "
            f"max_delay={self.max_delay}s, "
            f"exponential_base={self.exponential_base})"
        )
