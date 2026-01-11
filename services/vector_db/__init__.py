"""
Vector DB Service - Vector database operations and embeddings

Provides unified interface for vector operations:
- Vector embeddings creation (OpenAI, HuggingFace)
- Similarity search with scoring
- Vector storage and retrieval
- Batch operations for efficiency
- Multi-backend support (Pinecone, Weaviate, in-memory)
- Index management
- Metadata filtering

Features:
- Support for multiple vector databases (Pinecone, Weaviate, in-memory)
- Multiple embedding models (OpenAI, HuggingFace, local)
- Caching and optimization
- Batch operations
- Cost tracking (OpenAI)
- Performance metrics

Architecture:
- VectorDBClient: Unified interface for vector DB operations
  - Supports: search_similar_companies, search_similar_leads, semantic_search
  - Backends: Pinecone, Weaviate, in-memory (development)
  - Metadata filtering and namespace support

- EmbeddingsProvider: Text embedding generation
  - Models: text-embedding-3-small, text-embedding-3-large, sentence-transformers
  - Features: Caching, batch processing, cost estimation
  - Providers: OpenAI, HuggingFace, local

- Config: Environment-based configuration
  - Settings: vector DB type, embedding model, search parameters
  - Environment variables: VECTOR_DB_TYPE, EMBEDDING_MODEL, PINECONE_API_KEY, etc.

Usage:
    from services.vector_db import VectorDBClient, EmbeddingsProvider
    
    # Initialize embeddings provider
    embeddings = EmbeddingsProvider(model="text-embedding-3-small")
    
    # Generate embeddings
    text = "Senior software engineer at startup with 5 years experience"
    embedding = embeddings.embed_text(text)
    
    # Initialize vector DB client
    client = VectorDBClient(backend="pinecone")
    
    # Search similar companies
    results = client.search_similar_companies(
        query_embedding=embedding,
        limit=10,
        filters={"industry": "technology"}
    )
    
    # Upsert vectors
    client.upsert_vector(
        vector_id="company_123",
        embedding=embedding,
        metadata={"name": "Acme Corp", "industry": "technology"}
    )

Exported Components:
- VectorDBClient: Main vector database client
- SimilarityMatch: Result dataclass for company/lead searches
- VectorSearchResult: Result dataclass for semantic search
- EmbeddingsProvider: Embedding model wrapper
- EmbeddingModel: Model metadata
- Config: Configuration management (get_config, reset_config)
"""

from .client import VectorDBClient, SimilarityMatch, VectorSearchResult
from .embeddings import EmbeddingsProvider, EmbeddingModel
from .config import get_config, reset_config

__all__ = [
    # Client classes
    "VectorDBClient",
    "EmbeddingsProvider",
    # Result types
    "SimilarityMatch",
    "VectorSearchResult",
    "EmbeddingModel",
    # Configuration
    "get_config",
    "reset_config",
    # Sub-modules
    "client",
    "embeddings",
    "config",
]

