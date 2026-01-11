"""
Core framework components for the Agentic System.

This package contains the fundamental infrastructure that powers the three-tier architecture:
- Harness: Agent execution framework with retry, observability, and checkpointing
- Envelope: Typed message envelope system for agent-to-agent communication
- Deep Agents: Deep agent framework integration (optional)
"""

__all__ = [
    "harness",
    "envelope",
    "deep_agents",
]
