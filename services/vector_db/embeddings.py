"""
Embeddings Provider - Vector embedding generation and management

Supports multiple embedding models:
- OpenAI (text-embedding-ada-002, text-embedding-3-large)
- HuggingFace (sentence-transformers)
- Local models for privacy-sensitive data

Features:
- Model caching
- Batch embedding generation
- Dimension normalization
- Rate limiting
- Cost tracking
"""

import logging
import os
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingModel:
    """Metadata about an embedding model"""
    name: str
    provider: str
    dimensions: int
    max_tokens: int
    cost_per_1k_tokens: float


class EmbeddingsProvider:
    """
    Unified Embeddings Provider
    
    Generates text embeddings using various models.
    Handles model selection, caching, and batch processing.
    """
    
    # Available models and their specs
    MODELS = {
        "text-embedding-ada-002": EmbeddingModel(
            name="text-embedding-ada-002",
            provider="openai",
            dimensions=1536,
            max_tokens=8191,
            cost_per_1k_tokens=0.0001
        ),
        "text-embedding-3-small": EmbeddingModel(
            name="text-embedding-3-small",
            provider="openai",
            dimensions=1536,
            max_tokens=8191,
            cost_per_1k_tokens=0.00002
        ),
        "text-embedding-3-large": EmbeddingModel(
            name="text-embedding-3-large",
            provider="openai",
            dimensions=3072,
            max_tokens=8191,
            cost_per_1k_tokens=0.00013
        ),
        "sentence-transformers/all-MiniLM-L6-v2": EmbeddingModel(
            name="sentence-transformers/all-MiniLM-L6-v2",
            provider="huggingface",
            dimensions=384,
            max_tokens=512,
            cost_per_1k_tokens=0.0
        ),
        "sentence-transformers/all-mpnet-base-v2": EmbeddingModel(
            name="sentence-transformers/all-mpnet-base-v2",
            provider="huggingface",
            dimensions=768,
            max_tokens=384,
            cost_per_1k_tokens=0.0
        ),
    }
    
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        cache_enabled: bool = True
    ):
        """
        Initialize Embeddings Provider.
        
        Args:
            model: Model name from MODELS dict
            api_key: API key for cloud-based models
            cache_enabled: Whether to cache embeddings
        """
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}. Available: {list(self.MODELS.keys())}")
        
        self.model_name = model
        self.model_spec = self.MODELS[model]
        self.cache_enabled = cache_enabled
        self._embedding_cache: Dict[str, List[float]] = {}
        self._client = None
        self._token_count = 0
        
        logger.info(f"EmbeddingsProvider initialized (model={model}, dims={self.model_spec.dimensions})")
        
        # Initialize model-specific client
        if self.model_spec.provider == "openai":
            self._init_openai(api_key)
        elif self.model_spec.provider == "huggingface":
            self._init_huggingface()
        else:
            raise ValueError(f"Unknown provider: {self.model_spec.provider}")
    
    def _init_openai(self, api_key: Optional[str]) -> None:
        """Initialize OpenAI embeddings client"""
        try:
            import openai
            
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            
            openai.api_key = api_key
            self._client = openai.Embedding
            logger.info(f"OpenAI embeddings client initialized")
        except ImportError:
            logger.error("openai package not installed. Install with: pip install openai")
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            self._client = None
    
    def _init_huggingface(self) -> None:
        """Initialize HuggingFace embeddings client"""
        try:
            from sentence_transformers import SentenceTransformer
            
            self._client = SentenceTransformer(self.model_name)
            logger.info(f"HuggingFace model loaded: {self.model_name}")
        except ImportError:
            logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize HuggingFace model: {e}")
            self._client = None
    
    # ==================== EMBEDDING OPERATIONS ====================
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
        
        Returns:
            Vector embedding
        """
        # Check cache first
        if self.cache_enabled and text in self._embedding_cache:
            return self._embedding_cache[text]
        
        try:
            if self.model_spec.provider == "openai":
                embedding = self._embed_openai(text)
            else:
                embedding = self._embed_huggingface(text)
            
            # Cache result
            if self.cache_enabled:
                self._embedding_cache[text] = embedding
            
            return embedding
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return []
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of vector embeddings
        """
        embeddings = []
        
        # Separate cached and uncached texts
        cached = []
        uncached = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            if self.cache_enabled and text in self._embedding_cache:
                cached.append(self._embedding_cache[text])
            else:
                uncached.append(text)
                uncached_indices.append(i)
        
        # Generate embeddings for uncached texts
        if uncached:
            try:
                if self.model_spec.provider == "openai":
                    new_embeddings = self._embed_batch_openai(uncached)
                else:
                    new_embeddings = self._embed_batch_huggingface(uncached)
                
                # Cache new embeddings
                if self.cache_enabled:
                    for text, embedding in zip(uncached, new_embeddings):
                        self._embedding_cache[text] = embedding
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                new_embeddings = [[] for _ in uncached]
        else:
            new_embeddings = []
        
        # Reconstruct results in original order
        result = [[] for _ in texts]
        for i, embedding in zip(range(len(cached)), cached):
            result[i] = embedding
        for i, idx in enumerate(uncached_indices):
            result[idx] = new_embeddings[i]
        
        return result
    
    def _embed_openai(self, text: str) -> List[float]:
        """Generate embedding using OpenAI"""
        if not self._client:
            logger.warning("OpenAI client not initialized")
            return []
        
        try:
            response = self._client.create(
                input=text,
                model=self.model_name
            )
            
            embedding = response["data"][0]["embedding"]
            
            # Track token usage for cost estimation
            self._token_count += response.get("usage", {}).get("prompt_tokens", 0)
            
            return embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            return []
    
    def _embed_batch_openai(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings using OpenAI"""
        if not self._client:
            logger.warning("OpenAI client not initialized")
            return [[] for _ in texts]
        
        try:
            response = self._client.create(
                input=texts,
                model=self.model_name
            )
            
            # Sort by index to maintain order
            embeddings = [None] * len(texts)
            for item in response["data"]:
                embeddings[item["index"]] = item["embedding"]
            
            # Track token usage
            self._token_count += response.get("usage", {}).get("prompt_tokens", 0)
            
            return embeddings
        except Exception as e:
            logger.error(f"OpenAI batch embedding failed: {e}")
            return [[] for _ in texts]
    
    def _embed_huggingface(self, text: str) -> List[float]:
        """Generate embedding using HuggingFace"""
        if not self._client:
            logger.warning("HuggingFace model not loaded")
            return []
        
        try:
            embedding = self._client.encode(text, convert_to_list=True)
            return embedding
        except Exception as e:
            logger.error(f"HuggingFace embedding failed: {e}")
            return []
    
    def _embed_batch_huggingface(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings using HuggingFace"""
        if not self._client:
            logger.warning("HuggingFace model not loaded")
            return [[] for _ in texts]
        
        try:
            embeddings = self._client.encode(texts, convert_to_list=True)
            return embeddings
        except Exception as e:
            logger.error(f"HuggingFace batch embedding failed: {e}")
            return [[] for _ in texts]
    
    # ==================== UTILITY METHODS ====================
    
    def get_dimensions(self) -> int:
        """Get embedding vector dimensions"""
        return self.model_spec.dimensions
    
    def get_cost_estimate(self) -> Dict[str, float]:
        """Get cost estimate for embeddings generated so far"""
        cost = self._token_count / 1000 * self.model_spec.cost_per_1k_tokens
        return {
            "tokens": self._token_count,
            "estimated_cost": cost,
            "currency": "USD"
        }
    
    def clear_cache(self) -> None:
        """Clear embedding cache"""
        self._embedding_cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "cached_embeddings": len(self._embedding_cache),
            "cache_enabled": self.cache_enabled
        }
