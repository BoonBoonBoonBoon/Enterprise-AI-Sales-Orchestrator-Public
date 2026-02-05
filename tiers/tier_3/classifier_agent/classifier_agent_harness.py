"""Classifier Agent Harness.

This repo's Redis Streams consumption is implemented by dedicated `consumer.py`
modules (see `tiers/tier_2/leads_orchestrator/consumer.py`, etc).

The `core.harness.AgentHarness` is a *universal execution reliability wrapper*,
not a Redis Streams consumer base class.

So this harness is a lightweight execution wrapper used by the classifier
consumer.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .classifier_agent import ClassifierAgent

logger = logging.getLogger(__name__)


class ClassifierAgentHarness:
    """Execution wrapper for `ClassifierAgent`."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.agent = ClassifierAgent(
            llm_enabled=self.config.get(
                "llm_enabled",
                os.getenv("CLASSIFIER_LLM_ENABLED", "0").lower() in ("1", "true", "yes"),
            )
        )
        logger.info("ClassifierAgentHarness initialized")

    async def execute(self, task_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a classification request.

        Accepts either:
        - a full task-like dict with `payload.context.email_event`, OR
        - an envelope payload dict with `context.email_event`.
        """
        if isinstance(task_data, dict) and isinstance(task_data.get("payload"), dict) and isinstance(task_data["payload"].get("context"), dict):
            task = task_data
        else:
            task = {"payload": task_data}
        return self.agent.process_task(task)
