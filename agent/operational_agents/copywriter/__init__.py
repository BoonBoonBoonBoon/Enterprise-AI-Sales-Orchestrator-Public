"""Compatibility re-export for the copywriter operational agent.

This package re-exports the implementation in `copywriter_agent` to support
existing import paths. It is intentionally minimal and can be removed once
all imports are migrated to `copywriter_agent`.
"""

from agent.operational_agents.copywriter_agent.copywriter import CopywriterAgent, generate_email, generate_text

__all__ = ["CopywriterAgent", "generate_email", "generate_text"]
