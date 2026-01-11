"""
Outreach Orchestrator with Harness Wrapper

Production-ready wrapper for Outreach Orchestrator with Agent Harness.

Configuration for Outreach (campaign operations):
- Retries on transient failures
- Observability and tracing
- Rate limiting
- Checkpointing for long-running campaigns
"""

import logging
from typing import Any, Dict

from core.harness import AgentHarness, HarnessConfig
from .outreach_orchestrator import OutreachOrchestrator

logger = logging.getLogger(__name__)


class OutreachOrchestratorHarness:
    """
    Production-ready Outreach Orchestrator with harness wrapper.
    
    Configuration for Outreach (campaign operations):
    - 5 retries with jittered backoff (campaigns are valuable)
    - 120 second timeout (copy generation can be slow)
    - Redis checkpointing enabled (resume long campaigns)
    - 500 requests/hour rate limit (protect external APIs)
    - Datadog observability for production
    
    Example:
        # Development
        harness = OutreachOrchestratorHarness(
            redis_client,
            tenant_id="acme",
            environment="development"
        )
        
        result = await harness.execute({
            "goal": "Launch Q4 enterprise outreach campaign",
            "data": {
                "leads": ["lead-123", "lead-456"],
                "channels": ["email", "linkedin", "phone"]
            }
        })
        
        # Production (with full observability)
        harness = OutreachOrchestratorHarness(
            redis_client,
            tenant_id="acme",
            environment="production",
            enable_observability=True,
            enable_checkpointing=True
        )
    """
    
    def __init__(
        self,
        redis_client,
        tenant_id: str,
        environment: str = "development",
        enable_observability: bool = False,
        enable_checkpointing: bool = False,
    ):
        """
        Initialize Outreach Orchestrator with harness.
        
        Args:
            redis_client: Redis client for middleware
            tenant_id: Tenant identifier
            environment: Environment name (development/staging/production)
            enable_observability: Enable Datadog observability
            enable_checkpointing: Enable Redis checkpointing for campaign resumption
        """
        self.tenant_id = tenant_id
        self.environment = environment
        
        # Create orchestrator
        self.orchestrator = OutreachOrchestrator(redis_client, tenant_id)
        
        # Configure harness for Outreach (campaign operations)
        config = HarnessConfig(
            max_retries=5,  # Higher retries for campaigns (valuable work)
            retry_strategy="jittered",  # Jittered to avoid thundering herd with external APIs
            timeout_seconds=120,  # Longer timeout (copy generation can be slow)
            enable_checkpointing=enable_checkpointing,
            checkpoint_backend="redis" if enable_checkpointing else None,
            requests_per_hour=500,  # Conservative limit (protect external APIs)
            quota_backend="redis" if redis_client else "memory",
            observability_backend="datadog" if enable_observability else "simple",
            service_name="agentic-system",
        )
        
        # Create harness
        self.harness = AgentHarness.from_config(
            agent=self.orchestrator,
            config=config,
            redis_client=redis_client,
        )
        
        logger.info(
            f"OutreachOrchestratorHarness initialized: "
            f"tenant={tenant_id}, env={environment}, "
            f"checkpointing={enable_checkpointing}"
        )
    
    async def execute(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task through harness.
        
        Args:
            task_data: Task data with "goal" and optional "data"
        
        Returns:
            Execution result
        
        Example:
            result = await harness.execute({
                "goal": "Launch email campaign",
                "data": {
                    "campaign_id": "camp-123",
                    "leads": ["lead-123", "lead-456"],
                    "channels": ["email", "linkedin"]
                }
            })
        """
        return await self.harness.execute(task_data)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of harness and orchestrator.
        
        Returns:
            Health status dictionary
        """
        return await self.harness.health_check()
    
    def __repr__(self) -> str:
        """String representation"""
        return (
            f"OutreachOrchestratorHarness(tenant={self.tenant_id}, "
            f"env={self.environment})"
        )
