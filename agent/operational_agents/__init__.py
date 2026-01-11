"""Operational agents package.

Provides a small discovery helper so agents can be discovered at runtime
without hard-coded imports. Use `discover_local_agents()` to get a mapping
of local agent names to their Agent class or factory.
"""

__all__ = ["rag_agent", "registry"]
