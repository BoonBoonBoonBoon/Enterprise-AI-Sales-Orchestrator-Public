"""
Core Agent Harness: Universal Production Wrapper

Wraps any agent/orchestrator with production reliability features.
Orchestrates pluggable components:
- Retry strategy
- Observability system
- Checkpointing system
- Quota manager

The harness handles the orchestration; actual implementations are pluggable.
"""

import uuid
import asyncio
import logging
from typing import Any, Optional
from datetime import datetime

from core.observability.metrics import MetricsCollector

from .interfaces import (
    IRetryStrategy,
    IObservability,
    ICheckpointer,
    IQuotaManager,
    QuotaExceededError,
    CheckpointError,
)
from .config import HarnessConfig

# Import all implementations for factory method
from .retry_strategies import (
    ExponentialBackoffRetry,
    LinearBackoffRetry,
    JitteredBackoffRetry,
)
from .observability import (
    SimpleLoggingObservability,
    OpenTelemetryObservability,
    DatadogObservability,
)
# Note: checkpointers are imported lazily inside `from_config` to avoid
# importing optional heavy dependencies (e.g., boto3) on startup.
from .quota_management import (
    RedisTokenBucket,
    InMemoryQuota,
)

logger = logging.getLogger(__name__)


class AgentHarness:
    """
    Universal production wrapper for any agent/orchestrator.
    
    Provides:
    - Automatic retries with configurable backoff
    - Distributed tracing and observability
    - Execution state checkpointing (for resumption)
    - Rate limiting and quota enforcement
    
    All components are pluggable and swappable.
    
    Example:
        from agent.harness import AgentHarness, HarnessConfig
        
        orchestrator = LeadsOrchestrator(redis, "tenant1")
        harness = AgentHarness(
            orchestrator,
            config=HarnessConfig.for_production()
        )
        
        result = await harness.execute({"lead_id": "123"})
    """
    
    def __init__(
        self,
        agent: Any,
        config: Optional[HarnessConfig] = None,
        retry_strategy: Optional[IRetryStrategy] = None,
        observability: Optional[IObservability] = None,
        checkpointer: Optional[ICheckpointer] = None,
        quota_manager: Optional[IQuotaManager] = None,
    ):
        """
        Initialize harness with agent and optional components.
        
        Args:
            agent: Agent/orchestrator to wrap (must have execute() method)
            config: HarnessConfig object (if provided, used to configure defaults)
            retry_strategy: IRetryStrategy implementation (optional)
            observability: IObservability implementation (optional)
            checkpointer: ICheckpointer implementation (optional)
            quota_manager: IQuotaManager implementation (optional)
        
        Note:
            If components provided directly, they override config.
            If config provided but components not, defaults are used (minimal).
        """
        self.agent = agent
        self.config = config or HarnessConfig()
        
        # Store timeout
        self.timeout_seconds = self.config.timeout_seconds
        
        # Store optional components (user can inject custom implementations)
        self.retry_strategy = retry_strategy
        self.observability = observability
        self.checkpointer = checkpointer
        self.quota_manager = quota_manager
        
        logger.info(
            f"AgentHarness initialized for {agent.__class__.__name__}: "
            f"retries={config.max_retries if config else 0}, "
            f"timeout={self.timeout_seconds}s"
        )
    
    @classmethod
    def from_config(
        cls,
        agent: Any,
        config: HarnessConfig,
        redis_client=None,
        s3_bucket_name: Optional[str] = None,
        postgres_connection_string: Optional[str] = None,
    ) -> "AgentHarness":
        """
        Factory method to create harness from configuration.
        
        Instantiates all components based on HarnessConfig settings.
        
        Args:
            agent: Agent/orchestrator to wrap
            config: HarnessConfig object
            redis_client: Redis client (required if using Redis checkpointer or quota)
            s3_bucket_name: S3 bucket name (required if using S3 checkpointer)
            postgres_connection_string: PostgreSQL connection string (required if using PostgreSQL checkpointer)
        
        Returns:
            Configured AgentHarness instance
        
        Example:
            config = HarnessConfig.for_production()
            harness = AgentHarness.from_config(
                orchestrator,
                config,
                redis_client=redis_client,
                s3_bucket_name="prod-checkpoints"
            )
        """
        # 1. Instantiate retry strategy
        retry_strategy = None
        if config.max_retries > 0:
            if config.retry_strategy == "exponential":
                retry_strategy = ExponentialBackoffRetry(
                    max_retries=config.max_retries,
                    base_delay=1.0,
                    max_delay=60.0,
                )
            elif config.retry_strategy == "linear":
                retry_strategy = LinearBackoffRetry(
                    max_retries=config.max_retries,
                    base_delay=2.0,
                    increment=2.0,
                )
            elif config.retry_strategy == "jittered":
                retry_strategy = JitteredBackoffRetry(
                    max_retries=config.max_retries,
                    base_delay=1.0,
                    max_delay=60.0,
                    jitter_factor=0.3,
                )
            else:
                logger.warning(
                    f"Unknown retry strategy: {config.retry_strategy}. "
                    f"Using exponential as default."
                )
                retry_strategy = ExponentialBackoffRetry(
                    max_retries=config.max_retries
                )
        
        # 2. Instantiate observability backend
        observability = None
        if config.observability_backend == "simple":
            observability = SimpleLoggingObservability()
        elif config.observability_backend == "grafana":
            from .observability.grafana_stack import GrafanaStackObservability
            # Infer tier from service name or default to "agent"
            tier = "agent"
            if hasattr(agent, "tier"):
                tier = agent.tier
            component = getattr(agent, "name", config.service_name)
            observability = GrafanaStackObservability(
                tier=tier,
                component=component,
                tenant_id=getattr(agent, "tenant_id", "default"),
            )
        elif config.observability_backend == "opentelemetry":
            try:
                observability = OpenTelemetryObservability(
                    service_name=config.service_name
                )
            except ImportError as e:
                logger.warning(
                    f"OpenTelemetry not available, falling back to simple: {e}"
                )
                observability = SimpleLoggingObservability()
        elif config.observability_backend == "datadog":
            try:
                observability = DatadogObservability(
                    service_name=config.service_name,
                    env=config.environment
                )
            except ImportError as e:
                logger.warning(
                    f"Datadog not available, falling back to simple: {e}"
                )
                observability = SimpleLoggingObservability()
        else:
            logger.info(
                f"No observability backend specified or unknown: {config.observability_backend}"
            )
            observability = SimpleLoggingObservability()
        
        # 3. Instantiate checkpointer (if enabled)
        checkpointer = None
        if config.enable_checkpointing:
            if config.checkpoint_backend == "redis":
                if not redis_client:
                    logger.error(
                        "Redis checkpointer requested but no redis_client provided"
                    )
                else:
                    from .checkpointing.redis_checkpointer import RedisCheckpointer

                    checkpointer = RedisCheckpointer(
                        redis_client,
                        ttl_seconds=86400,  # 24 hours
                        key_prefix="checkpoint:"
                    )
            elif config.checkpoint_backend == "s3":
                if not s3_bucket_name:
                    logger.error(
                        "S3 checkpointer requested but no s3_bucket_name provided"
                    )
                else:
                    try:
                        from .checkpointing.s3_checkpointer import S3Checkpointer

                        checkpointer = S3Checkpointer(
                            bucket_name=s3_bucket_name,
                            prefix="checkpoints/",
                            region="us-east-1"
                        )
                    except ImportError as e:
                        logger.error(f"S3 checkpointer not available: {e}")
            elif config.checkpoint_backend == "postgresql":
                if not postgres_connection_string:
                    logger.error(
                        "PostgreSQL checkpointer requested but no connection string provided"
                    )
                else:
                    try:
                        from .checkpointing.postgres_checkpointer import PostgreSQLCheckpointer

                        checkpointer = PostgreSQLCheckpointer(
                            connection_string=postgres_connection_string
                        )
                    except ImportError as e:
                        logger.error(f"PostgreSQL checkpointer not available: {e}")
            else:
                logger.warning(
                    f"Unknown checkpoint backend: {config.checkpoint_backend}"
                )
        
        # 4. Instantiate quota manager (if enabled)
        quota_manager = None
        if config.requests_per_hour and config.requests_per_hour > 0:
            if config.quota_backend == "redis":
                if not redis_client:
                    logger.error(
                        "Redis quota manager requested but no redis_client provided"
                    )
                else:
                    # RedisTokenBucket expects a raw redis-py client (supports register_script, hmget, etc).
                    # Our app often passes RedisStreamsClient (services.redis.client.RedisStreamsClient)
                    # which wraps the underlying redis client on `.client`.
                    redis_for_quota = getattr(redis_client, "client", redis_client)
                    quota_manager = RedisTokenBucket(
                        redis_for_quota,
                        capacity=100,  # burst size
                        refill_rate=config.requests_per_hour / 3600,  # per second
                        key_prefix="quota:",
                        cost_per_execution=1
                    )
            elif config.quota_backend == "memory":
                quota_manager = InMemoryQuota(
                    requests_per_hour=config.requests_per_hour,
                    window_seconds=3600
                )
            else:
                logger.warning(
                    f"Unknown quota backend: {config.quota_backend}. Using in-memory."
                )
                quota_manager = InMemoryQuota(
                    requests_per_hour=config.requests_per_hour
                )
        
        # 5. Create harness with all components
        return cls(
            agent=agent,
            config=config,
            retry_strategy=retry_strategy,
            observability=observability,
            checkpointer=checkpointer,
            quota_manager=quota_manager,
        )
    
    async def execute(
        self,
        task_data: Any,
        execution_id: Optional[str] = None
    ) -> Any:
        """
        Execute task with production features.
        
        Flow:
        1. Generate execution ID
        2. Check quota (if enabled)
        3. Load checkpoint (if exists, resume)
        4. Start tracing span
        5. Execute agent with retries
        6. Save checkpoint (if enabled)
        7. Return result
        
        Args:
            task_data: Task data to execute
            execution_id: Optional execution ID (generated if not provided)
        
        Returns:
            Result from agent execution
        
        Raises:
            QuotaExceededError: If quota limit exceeded
            Exception: If all retries exhausted or execution fails
        """
        # 1. Generate execution ID
        execution_id = execution_id or f"exec_{uuid.uuid4()}"
        start_time = datetime.now()

        # Prometheus metrics (emitted regardless of harness backend)
        metrics = MetricsCollector.get_instance()
        component = getattr(self.agent, "name", None) or self.config.service_name or self.agent.__class__.__name__
        tenant_id = getattr(self.agent, "tenant_id", "default")

        tier = getattr(self.agent, "tier", None)
        if not tier:
            agent_name = self.agent.__class__.__name__.lower()
            if "orchestrator" in agent_name:
                tier = "orchestrator"
            elif "manager" in agent_name:
                tier = "manager"
            else:
                tier = "agent"
        
        logger.info(
            f"[{execution_id}] Starting execution on {self.agent.__class__.__name__}"
        )
        
        try:
            # 2. Check quota
            if self.quota_manager:
                if not await self.quota_manager.can_execute(self.agent):
                    error_msg = (
                        f"Quota exceeded for {self.agent.__class__.__name__}"
                    )
                    logger.error(f"[{execution_id}] {error_msg}")
                    raise QuotaExceededError(error_msg)
            
            # 3. Load checkpoint (resume if exists)
            if self.checkpointer:
                try:
                    checkpoint = await self.checkpointer.load(execution_id)
                    if checkpoint:
                        logger.info(
                            f"[{execution_id}] Resuming from checkpoint"
                        )
                        task_data = checkpoint.get("task_data", task_data)
                except Exception as e:
                    logger.warning(
                        f"[{execution_id}] Failed to load checkpoint: {e}"
                    )
                    # Continue anyway (checkpoint is optional)
            
            # 4. Start tracing
            if self.observability:
                span_ctx = self.observability.start_span(
                    f"{self.agent.__class__.__name__}.execute"
                )
            else:
                span_ctx = self._null_context_manager()
            
            with span_ctx as span:
                # Set span attributes if span exists
                if span and hasattr(span, "set_attribute"):
                    span.set_attribute("execution_id", execution_id)
                    span.set_attribute(
                        "agent_type",
                        self.agent.__class__.__name__
                    )
                
                try:
                    # 5. Execute with retries
                    if self.retry_strategy:
                        result = await self.retry_strategy.execute_with_retry(
                            func=self.agent.execute,
                            args=(task_data,),
                            execution_id=execution_id
                        )
                    else:
                        # No retry strategy, execute directly
                        result = await self._execute_agent(
                            self.agent.execute,
                            task_data
                        )
                    
                    # 6. Save checkpoint (success state)
                    if self.checkpointer:
                        try:
                            await self.checkpointer.save(
                                execution_id,
                                {
                                    "task_data": task_data,
                                    "result": result,
                                    "status": "completed",
                                    "completed_at": datetime.now().isoformat()
                                }
                            )
                        except Exception as e:
                            logger.warning(
                                f"[{execution_id}] Failed to save checkpoint: {e}"
                            )
                    
                    # Record success
                    elapsed_ms = (
                        (datetime.now() - start_time).total_seconds() * 1000
                    )
                    logger.info(
                        f"[{execution_id}] Success in {elapsed_ms:.2f}ms"
                    )

                    metrics.histogram(
                        f"{tier}.latency_ms",
                        elapsed_ms,
                        tags={"component": component, "tenant": tenant_id},
                    )
                    
                    if self.observability:
                        self.observability.record_metric(
                            "agent.execution.success",
                            1.0,
                            {
                                "agent": self.agent.__class__.__name__,
                                "execution_id": execution_id
                            }
                        )
                    
                    return result
                    
                except Exception as e:
                    # Record failure
                    elapsed_ms = (
                        (datetime.now() - start_time).total_seconds() * 1000
                    )
                    logger.error(
                        f"[{execution_id}] Failed after {elapsed_ms:.2f}ms: {e}"
                    )

                    metrics.increment(
                        f"{tier}.errors.total",
                        tags={"component": component, "tenant": tenant_id},
                    )
                    metrics.histogram(
                        f"{tier}.latency_ms",
                        elapsed_ms,
                        tags={"component": component, "tenant": tenant_id},
                    )
                    
                    if self.observability:
                        self.observability.record_metric(
                            "agent.execution.failure",
                            1.0,
                            {
                                "agent": self.agent.__class__.__name__,
                                "error_type": type(e).__name__,
                                "execution_id": execution_id
                            }
                        )
                        self.observability.log_event(
                            "ERROR",
                            f"Execution failed: {type(e).__name__}",
                            {
                                "execution_id": execution_id,
                                "agent": self.agent.__class__.__name__,
                                "error": str(e),
                                "elapsed_ms": elapsed_ms
                            }
                        )
                    
                    raise
        
        except Exception as e:
            logger.error(
                f"[{execution_id}] Execution failed: {type(e).__name__}: {e}"
            )
            raise
    
    async def health_check(self) -> dict:
        """
        Check health of harness and wrapped agent.
        
        Returns:
            Health status dict
        """
        health = {
            "status": "healthy",
            "harness": {
                "timestamp": datetime.now().isoformat(),
                "agent": self.agent.__class__.__name__,
                "timeout_seconds": self.timeout_seconds,
            },
            "components": {}
        }
        
        # Check agent health (if it has health_check method)
        if hasattr(self.agent, "health_check"):
            try:
                agent_health = (
                    await self.agent.health_check()
                    if asyncio.iscoroutinefunction(self.agent.health_check)
                    else self.agent.health_check()
                )
                health["components"]["agent"] = agent_health
            except Exception as e:
                health["components"]["agent"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health["status"] = "degraded"
        
        # Check components
        if self.retry_strategy:
            health["components"]["retry_strategy"] = {
                "status": "healthy",
                "type": self.retry_strategy.__class__.__name__
            }
        
        if self.observability:
            health["components"]["observability"] = {
                "status": "healthy",
                "type": self.observability.__class__.__name__
            }
        
        if self.checkpointer:
            health["components"]["checkpointer"] = {
                "status": "healthy",
                "type": self.checkpointer.__class__.__name__
            }
        
        if self.quota_manager:
            health["components"]["quota_manager"] = {
                "status": "healthy",
                "type": self.quota_manager.__class__.__name__
            }
        
        return health
    
    # ==================== Private Helpers ====================
    
    @staticmethod
    async def _execute_agent(func, *args, **kwargs) -> Any:
        """Execute function (sync or async)"""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    @staticmethod
    def _null_context_manager():
        """Context manager that does nothing (for when observability is None)"""
        from contextlib import contextmanager
        
        @contextmanager
        def null_ctx():
            yield None
        
        return null_ctx()


# Exception for quota exceeded
__all__ = [
    "AgentHarness",
]
