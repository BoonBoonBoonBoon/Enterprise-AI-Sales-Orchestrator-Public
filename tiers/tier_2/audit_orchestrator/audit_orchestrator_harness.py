"""
Audit Orchestrator Harness

Wraps the AuditOrchestrator with the standard harness framework for
retry logic, checkpointing, and observability.
"""

import logging
from typing import Any, Dict, Optional

try:
    from core.harness import AgentHarness, HarnessConfig
except ImportError:
    AgentHarness = None
    HarnessConfig = None

try:
    from core.envelope import Envelope
except ImportError:
    Envelope = None

from .audit_orchestrator import AuditOrchestrator

logger = logging.getLogger(__name__)


class AuditOrchestratorHarness:
    """
    Harness wrapper for AuditOrchestrator.
    
    Provides standard harness capabilities:
    - Retry strategies
    - State checkpointing
    - Observability/tracing
    - Error handling
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the harness.
        
        Args:
            config: Optional harness configuration
        """
        self.config = config or {}
        self.orchestrator = AuditOrchestrator(config)
        
        # Initialize harness with default config
        harness_config = HarnessConfig(
            max_retries=3,
            retry_delay=1.0,
            enable_checkpointing=True,
            enable_tracing=True
        )
        
        self.harness = AgentHarness(
            agent=self.orchestrator,
            config=harness_config
        )
        
        logger.info("AuditOrchestratorHarness initialized")

    async def execute(self, envelope: Envelope) -> Envelope:
        """
        Execute audit task with harness capabilities.
        
        Args:
            envelope: Task envelope
            
        Returns:
            Result envelope
        """
        return await self.harness.execute(envelope)
