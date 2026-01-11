"""
RAG Agent Harness Wrapper

Production wrapper for RAG Agent with reliability features.
Provides retry logic, observability, checkpointing, and quota management.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any
from core.harness import AgentHarness, HarnessConfig
from .rag_agent import RAGAgent

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


class RAGAgentHarness:
    """
    Production wrapper for RAG Agent.
    
    Configuration:
    - 3 retries (external APIs can be flaky)
    - 90s timeout (vector search + API calls take time)
    - Redis checkpointing (enrichment can be expensive, save progress)
    - 500 req/hr quota (respect external API rate limits)
    """
    
    def __init__(
        self,
        redis_client,
        tenant_id: str = "default",
        environment: str = "development",
        enable_observability: bool = False,
        enable_checkpointing: bool = True,
    ):
        """
        Initialize RAG Agent harness.
        
        Args:
            redis_client: Redis client for state management and caching
            tenant_id: Tenant identifier
            environment: Environment (development/staging/production)
            enable_observability: Enable Datadog/OpenTelemetry
            enable_checkpointing: Enable state checkpointing
        """
        # Create base RAG agent
        self.agent = RAGAgent(
            redis_client=redis_client,
            tenant_id=tenant_id
        )
        
        # Load configuration based on environment
        if environment == "production":
            config = HarnessConfig.for_production()
            # Customize for RAG Agent
            config.max_retries = 3  # External APIs can fail
            config.timeout_seconds = 90  # Vector search + API calls
            config.enable_checkpointing = enable_checkpointing
            config.checkpoint_backend = "redis"  # Fast for enrichment caching
            config.requests_per_hour = 500  # Respect external API limits
        elif environment == "staging":
            config = HarnessConfig.for_staging()
            config.max_retries = 2
            config.timeout_seconds = 90
            config.enable_checkpointing = enable_checkpointing
            config.requests_per_hour = 1000
        else:  # development
            config = HarnessConfig.for_development()
            config.max_retries = 1
            config.timeout_seconds = 60
            config.enable_checkpointing = False  # Faster iteration
            config.requests_per_hour = 10000  # No limit for testing
        
        # Create universal harness from config
        self.harness = AgentHarness.from_config(
            agent=self.agent,
            config=config
        )
        
        logger.info(
            f"RAGAgentHarness initialized: tenant={tenant_id}, "
            f"env={environment}, checkpointing={enable_checkpointing}"
        )
    
    async def execute(self, task_data: dict) -> Dict[str, Any]:
        """
        Execute RAG task through harness.
        
        Args:
            task_data: Task data with goal and parameters
            
        Returns:
            Enrichment result with confidence scores
        """
        correlation_id = str(
            (task_data or {}).get("correlation_id")
            or (task_data or {}).get("task_id")
            or "rag"
        )
        task_identifier = str((task_data or {}).get("task_id") or "rag-execute")

        _trace_log(
            "rag_agent",
            correlation_id=correlation_id,
            task_id=task_identifier,
            step="received",
            detail="rag task received",
        )

        try:
            result = await self.harness.execute(task_data)
            _trace_log(
                "rag_agent",
                correlation_id=correlation_id,
                task_id=task_identifier,
                step="completed",
                detail="rag task completed",
                status=result.get("status"),
            )
            return result
        except Exception as exc:
            _trace_log(
                "rag_agent",
                correlation_id=correlation_id,
                task_id=task_identifier,
                step="failed",
                detail=str(exc),
            )
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Check RAG Agent health status"""
        return self.agent.health_check()
