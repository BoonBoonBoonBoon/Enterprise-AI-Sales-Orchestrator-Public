"""
Copywriter Agent - Tier 3 Content Generation

Generates personalized outreach content including:
- Subject lines
- Email body variations
- A/B test variants
- Personalization based on lead context

Built with OpenAI API and Redis caching for performance.

Typical Usage:
    # Direct agent usage
    from tiers.tier_3.copywriter_agent import CopywriterAgent
    
    agent = CopywriterAgent(openai_client=..., redis_client=...)
    
    # Generate email
    from tiers.tier_3.copywriter_agent import generate_email
    email = await generate_email(
        lead_id="lead_123",
        lead_context={"name": "John", "company": "TechCorp"},
        campaign_id="campaign_456"
    )
    
    # Production with harness
    from tiers.tier_3.copywriter_agent import CopywriterAgentHarness
    harness = CopywriterAgentHarness(agent, environment="production")
    
    # Redis Streams consumer
    from tiers.tier_3.copywriter_agent import CopywriterAgentConsumer
    consumer = CopywriterAgentConsumer(redis_client, tenant_id="acme")
    await consumer.run()
"""

from .copywriter import CopywriterAgent, generate_email, generate_text
from .copywriter_agent_harness import CopywriterAgentHarness
from .consumer import CopywriterAgentConsumer

__all__ = [
    "CopywriterAgent",
    "CopywriterAgentHarness",
    "CopywriterAgentConsumer",
    "generate_email",
    "generate_text",
]

