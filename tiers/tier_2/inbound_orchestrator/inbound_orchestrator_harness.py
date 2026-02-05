"""
Inbound Orchestrator Harness

Wraps the InboundOrchestrator with Redis Streams consumer pattern for
Tier-2 operation.

Listens on: {tenant}:orchestrators:inbound:tasks
Publishes to: {tenant}:orchestrators:inbound:results
"""

import logging
from typing import Any, Dict, Optional
from .inbound_orchestrator import InboundOrchestrator

logger = logging.getLogger(__name__)


class InboundOrchestratorHarness:
    """Execution wrapper for `InboundOrchestrator` used by its consumer."""

    def __init__(self, tenant_id: str = "agentic-dev", config: Optional[Dict[str, Any]] = None):
        self.tenant_id = tenant_id
        self.config = config or {}
        self.orchestrator = InboundOrchestrator(tenant_id=tenant_id, config=config)
        logger.info("InboundOrchestratorHarness initialized (tenant=%s)", tenant_id)

    async def execute(self, task_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute an inbound orchestrator task.

        Manager publishes typed envelopes where the envelope payload includes a nested
        `payload` (the original request payload). For backward compatibility with the
        orchestrator's existing expectations, we adapt into a minimal dict containing
        `payload` and `metadata.task_id`.
        """
        meta = context or {}
        adapted = {
            "payload": (task_data or {}).get("payload", {}) if isinstance(task_data, dict) else {},
            "metadata": {
                "task_id": meta.get("task_id"),
                "correlation_id": meta.get("correlation_id"),
            },
        }
        return self.orchestrator.process_task(adapted)
