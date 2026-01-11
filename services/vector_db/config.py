"""
Vector DB Service Configuration

Environment-based configuration for vector database operations.
Supports multiple vector database backends.
"""

import os
from typing import Optional


class VectorDBConfig:
    """Configuration for Vector DB Service"""
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.vector_db_type = os.getenv("VECTOR_DB_TYPE", "pinecone")
        
        # Pinecone configuration
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY", "")
        self.pinecone_environment = os.getenv("PINECONE_ENVIRONMENT", "")
        self.pinecone_index = os.getenv("PINECONE_INDEX", "agentic-system")
        
        # Embeddings configuration
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai")
        
        # Search settings
        self.search_top_k = int(os.getenv("VECTOR_SEARCH_TOP_K", "5"))
        self.search_threshold = float(os.getenv("VECTOR_SEARCH_THRESHOLD", "0.7"))
    
    def to_dict(self) -> dict:
        """Convert config to dictionary (without sensitive data)"""
        return {
            "environment": self.environment,
            "vector_db_type": self.vector_db_type,
            "pinecone_index": self.pinecone_index,
            "embedding_model": self.embedding_model,
            "embedding_dimension": str(self.embedding_dimension),
            "embedding_provider": self.embedding_provider,
            "search_top_k": str(self.search_top_k),
            "search_threshold": str(self.search_threshold),
        }


# Global config instance
_config: Optional[VectorDBConfig] = None


def get_config() -> VectorDBConfig:
    """Get vector DB service configuration"""
    global _config
    if _config is None:
        _config = VectorDBConfig()
    return _config


def reset_config() -> None:
    """Reset configuration (for testing)"""
    global _config
    _config = None
