"""Synchronous worker wrapper for SchedulerAgent."""
from __future__ import annotations

from typing import Dict, Any

from tiers.tier_3.scheduler_agent.scheduler_agent import SchedulerAgent


def execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    agent = SchedulerAgent()
    return agent.execute(payload)
