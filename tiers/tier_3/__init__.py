"""
Tier 3: Operational Agents - Specialized task execution layer.

Operational agents are responsible for:
- Specialized task execution
- Individual operations (RAG, persistence, copywriting, etc.)
- Result reporting back to Tier 2
- Isolated processing and error handling

Exported Agents:
- RAGAgent: Information retrieval and semantic search
- PersistenceAgent: Database write operations
- CopywriterAgent: Content generation and copywriting
- (Additional specialized agents can be added here)
"""

__all__ = [
    "rag_agent",
    "persistence_agent",
    "copywriter_agent",
]
