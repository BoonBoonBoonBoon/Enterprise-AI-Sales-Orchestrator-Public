"""
Tier 1: Manager - Strategic orchestration layer.

The Manager is responsible for:
- Receiving requests from external sources
- Strategic decision making and delegation
- Coordinating with Tier 2 orchestrators
- System-level monitoring and health checks

Exported Components:
- ManagerAgent: Core manager agent implementation
- ManagerAgentHarness: Manager harness with retry/observability
- manager consumer: Redis Streams consumer for manager tasks
"""

__all__ = [
    "manager",
]
