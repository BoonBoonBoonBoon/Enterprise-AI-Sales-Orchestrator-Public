"""
Manager Agent Package - Tier 1 Strategic AI

This package provides the top-level strategic decision-making layer:
- ManagerAgent: Deep Agent with delegation tools
- ManagerAgentHarness: Production-ready wrapper with retry logic
- ManagerConsumer: Redis Streams consumer for async task processing
- ShortcutRegistry: Fast-path optimizations for simple operations

Typical Usage:
    # Direct agent usage
    from tiers.tier_1.manager import ManagerAgent
    manager = ManagerAgent(redis_client, tenant_id="acme")
    result = manager.execute("Find leads in the tech industry")
    
    # Production with harness
    from tiers.tier_1.manager import ManagerAgentHarness
    harness = ManagerAgentHarness(redis_client, "acme", environment="production")
    result = await harness.execute(task_data)
    
    # Redis Streams consumer
    from tiers.tier_1.manager import ManagerConsumer
    consumer = ManagerConsumer(redis_client, tenant_id="acme")
    await consumer.run()
"""

from .manager_agent import ManagerAgent
from .manager_agent_harness import ManagerAgentHarness
from .consumer import ManagerConsumer
from .shortcut_registry import ShortcutRegistry

__all__ = [
    "ManagerAgent",
    "ManagerAgentHarness",
    "ManagerConsumer",
    "ShortcutRegistry",
]

