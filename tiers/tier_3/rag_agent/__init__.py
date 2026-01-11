"""
RAG Agent - Tier 3 Retrieval Augmented Generation

Performs semantic search, document retrieval, and context enrichment using:
- Vector DB integration (Pinecone, Weaviate, etc.)
- External API clients (CrunchBase, LinkedIn)
- LLM-powered reasoning
- Agent Harness for reliability

Typical Usage:
    # Direct agent usage
    from tiers.tier_3.rag_agent import RAGAgent
    
    agent = RAGAgent(
        vector_db_client=...,
        redis_client=...,
        tenant_id="acme"
    )
    
    # Production with harness
    from tiers.tier_3.rag_agent import RAGAgentHarness
    harness = RAGAgentHarness(agent, environment="production")
    
    # Redis Streams consumer
    from tiers.tier_3.rag_agent import RAGConsumer
    consumer = RAGConsumer(redis_client, tenant_id="acme")
    await consumer.run()
"""

from .rag_agent import RAGAgent
from .rag_agent_harness import RAGAgentHarness
from .consumer import RAGConsumer

__all__ = [
    "RAGAgent",
    "RAGAgentHarness",
    "RAGConsumer",
]

