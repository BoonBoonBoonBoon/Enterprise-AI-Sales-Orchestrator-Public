"""Legacy shim for BaseOrchestrator.

Allows imports like `from agent.orchestration_agents.base_orchestrator import BaseOrchestrator`.
"""
from agent.high_level_agents.orchestrators.base_orchestrator import BaseOrchestrator  # noqa: F401

__all__ = ["BaseOrchestrator"]
