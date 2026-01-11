"""Factory functions for creating Tier 3 operational agents.

Provides convenience functions to instantiate agents with proper configuration.
"""
import os
from typing import Any, Optional


def create_rag_agent(**kwargs) -> Any:
    """Create a RAG agent instance.
    
    Args:
        **kwargs: Configuration options passed to RAGAgent constructor.
        
    Returns:
        RAGAgent instance
    """
    # Backward compatibility: older callers pass kind='supabase'/'memory'.
    # The current Tier-3 RAGAgent constructor does not accept this, so we ignore it.
    kwargs.pop("kind", None)

    from tiers.tier_3.rag_agent.rag_agent import RAGAgent

    redis_client = kwargs.pop("redis_client", None)
    tenant_id = kwargs.pop("tenant_id", os.getenv("TENANT_ID", "default"))
    model = kwargs.pop("model", "gpt-4o-mini")

    if redis_client is None:
        import redis  # type: ignore

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

    return RAGAgent(redis_client=redis_client, tenant_id=tenant_id, model=model)


def create_persistence_agent(**kwargs) -> Any:
    """Create a Persistence agent instance.
    
    Args:
        **kwargs: Configuration options passed to PersistenceAgent constructor.
        
    Returns:
        PersistenceAgent instance
    """
    from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent
    return PersistenceAgent(**kwargs)


def create_copywriter_agent(**kwargs) -> Any:
    """Create a Copywriter agent instance.
    
    Args:
        **kwargs: Configuration options passed to CopywriterAgent constructor.
        
    Returns:
        CopywriterAgent instance
    """
    from tiers.tier_3.copywriter_agent.copywriter_agent import CopywriterAgent
    return CopywriterAgent(**kwargs)


# Convenience aliases
AGENT_FACTORIES = {
    "rag": create_rag_agent,
    "persistence": create_persistence_agent,
    "copywriter": create_copywriter_agent,
}


def create_agent(agent_type: str, **kwargs) -> Any:
    """Create an agent by type name.
    
    Args:
        agent_type: One of 'rag', 'persistence', 'copywriter'
        **kwargs: Configuration passed to the agent constructor
        
    Returns:
        Agent instance
        
    Raises:
        ValueError: If agent_type is not recognized
    """
    factory = AGENT_FACTORIES.get(agent_type.lower())
    if not factory:
        raise ValueError(f"Unknown agent type: {agent_type}. Valid types: {list(AGENT_FACTORIES.keys())}")
    return factory(**kwargs)
