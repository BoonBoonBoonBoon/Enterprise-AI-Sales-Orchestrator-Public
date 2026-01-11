"""
Vector Database Client - Unified interface for vector operations

Supports multiple vector database backends:
- Pinecone (cloud-hosted)
- Weaviate (self-hosted)
- In-memory for development/testing

Provides:
- Vector search with similarity scoring
- Batch operations for efficiency
- Metadata filtering
- Index management
- Caching and rate limiting
"""

import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import os

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """Result from vector search operation"""
    id: str
    score: float
    metadata: Dict[str, Any]
    text: Optional[str] = None


@dataclass
class SimilarityMatch:
    """Similarity match result"""
    item_id: str
    similarity_score: float
    item_type: str
    metadata: Dict[str, Any]


class VectorDBClient:
    """
    Unified Vector Database Client
    
    Abstracts away specific vector DB implementation details.
    Supports similarity search, metadata filtering, and batch operations.
    """
    
    def __init__(
        self,
        backend: str = "in_memory",
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        index_name: str = "agentic-default"
    ):
        """
        Initialize Vector DB Client.
        
        Args:
            backend: "pinecone", "weaviate", or "in_memory"
            api_key: API key for cloud backends
            environment: Environment name for Pinecone
            index_name: Name of vector index to use
        """
        self.backend = backend
        self.index_name = index_name
        self._client = None
        self._cache: Dict[str, VectorSearchResult] = {}
        
        logger.info(f"VectorDBClient initialized (backend={backend}, index={index_name})")
        
        # Initialize backend-specific client
        if backend == "pinecone":
            self._init_pinecone(api_key, environment)
        elif backend == "weaviate":
            self._init_weaviate(api_key)
        elif backend == "in_memory":
            self._init_in_memory()
        else:
            raise ValueError(f"Unsupported backend: {backend}")
    
    def _init_pinecone(self, api_key: Optional[str], environment: Optional[str]) -> None:
        """Initialize Pinecone client"""
        try:
            import pinecone
            
            api_key = api_key or os.getenv("PINECONE_API_KEY")
            environment = environment or os.getenv("PINECONE_ENVIRONMENT", "us-west1-gcp")
            
            if not api_key:
                logger.warning("PINECONE_API_KEY not set. Vector operations will fail.")
                self._client = None
                return
            
            pinecone.init(api_key=api_key, environment=environment)
            self._client = pinecone.Index(self.index_name)
            logger.info(f"Pinecone client initialized (index={self.index_name})")
        except ImportError:
            logger.warning("Pinecone not installed. Install with: pip install pinecone-client")
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            self._client = None
    
    def _init_weaviate(self, api_key: Optional[str]) -> None:
        """Initialize Weaviate client"""
        try:
            import weaviate
            
            url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
            api_key = api_key or os.getenv("WEAVIATE_API_KEY")
            
            auth_config = None
            if api_key:
                auth_config = weaviate.AuthApiKey(api_key=api_key)
            
            self._client = weaviate.Client(url=url, auth_client_secret=auth_config)
            logger.info(f"Weaviate client initialized (url={url})")
        except ImportError:
            logger.warning("Weaviate not installed. Install with: pip install weaviate-client")
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize Weaviate: {e}")
            self._client = None
    
    def _init_in_memory(self) -> None:
        """Initialize in-memory vector store"""
        self._vectors: Dict[str, Tuple[List[float], Dict[str, Any]]] = {}
        self._client = None
        logger.info("In-memory vector store initialized")
    
    # ==================== SEARCH OPERATIONS ====================
    
    def search_similar_companies(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SimilarityMatch]:
        """
        Search for similar companies.
        
        Args:
            query_embedding: Query vector embedding
            limit: Maximum results to return
            filters: Metadata filters (e.g., {"company_type": "startup"})
        
        Returns:
            List of SimilarityMatch results
        """
        try:
            results = self._search(
                query_embedding=query_embedding,
                limit=limit,
                namespace="companies",
                filters=filters
            )
            return results
        except Exception as e:
            logger.error(f"Company similarity search failed: {e}")
            return []
    
    def search_similar_leads(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SimilarityMatch]:
        """
        Search for similar leads.
        
        Args:
            query_embedding: Query vector embedding
            limit: Maximum results to return
            filters: Metadata filters
        
        Returns:
            List of SimilarityMatch results
        """
        try:
            results = self._search(
                query_embedding=query_embedding,
                limit=limit,
                namespace="leads",
                filters=filters
            )
            return results
        except Exception as e:
            logger.error(f"Lead similarity search failed: {e}")
            return []
    
    def semantic_search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        Semantic search across knowledge base.
        
        Args:
            query_embedding: Query vector embedding
            limit: Maximum results
            filters: Metadata filters
        
        Returns:
            List of VectorSearchResult
        """
        try:
            results = self._search_raw(
                query_embedding=query_embedding,
                limit=limit,
                filters=filters
            )
            return results
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def _search(
        self,
        query_embedding: List[float],
        limit: int,
        namespace: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SimilarityMatch]:
        """Internal search for structured data (companies, leads)"""
        results = self._search_raw(query_embedding, limit, filters)
        
        matches = []
        for result in results:
            match = SimilarityMatch(
                item_id=result.id,
                similarity_score=result.score,
                item_type=namespace.rstrip("s"),  # companies -> company
                metadata=result.metadata
            )
            matches.append(match)
        
        return matches
    
    def _search_raw(
        self,
        query_embedding: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """Raw vector search operation"""
        
        if self.backend == "in_memory":
            return self._search_in_memory(query_embedding, limit, filters)
        elif self.backend == "pinecone":
            return self._search_pinecone(query_embedding, limit, filters)
        elif self.backend == "weaviate":
            return self._search_weaviate(query_embedding, limit, filters)
        else:
            logger.error(f"Unknown backend: {self.backend}")
            return []
    
    def _search_in_memory(
        self,
        query_embedding: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """In-memory vector search using cosine similarity"""
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            """Calculate cosine similarity"""
            if not a or not b:
                return 0.0
            dot_product = sum(x * y for x, y in zip(a, b))
            mag_a = sum(x ** 2 for x in a) ** 0.5
            mag_b = sum(y ** 2 for y in b) ** 0.5
            if mag_a == 0 or mag_b == 0:
                return 0.0
            return dot_product / (mag_a * mag_b)
        
        # Calculate similarity with all vectors
        scores = []
        for vector_id, (vector, metadata) in self._vectors.items():
            # Apply filters if provided
            if filters:
                skip = False
                for key, value in filters.items():
                    if metadata.get(key) != value:
                        skip = True
                        break
                if skip:
                    continue
            
            similarity = cosine_similarity(query_embedding, vector)
            scores.append((vector_id, similarity, metadata))
        
        # Sort by similarity and return top results
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for vector_id, score, metadata in scores[:limit]:
            result = VectorSearchResult(
                id=vector_id,
                score=max(0.0, min(1.0, (score + 1) / 2)),  # Normalize to [0, 1]
                metadata=metadata
            )
            results.append(result)
        
        return results
    
    def _search_pinecone(
        self,
        query_embedding: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """Search using Pinecone"""
        if not self._client:
            logger.warning("Pinecone client not initialized")
            return []
        
        try:
            response = self._client.query(
                vector=query_embedding,
                top_k=limit,
                include_metadata=True,
                filter=filters
            )
            
            results = []
            for match in response.get("matches", []):
                result = VectorSearchResult(
                    id=match["id"],
                    score=match["score"],
                    metadata=match.get("metadata", {})
                )
                results.append(result)
            
            return results
        except Exception as e:
            logger.error(f"Pinecone search failed: {e}")
            return []
    
    def _search_weaviate(
        self,
        query_embedding: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """Search using Weaviate"""
        if not self._client:
            logger.warning("Weaviate client not initialized")
            return []
        
        try:
            # Weaviate requires class name for search
            class_name = "AgenticVector"
            
            response = self._client.query.get(class_name, ["_additional {vector distance}"] if query_embedding else []).with_near_vector(
                {"vector": query_embedding}
            ).with_limit(limit).do()
            
            results = []
            for item in response.get("data", {}).get("Get", {}).get(class_name, []):
                result = VectorSearchResult(
                    id=item.get("id", ""),
                    score=1.0 - item.get("_additional", {}).get("distance", 1.0),
                    metadata=item
                )
                results.append(result)
            
            return results
        except Exception as e:
            logger.error(f"Weaviate search failed: {e}")
            return []
    
    # ==================== UPSERT OPERATIONS ====================
    
    def upsert_vector(
        self,
        vector_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str = "default"
    ) -> bool:
        """
        Upsert (insert or update) a single vector.
        
        Args:
            vector_id: Unique identifier for the vector
            embedding: Vector embedding
            metadata: Associated metadata
            namespace: Vector namespace
        
        Returns:
            True if successful
        """
        try:
            if self.backend == "in_memory":
                self._vectors[vector_id] = (embedding, metadata)
                return True
            elif self.backend == "pinecone":
                return self._upsert_pinecone(vector_id, embedding, metadata, namespace)
            elif self.backend == "weaviate":
                return self._upsert_weaviate(vector_id, embedding, metadata)
            else:
                return False
        except Exception as e:
            logger.error(f"Upsert failed for {vector_id}: {e}")
            return False
    
    def _upsert_pinecone(
        self,
        vector_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str
    ) -> bool:
        """Upsert vector to Pinecone"""
        if not self._client:
            return False
        
        try:
            self._client.upsert(
                vectors=[(vector_id, embedding, metadata)],
                namespace=namespace
            )
            return True
        except Exception as e:
            logger.error(f"Pinecone upsert failed: {e}")
            return False
    
    def _upsert_weaviate(
        self,
        vector_id: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """Upsert vector to Weaviate"""
        if not self._client:
            return False
        
        try:
            self._client.data_object.create(
                data_object=metadata,
                class_name="AgenticVector",
                vector=embedding
            )
            return True
        except Exception as e:
            logger.error(f"Weaviate upsert failed: {e}")
            return False
    
    def upsert_batch(
        self,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
        namespace: str = "default"
    ) -> int:
        """
        Batch upsert multiple vectors.
        
        Args:
            vectors: List of (id, embedding, metadata) tuples
            namespace: Vector namespace
        
        Returns:
            Number of vectors successfully upserted
        """
        if self.backend == "in_memory":
            for vector_id, embedding, metadata in vectors:
                self._vectors[vector_id] = (embedding, metadata)
            return len(vectors)
        elif self.backend == "pinecone":
            return self._upsert_batch_pinecone(vectors, namespace)
        elif self.backend == "weaviate":
            return self._upsert_batch_weaviate(vectors)
        else:
            return 0
    
    def _upsert_batch_pinecone(
        self,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
        namespace: str
    ) -> int:
        """Batch upsert to Pinecone"""
        if not self._client:
            return 0
        
        try:
            prepared = [(vid, emb, meta) for vid, emb, meta in vectors]
            self._client.upsert(vectors=prepared, namespace=namespace)
            return len(vectors)
        except Exception as e:
            logger.error(f"Pinecone batch upsert failed: {e}")
            return 0
    
    def _upsert_batch_weaviate(
        self,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]]
    ) -> int:
        """Batch upsert to Weaviate"""
        if not self._client:
            return 0
        
        count = 0
        for vector_id, embedding, metadata in vectors:
            try:
                self._client.data_object.create(
                    data_object=metadata,
                    class_name="AgenticVector",
                    vector=embedding
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert {vector_id}: {e}")
        
        return count
    
    # ==================== UTILITY OPERATIONS ====================
    
    def delete_vector(self, vector_id: str, namespace: str = "default") -> bool:
        """Delete a vector"""
        try:
            if self.backend == "in_memory":
                if vector_id in self._vectors:
                    del self._vectors[vector_id]
                    return True
                return False
            elif self.backend == "pinecone":
                return self._delete_pinecone(vector_id, namespace)
            elif self.backend == "weaviate":
                return self._delete_weaviate(vector_id)
            else:
                return False
        except Exception as e:
            logger.error(f"Delete failed for {vector_id}: {e}")
            return False
    
    def _delete_pinecone(self, vector_id: str, namespace: str) -> bool:
        """Delete vector from Pinecone"""
        if not self._client:
            return False
        
        try:
            self._client.delete(ids=[vector_id], namespace=namespace)
            return True
        except Exception as e:
            logger.error(f"Pinecone delete failed: {e}")
            return False
    
    def _delete_weaviate(self, vector_id: str) -> bool:
        """Delete vector from Weaviate"""
        if not self._client:
            return False
        
        try:
            self._client.data_object.delete(vector_id, class_name="AgenticVector")
            return True
        except Exception as e:
            logger.error(f"Weaviate delete failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector database statistics"""
        stats = {
            "backend": self.backend,
            "index_name": self.index_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self.backend == "in_memory":
            stats["vector_count"] = len(self._vectors)
            stats["cache_size"] = len(self._cache)
        
        return stats
