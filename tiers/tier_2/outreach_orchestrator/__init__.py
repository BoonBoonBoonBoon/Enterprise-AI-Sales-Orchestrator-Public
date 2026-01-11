"""
Outreach Orchestrator - Tier 2 Campaign Management

Coordinates outreach campaigns across email, LinkedIn, and phone channels.
Delegates specialized tasks to:
- Copywriter Agent: Content generation
- Persistence Agent: Campaign tracking and lead updates

Built with Deep Agents for intelligent campaign planning and Agent Harness for reliability.

Typical Usage:
    # Production with harness
    from tiers.tier_2.outreach_orchestrator import OutreachOrchestratorHarness
    
    harness = OutreachOrchestratorHarness(
        redis_client,
        tenant_id="acme",
        environment="production",
        enable_observability=True
    )
    
    result = await harness.execute({
        "goal": "Launch Q4 enterprise campaign",
        "data": {"leads": [...], "channels": ["email", "linkedin"]}
    })
    
    # Redis Streams consumer
    from tiers.tier_2.outreach_orchestrator import OutreachConsumer
    consumer = OutreachConsumer(redis_client, tenant_id="acme")
    await consumer.run()
"""

from .outreach_orchestrator import OutreachOrchestrator
from .outreach_orchestrator_harness import OutreachOrchestratorHarness
from .consumer import OutreachConsumer

__all__ = [
    "OutreachOrchestrator",
    "OutreachOrchestratorHarness",
    "OutreachConsumer",
]

