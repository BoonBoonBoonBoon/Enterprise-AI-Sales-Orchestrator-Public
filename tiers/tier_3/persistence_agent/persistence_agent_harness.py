"""
Persistence Agent Harness

Wraps Persistence Agent with:
- Retry logic with exponential backoff
- Observability (structured logging)
- Checkpointing for long-running operations
- Quota management
- Error handling and recovery
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def _trace_log(actor: str, *, correlation_id: str, task_id: str, step: str, detail: str, **kwargs: Any) -> None:
    """Structured trace logging without external dependencies."""
    try:
        payload = {
            "trace": True,
            "actor": actor,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "step": step,
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat(),
        }
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        logger.info(json.dumps(payload))
    except Exception:
        pass


class PersistenceAgentHarness:
    """
    Harness wrapper for Persistence Agent providing reliability layer.
    
    Features:
    - Automatic retry with exponential backoff
    - Request/response logging
    - Execution time tracking
    - Error recovery
    - Quota tracking
    """
    
    def __init__(
        self,
        agent,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        checkpoint_enabled: bool = True
    ):
        """
        Initialize Persistence Agent Harness.
        
        Args:
            agent: PersistenceAgent instance to wrap
            max_retries: Maximum retry attempts (default: 3)
            initial_backoff: Initial backoff in seconds (default: 1.0)
            max_backoff: Maximum backoff in seconds (default: 60.0)
            checkpoint_enabled: Enable checkpointing (default: True)
        """
        self.agent = agent
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.checkpoint_enabled = checkpoint_enabled
        
        # Tracking
        self.request_count = 0
        self.error_count = 0
        self.retry_count = 0
    
    async def execute(
        self,
        task_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute persistence task with retry logic and observability.
        
        Args:
            task_data: Task data for persistence operation
            context: Optional execution context
        
        Returns:
            Execution result with metadata
        """
        self.request_count += 1
        request_id = context.get("request_id") if context else f"req_{self.request_count}"

        task_identifier = str((task_data or {}).get("task_id") or request_id)
        correlation_id = str(
            (task_data or {}).get("correlation_id")
            or (task_data or {}).get("task_id")
            or request_id
        )
        
        start_time = time.time()
        attempt = 0
        backoff = self.initial_backoff

        _trace_log(
            "persistence_agent",
            correlation_id=correlation_id,
            task_id=task_identifier,
            step="received",
            detail="persistence task received",
            request_id=request_id,
        )
        
        logger.info(
            f"[{request_id}] Starting persistence task",
            extra={
                "request_id": request_id,
                "task_data": task_data,
                "attempt": attempt
            }
        )
        
        while attempt <= self.max_retries:
            try:
                # Execute through agent
                result = await self.agent.execute(task_data, context)
                
                # Check if result indicates error
                if result.get("status") == "error":
                    raise Exception(result.get("error", "Unknown error"))
                
                # Success
                execution_time = time.time() - start_time
                
                logger.info(
                    f"[{request_id}] Persistence task completed successfully",
                    extra={
                        "request_id": request_id,
                        "execution_time": execution_time,
                        "attempt": attempt,
                        "result": result
                    }
                )

                _trace_log(
                    "persistence_agent",
                    correlation_id=correlation_id,
                    task_id=task_identifier,
                    step="completed",
                    detail="persistence task completed",
                    attempts=attempt + 1,
                    execution_time=execution_time,
                )
                
                return {
                    **result,
                    "metadata": {
                        "request_id": request_id,
                        "execution_time": execution_time,
                        "attempts": attempt + 1,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                
            except Exception as e:
                attempt += 1
                self.error_count += 1
                
                if attempt > self.max_retries:
                    # Final failure
                    execution_time = time.time() - start_time
                    
                    logger.error(
                        f"[{request_id}] Persistence task failed after {attempt} attempts",
                        extra={
                            "request_id": request_id,
                            "error": str(e),
                            "execution_time": execution_time,
                            "attempts": attempt
                        },
                        exc_info=True
                    )

                    _trace_log(
                        "persistence_agent",
                        correlation_id=correlation_id,
                        task_id=task_identifier,
                        step="failed",
                        detail=str(e),
                        attempts=attempt,
                    )
                    
                    return {
                        "status": "error",
                        "error": str(e),
                        "metadata": {
                            "request_id": request_id,
                            "execution_time": execution_time,
                            "attempts": attempt,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                
                # Retry with backoff
                self.retry_count += 1
                
                logger.warning(
                    f"[{request_id}] Persistence task failed, retrying in {backoff}s",
                    extra={
                        "request_id": request_id,
                        "error": str(e),
                        "attempt": attempt,
                        "backoff": backoff
                    }
                )

                _trace_log(
                    "persistence_agent",
                    correlation_id=correlation_id,
                    task_id=task_identifier,
                    step="retrying",
                    detail="retrying persistence task",
                    attempt=attempt,
                    backoff_seconds=backoff,
                )
                
                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)
        
        # Should never reach here
        return {
            "status": "error",
            "error": "Max retries exceeded"
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check harness and agent health.
        
        Returns:
            Health status with metrics
        """
        agent_health = await self.agent.health_check()
        
        return {
            **agent_health,
            "harness": {
                "status": "healthy",
                "metrics": {
                    "request_count": self.request_count,
                    "error_count": self.error_count,
                    "retry_count": self.retry_count,
                    "error_rate": self.error_count / max(self.request_count, 1)
                },
                "config": {
                    "max_retries": self.max_retries,
                    "initial_backoff": self.initial_backoff,
                    "max_backoff": self.max_backoff,
                    "checkpoint_enabled": self.checkpoint_enabled
                }
            }
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current harness metrics.
        
        Returns:
            Metrics dictionary
        """
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "error_rate": self.error_count / max(self.request_count, 1)
        }
