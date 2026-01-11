"""
Leads Orchestrator - Tier 2 Business Logic

Handles all lead-related workflows by coordinating between:
- Deterministic tools (validate, query, write)
- Subagents (RAG for enrichment, Persistence for storage)
- Multiple information sources (CrunchBase, LinkedIn, custom APIs)

Built with Deep Agents for intelligent planning and Agent Harness for reliability.

Typical Usage:
    # Direct orchestrator
    from tiers.tier_2.leads_orchestrator import LeadsOrchestrator
    orchestrator = LeadsOrchestrator(redis_client, tenant_id="acme")
    
    # Production with harness
    from tiers.tier_2.leads_orchestrator import LeadsOrchestratorHarness
    harness = LeadsOrchestratorHarness(redis_client, "acme", environment="production")
    
    # Redis Streams consumer
    from tiers.tier_2.leads_orchestrator import LeadsConsumer
    consumer = LeadsConsumer(redis_client, tenant_id="acme")
    await consumer.run()
"""

from .leads_orchestrator import LeadsOrchestrator
from .leads_orchestrator_harness import LeadsOrchestratorHarness
from .consumer import LeadsConsumer

__all__ = [
    "LeadsOrchestrator",
    "LeadsOrchestratorHarness",
    "LeadsConsumer",
]

