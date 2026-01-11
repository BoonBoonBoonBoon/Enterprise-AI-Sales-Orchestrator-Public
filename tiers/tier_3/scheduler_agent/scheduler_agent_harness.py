"""Reliability harness for SchedulerAgent with simple retry logic."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from tiers.tier_3.scheduler_agent.scheduler_agent import SchedulerAgent

logger = logging.getLogger(__name__)


class SchedulerAgentHarness:
    """Lightweight harness that retries schedule requests and tracks metadata."""

    def __init__(
        self,
        agent: Optional[SchedulerAgent] = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
    ) -> None:
        self.agent = agent or SchedulerAgent()
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff

    async def execute(
        self, task_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a scheduling task with retries and timing metadata."""
        request_id = (context or {}).get("request_id", "unknown")
        attempt = 0
        backoff = self.initial_backoff
        start_time = time.time()

        while attempt <= self.max_retries:
            try:
                result = self.agent.schedule(task_data)
                if result.get("status") == "error":
                    raise ValueError(result.get("error", "scheduler error"))

                elapsed = time.time() - start_time
                return {
                    **result,
                    "metadata": {
                        "request_id": request_id,
                        "attempts": attempt + 1,
                        "execution_time": elapsed,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }
            except Exception as exc:  # pragma: no cover - logging path
                attempt += 1
                if attempt > self.max_retries:
                    elapsed = time.time() - start_time
                    logger.error(
                        "Scheduler task failed after retries",
                        extra={"request_id": request_id, "error": str(exc)},
                    )
                    return {
                        "status": "error",
                        "error": str(exc),
                        "metadata": {
                            "request_id": request_id,
                            "attempts": attempt,
                            "execution_time": elapsed,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    }

                logger.warning(
                    "Scheduler task failed, retrying",
                    extra={"request_id": request_id, "attempt": attempt, "error": str(exc)},
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)

    async def health_check(self) -> Dict[str, Any]:
        """Return agent health status."""
        return {
            "status": "healthy",
            "agent": "scheduler_agent",
            "config": {
                "max_retries": self.max_retries,
                "initial_backoff": self.initial_backoff,
                "max_backoff": self.max_backoff,
            },
        }
