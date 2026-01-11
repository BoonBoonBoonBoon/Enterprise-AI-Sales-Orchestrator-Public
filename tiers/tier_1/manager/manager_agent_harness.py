"""
Manager Agent Harness Wrapper

Production wrapper for Manager Agent with reliability features.
"""

import logging
import os
from core.harness import AgentHarness, HarnessConfig
from .manager_agent import ManagerAgent

logger = logging.getLogger(__name__)


class ManagerAgentHarness:
    """
    Production wrapper for Manager Agent.
    
    Uses universal harness with Manager-specific configuration:
    - 2 retries (Manager rarely fails - strategic level)
    - 120s timeout (coordination takes time)
    - Checkpointing enabled (multi-step workflows)
    - 2000 req/hr quota (high priority)
    """
    
    def __init__(
        self,
        redis_client,
        tenant_id: str,
        environment: str = "development",
        enable_observability: bool = False,
        enable_checkpointing: bool = True,
    ):
        """
        Initialize Manager harness.
        
        Args:
            redis_client: Redis client for state management
            tenant_id: Tenant identifier
            environment: Environment (development/staging/production)
            enable_observability: Enable Datadog/OpenTelemetry
            enable_checkpointing: Enable state checkpointing
        """
        # Feature flags (env-driven) to allow exercising LLM decision-making in E2E.
        # LLM fallback defaults to ON when an API key is present, unless kill-switched.
        explicit_llm = os.getenv("MANAGER_ENABLE_LLM_FALLBACK")
        if explicit_llm is None:
            llm_kill = os.getenv("MANAGER_LLM_ENABLED", "1").lower() in ("0", "false", "no")
            enable_llm_fallback = bool(os.getenv("OPENAI_API_KEY")) and not llm_kill
        else:
            enable_llm_fallback = explicit_llm.lower() in ("1", "true", "yes")

        enable_deep_agent = os.getenv("MANAGER_ENABLE_DEEP_AGENT", "0").lower() in ("1", "true", "yes")

        # Create base Manager agent
        self.agent = ManagerAgent(
            redis_client=redis_client,
            tenant_id=tenant_id,
            enable_llm_fallback=enable_llm_fallback,
            enable_deep_agent=enable_deep_agent,
        )
        
        # Load configuration based on environment
        if environment == "production":
            config = HarnessConfig.for_production()
            # Customize for Manager
            config.max_retries = 2  # Manager is strategic, rarely fails
            config.timeout_seconds = 120
            config.enable_checkpointing = enable_checkpointing
            config.requests_per_hour = 2000  # High priority
        elif environment == "staging":
            config = HarnessConfig.for_staging()
            config.max_retries = 3
            config.timeout_seconds = 120
            config.enable_checkpointing = enable_checkpointing
            config.requests_per_hour = 1500
        else:  # development
            config = HarnessConfig.for_development()
            config.max_retries = 1
            config.timeout_seconds = 60
            config.enable_checkpointing = False
            config.requests_per_hour = 10000  # No limit for testing
        
        # Create universal harness from config
        self.harness = AgentHarness.from_config(
            agent=self.agent,
            config=config
        )
        
        logger.info(
            f"ManagerAgentHarness initialized: tenant={tenant_id}, "
            f"env={environment}, checkpointing={enable_checkpointing}"
        )
    
    async def execute(self, task_data: dict):
        """
        Execute Manager task through harness.
        
        Args:
            task_data: Task data with goal and parameters
            
        Returns:
            Orchestration result
        """
        return await self.harness.execute(task_data)
    
    async def health_check(self):
        """Check Manager health status"""
        return self.agent.health_check()
