"""Shim queue package for legacy imports.

Provides `QueueInterface` protocol expected by code importing from
`agent.high_level_agents.queue.interface`.
"""

from .interface import QueueInterface  # noqa: F401

__all__ = ["QueueInterface"]
