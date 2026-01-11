"""Legacy shim for Registry.

Allows imports like `from agent.orchestration_agents.registry import Registry` to
continue working by delegating to the new location.
"""
from agent.high_level_agents.orchestrators.registry import Registry  # noqa: F401

__all__ = ["Registry"]
