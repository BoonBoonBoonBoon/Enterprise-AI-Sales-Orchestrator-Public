"""Legacy compatibility package.

Provides backward-compatible import paths expected by older tests:
- agent.orchestration_agents.registry -> re-exports Registry from high_level_agents.orchestrators
- agent.orchestration_agents.base_orchestrator -> re-exports BaseOrchestrator

Remove once tests updated to new path: agent.high_level_agents.orchestrators
"""
from agent.high_level_agents.orchestrators.registry import Registry  # noqa: F401
from agent.high_level_agents.orchestrators.base_orchestrator import BaseOrchestrator  # noqa: F401

__all__ = ["Registry", "BaseOrchestrator"]
