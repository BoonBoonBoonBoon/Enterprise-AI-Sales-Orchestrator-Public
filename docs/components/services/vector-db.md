# Vector Database

The Vector DB service provides vector similarity search for semantic retrieval.

!!! warning "Status: Planned"
Vector DB integration is planned but not yet fully implemented.
See [Roadmap](../../roadmap/in-progress.md) for current status.

## Overview

| Component    | Description                         |
| ------------ | ----------------------------------- |
| **Location** | `services/vector_db/`               |
| **Purpose**  | Semantic search, embeddings storage |
| **Used By**  | RAGAgent (planned)                  |

## Planned Features

- **Embedding Generation** — Convert text to vectors
- **Similarity Search** — Find semantically similar content
- **Hybrid Search** — Combine keyword and semantic search
- **Collection Management** — Tenant-scoped collections

## Supported Backends

| Backend  | Status         |
| -------- | -------------- |
| ChromaDB | 🚧 In Progress |
| Qdrant   | 📋 Planned     |
| Pinecone | 📋 Planned     |

## Planned API

### Embedding

```python
from services.vector_db.client import VectorDBClient

client = VectorDBClient()

# Generate and store embedding
doc_id = await client.embed_and_store(
    collection="leads",
    document_id="lead-123",
    text="John Doe is a CTO at Acme Inc focusing on AI automation",
    metadata={"lead_id": "lead-123", "type": "profile"}
)
```

### Search

```python
# Semantic search
results = await client.search(
    collection="leads",
    query="enterprise software decision maker",
    limit=5,
    threshold=0.7
)

# Returns
# [
#     {"id": "lead-123", "score": 0.92, "text": "...", "metadata": {...}},
#     ...
# ]
```

## Configuration

| Variable               | Default                  | Description       |
| ---------------------- | ------------------------ | ----------------- |
| `CHROMA_HOST`          | `localhost`              | ChromaDB host     |
| `CHROMA_PORT`          | `8000`                   | ChromaDB port     |
| `EMBEDDING_MODEL`      | `text-embedding-3-small` | OpenAI model      |
| `EMBEDDING_DIMENSIONS` | `1536`                   | Vector dimensions |

## Integration with RAG Agent

When implemented:

```python
class RAGAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(tenant_id, "rag")
        self.db = SupabaseAdapter(role="agent_reader")
        self.vector_db = VectorDBClient()  # New

    async def search_similar_leads(self, query: str) -> list:
        # Semantic search across lead profiles
        return await self.vector_db.search(
            collection=f"{self.tenant_id}-leads",
            query=query,
            limit=10
        )
```

## Related

- [RAG Agent](../tier-3/rag.md)
- [Roadmap](../../roadmap/in-progress.md)
