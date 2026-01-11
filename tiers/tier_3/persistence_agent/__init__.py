"""
Persistence Agent - Tier 3 Data Storage

Handles all database write and read operations with:
- Agent Harness for production reliability
- Redis Streams for async task processing
- Configurable persistence adapters (Supabase, PostgreSQL, etc.)
- Write allowlist for security

Typical Usage:
    # Direct agent usage
    from tiers.tier_3.persistence_agent import PersistenceAgent
    from services.persistence import PersistenceService
    
    service = PersistenceService(adapter=...)
    agent = PersistenceAgent(service=service)
    
    # Production with harness
    from tiers.tier_3.persistence_agent import PersistenceAgentHarness
    harness = PersistenceAgentHarness(agent)
    
    # Redis Streams consumer
    from tiers.tier_3.persistence_agent import PersistenceAgentConsumer
    consumer = PersistenceAgentConsumer(redis_client, tenant_id="acme")
    await consumer.run()
"""

from .persistence_agent import PersistenceAgent
from .persistence_agent_harness import PersistenceAgentHarness
from .consumer import PersistenceAgentConsumer

__all__ = [
    "PersistenceAgent",
    "PersistenceAgentHarness",
    "PersistenceAgentConsumer",
]
