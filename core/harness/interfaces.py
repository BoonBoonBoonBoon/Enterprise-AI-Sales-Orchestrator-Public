"""
Harness Component Interfaces (Contracts)

All pluggable components implement these interfaces.
This allows swapping implementations without changing orchestrator code.

Example:
    IRetryStrategy interface:
    - ExponentialBackoffRetry (fast backoff)
    - LinearBackoffRetry (slow backoff)
    - JitteredBackoffRetry (distributed)
    
    All implement same interface, can swap freely.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Dict


class IRetryStrategy(ABC):
    """
    Interface for retry strategies.
    
    Implementations handle transient failures by retrying with backoff.
    """
    
    @abstractmethod
    async def execute_with_retry(
        self,
        func: Callable,
        args: tuple,
        execution_id: str
    ) -> Any:
        """
        Execute function with automatic retry logic.
        
        Args:
            func: Async or sync function to execute
            args: Arguments to pass to function
            execution_id: Unique execution ID for logging/tracing
        
        Returns:
            Result from successful execution
        
        Raises:
            Exception: Raised if all retries exhausted
        """
        pass


class IObservability(ABC):
    """
    Interface for observability/tracing systems.
    
    Implementations handle distributed tracing, metrics, and logging.
    """
    
    @abstractmethod
    def start_span(self, name: str):
        """
        Start a tracing span (context manager).
        
        Usage:
            with tracer.start_span("operation_name") as span:
                span.set_attribute("key", "value")
                # do work
        
        Args:
            name: Span name
        
        Returns:
            Context manager that yields a span object
        """
        pass
    
    @abstractmethod
    def record_metric(self, name: str, value: float, tags: Dict[str, str]):
        """
        Record a metric value.
        
        Usage:
            tracer.record_metric("requests_processed", 100, {"agent": "leads"})
        
        Args:
            name: Metric name (e.g., "requests_processed")
            value: Metric value
            tags: Tags for filtering (e.g., {"agent": "leads", "status": "success"})
        """
        pass
    
    @abstractmethod
    def log_event(self, level: str, message: str, context: Dict[str, Any]):
        """
        Log an event with context.
        
        Usage:
            tracer.log_event("ERROR", "Task failed", {"task_id": "123", "error": "..."})
        
        Args:
            level: Log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
            message: Log message
            context: Additional context (will be attached to trace/logs)
        """
        pass


class ICheckpointer(ABC):
    """
    Interface for execution state persistence.
    
    Implementations save/load execution state for resumption on failure.
    Enables long-running tasks to survive process crashes.
    """
    
    @abstractmethod
    async def save(self, execution_id: str, state: Dict[str, Any]) -> bool:
        """
        Save execution state.
        
        Args:
            execution_id: Unique execution ID
            state: State dictionary to save
        
        Returns:
            True if save successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Load execution state.
        
        Args:
            execution_id: Unique execution ID
        
        Returns:
            State dictionary if found, None if not found
        """
        pass
    
    @abstractmethod
    async def delete(self, execution_id: str) -> bool:
        """
        Delete execution state (cleanup after completion).
        
        Args:
            execution_id: Unique execution ID
        
        Returns:
            True if deleted, False if not found
        """
        pass


class IQuotaManager(ABC):
    """
    Interface for rate limiting and quota enforcement.
    
    Implementations prevent resource exhaustion by enforcing limits.
    """
    
    @abstractmethod
    async def can_execute(self, agent: Any) -> bool:
        """
        Check if execution is allowed (within quota).
        
        Usage:
            if await quota_mgr.can_execute(agent):
                # Execute
            else:
                raise QuotaExceededError(...)
        
        Args:
            agent: Agent/orchestrator to check quota for
        
        Returns:
            True if quota available, False if exhausted
        """
        pass
    
    @abstractmethod
    async def record_execution(self, agent: Any):
        """
        Record an execution (consume quota).
        
        Note: Some implementations consume quota in can_execute(),
        others do it here. Both patterns are valid.
        
        Args:
            agent: Agent/orchestrator that executed
        """
        pass
    
    @abstractmethod
    async def get_remaining_quota(self, agent: Any) -> int:
        """
        Get remaining quota for agent.
        
        Usage:
            remaining = await quota_mgr.get_remaining_quota(agent)
            if remaining < 10:
                logger.warning(f"Low quota: {remaining} remaining")
        
        Args:
            agent: Agent/orchestrator to check
        
        Returns:
            Number of executions remaining in current window
        """
        pass


# Exception classes for harness errors

class QuotaExceededError(Exception):
    """Raised when quota limit is exceeded"""
    pass


class CheckpointError(Exception):
    """Raised when checkpoint save/load fails"""
    pass


class RetryExhaustedError(Exception):
    """Raised when all retries exhausted"""
    pass
