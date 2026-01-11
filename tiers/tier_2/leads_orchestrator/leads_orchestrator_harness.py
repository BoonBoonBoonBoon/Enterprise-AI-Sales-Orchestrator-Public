"""
Leads Orchestrator with Harness Wrapper

Production-ready wrapper for Leads Orchestrator with Agent Harness.

This demonstrates how to wrap any orchestrator with the harness
for production reliability features:
- Retries on transient failures
- Observability and tracing
- Rate limiting
"""

import logging
from typing import Any, Dict

from core.harness import AgentHarness, HarnessConfig
from .leads_orchestrator import LeadsOrchestrator

logger = logging.getLogger(__name__)


class LeadsOrchestratorHarness:
    """
    Production-ready Leads Orchestrator with harness wrapper.
    
    Configuration for Leads (fast DB operations):
    - 3 retries with exponential backoff
    - 60 second timeout
    - No checkpointing (fast operations don't need it)
    - 1000 requests/hour rate limit
    - Simple logging for development (upgrade to Datadog for production)
    
    Example:
        # Development
        harness = LeadsOrchestratorHarness(
            redis_client,
            tenant_id="acme",
            environment="development"
        )
        
        result = await harness.execute({
            "goal": "Add new lead from form submission",
            "data": {"name": "John Doe", "email": "john@example.com"}
        })
        
        # Production (with Datadog)
        harness = LeadsOrchestratorHarness(
            redis_client,
            tenant_id="acme",
            environment="production",
            enable_observability=True
        )
    """
    
    def __init__(
        self,
        redis_client,
        tenant_id: str,
        environment: str = "development",
        enable_observability: bool = False,
    ):
        """
        Initialize Leads Orchestrator with harness.
        
        Args:
            redis_client: Redis client for middleware
            tenant_id: Tenant identifier
            environment: Environment name (development/staging/production)
            enable_observability: Enable Datadog observability (production only)
        """
        self.tenant_id = tenant_id
        self.environment = environment
        
        # Create orchestrator
        self.orchestrator = LeadsOrchestrator(redis_client, tenant_id)
        
        # Configure harness for Leads (fast DB operations)
        config = HarnessConfig(
            max_retries=3,
            retry_strategy="exponential",
            timeout_seconds=60,
            enable_checkpointing=False,  # Fast ops don't need checkpointing
            requests_per_hour=1000,
            quota_backend="memory",
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
            f"LeadsOrchestratorHarness initialized: "
            f"tenant={tenant_id}, env={environment}"
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
                "goal": "Add new lead",
                "data": {"name": "John", "email": "john@example.com"}
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
            f"LeadsOrchestratorHarness(tenant={self.tenant_id}, "
            f"env={self.environment})"
        )
