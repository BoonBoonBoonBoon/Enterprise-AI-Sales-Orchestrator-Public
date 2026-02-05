"""
Embedding Pipeline for RAG Entity Indexing

Provides batch embedding generation and vector DB indexing:
- Text field extraction per entity type
- Batch embedding generation (OpenAI or local)
- Redis caching (TTL 7 days)
- VectorDBClient integration
- Namespace isolation per entity type

Usage:
    pipeline = EmbeddingPipeline(redis_client=redis)
    await pipeline.index_entity(EntityType.LEAD, lead_record)
    results = await pipeline.search_similar(EntityType.LEAD, "AI startup in SF", limit=10)
"""

import logging
import json
import hashlib
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

try:
    from services.vector_db import VectorDBClient
    from services.vector_db.embeddings import EmbeddingsProvider
    from services.vector_db.config import get_config
except ImportError:
    try:
        from agent.tools.vector_db.client import VectorDBClient
        from agent.tools.vector_db.embeddings import EmbeddingsProvider
    except ImportError:
        VectorDBClient = None
        EmbeddingsProvider = None
    try:
        from agent.tools.vector_db.config import get_config
    except ImportError:
        get_config = None

try:
    from config.rag_entities import EntityType, get_text_fields
except ImportError:
    from rag_entities import EntityType, get_text_fields

logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    """
    Embedding pipeline for RAG entities.
    
    Handles:
    - Text extraction from entity records
    - Embedding generation (cached in Redis)
    - Vector DB indexing
    - Similarity search
    """
    
    def __init__(
        self,
        redis_client,
        vector_db_client: Optional[VectorDBClient] = None,
        embeddings_provider: Optional[EmbeddingsProvider] = None,
        tenant_id: str = "default",
        cache_ttl_seconds: int = 604800  # 7 days
    ):
        """
        Initialize embedding pipeline.
        
        Args:
            redis_client: Redis client for caching
            vector_db_client: VectorDBClient instance (creates default if None)
            embeddings_provider: EmbeddingsProvider instance (creates default if None)
            tenant_id: Tenant ID for cache key isolation
            cache_ttl_seconds: Cache TTL (default 7 days)
        """
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.cache_ttl = cache_ttl_seconds
        
        # Initialize vector DB client
        if vector_db_client:
            self.vector_db = vector_db_client
        elif VectorDBClient:
            backend = "in_memory"
            api_key = None
            environment = None
            index_name = "agentic-default"

            if get_config:
                cfg = get_config()
                backend = cfg.vector_db_type or backend
                api_key = cfg.pinecone_api_key or None
                environment = cfg.pinecone_environment or None
                index_name = cfg.pinecone_index or index_name

            if backend not in ("pinecone", "weaviate", "in_memory"):
                logger.warning(f"Unknown VECTOR_DB_TYPE '{backend}', falling back to in_memory")
                backend = "in_memory"

            self.vector_db = VectorDBClient(
                backend=backend,
                api_key=api_key,
                environment=environment,
                index_name=index_name,
            )
        else:
            logger.warning("VectorDBClient not available - vector operations will fail")
            self.vector_db = None
        
        # Initialize embeddings provider
        if embeddings_provider:
            self.embeddings = embeddings_provider
        elif EmbeddingsProvider:
            self.embeddings = EmbeddingsProvider()
        else:
            logger.warning("EmbeddingsProvider not available - embedding operations will fail")
            self.embeddings = None
        
        logger.info(f"EmbeddingPipeline initialized (tenant={tenant_id}, cache_ttl={cache_ttl_seconds}s)")
    
    # ==================== TEXT EXTRACTION ====================
    
    def extract_text_for_embedding(
        self,
        entity_type: EntityType,
        record: Dict[str, Any]
    ) -> str:
        """
        Extract and combine text fields for embedding.
        
        Args:
            entity_type: Type of entity
            record: Entity record data
        
        Returns:
            Combined text string for embedding
        
        Example:
            >>> extract_text_for_embedding(
            ...     EntityType.LEAD,
            ...     {"company_name": "Acme Corp", "job_title": "CEO", "industry": "SaaS"}
            ... )
            "Acme Corp | CEO | | SaaS"
        """
        text_fields = get_text_fields(entity_type)
        
        # Extract field values
        field_values = []
        for field in text_fields:
            value = record.get(field, "")
            if value:
                field_values.append(str(value))
            else:
                field_values.append("")
        
        # Join with separator
        combined = " | ".join(field_values)
        
        # Add entity type prefix for context
        prefixed = f"[{entity_type.value}] {combined}"
        
        return prefixed
    
    # ==================== EMBEDDING GENERATION ====================
    
    async def generate_embedding(
        self,
        text: str,
        use_cache: bool = True
    ) -> Optional[List[float]]:
        """
        Generate embedding for text with Redis caching.
        
        Args:
            text: Text to embed
            use_cache: Whether to use Redis cache
        
        Returns:
            Embedding vector or None if generation fails
        """
        if not self.embeddings:
            logger.error("EmbeddingsProvider not available")
            return None
        
        # Generate cache key
        cache_key = self._get_cache_key(text)
        
        # Try cache first
        if use_cache and self.redis:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    if isinstance(cached, bytes):
                        cached = cached.decode()
                    embedding = json.loads(cached)
                    logger.debug(f"Cache hit for embedding: {cache_key}")
                    return embedding
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
        
        # Generate embedding
        try:
            embed_result = self.embeddings.embed_text(text)
            if asyncio.iscoroutine(embed_result):
                embedding = await embed_result
            else:
                embedding = embed_result
            
            # Cache result
            if use_cache and self.redis and embedding:
                try:
                    self.redis.setex(
                        cache_key,
                        self.cache_ttl,
                        json.dumps(embedding)
                    )
                    logger.debug(f"Cached embedding: {cache_key}")
                except Exception as e:
                    logger.warning(f"Cache write failed: {e}")
            
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        use_cache: bool = True
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts with batching.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use Redis cache
        
        Returns:
            List of embeddings (None for failures)
        """
        if not self.embeddings:
            logger.error("EmbeddingsProvider not available")
            return [None] * len(texts)
        
        # Check cache for each text
        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []
        
        if use_cache and self.redis:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                try:
                    cached = self.redis.get(cache_key)
                    if cached:
                        if isinstance(cached, bytes):
                            cached = cached.decode()
                        embeddings[i] = json.loads(cached)
                    else:
                        uncached_indices.append(i)
                        uncached_texts.append(text)
                except Exception as e:
                    logger.warning(f"Cache read failed: {e}")
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        else:
            uncached_indices = list(range(len(texts)))
            uncached_texts = texts
        
        # Generate embeddings for uncached texts
        if uncached_texts:
            try:
                embed_batch_fn = getattr(self.embeddings, "embed_texts", None) or getattr(self.embeddings, "embed_batch", None)
                if not embed_batch_fn:
                    raise RuntimeError("EmbeddingsProvider does not support batch embedding")

                batch_result = embed_batch_fn(uncached_texts)
                if asyncio.iscoroutine(batch_result):
                    new_embeddings = await batch_result
                else:
                    new_embeddings = batch_result
                
                # Cache and assign results
                for i, embedding in zip(uncached_indices, new_embeddings):
                    embeddings[i] = embedding
                    
                    # Cache successful embeddings
                    if use_cache and self.redis and embedding:
                        cache_key = self._get_cache_key(texts[i])
                        try:
                            self.redis.setex(
                                cache_key,
                                self.cache_ttl,
                                json.dumps(embedding)
                            )
                        except Exception as e:
                            logger.warning(f"Cache write failed: {e}")
            except Exception as e:
                logger.error(f"Batch embedding generation failed: {e}")
        
        return embeddings
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{self.tenant_id}:embeddings:{text_hash}"
    
    # ==================== VECTOR DB OPERATIONS ====================
    
    async def index_entity(
        self,
        entity_type: EntityType,
        record: Dict[str, Any]
    ) -> bool:
        """
        Index entity in vector database.
        
        Args:
            entity_type: Type of entity
            record: Entity record with all fields
        
        Returns:
            True if indexing succeeded
        
        Example:
            >>> await pipeline.index_entity(
            ...     EntityType.LEAD,
            ...     {"id": "123", "company_name": "Acme", "job_title": "CEO"}
            ... )
            True
        """
        if not self.vector_db:
            logger.error("VectorDBClient not available")
            return False
        
        # Extract text
        text = self.extract_text_for_embedding(entity_type, record)
        if not text.strip():
            logger.warning(f"No text to embed for {entity_type.value} record")
            return False
        
        # Generate embedding
        embedding = await self.generate_embedding(text)
        if not embedding:
            logger.error(f"Failed to generate embedding for {entity_type.value}")
            return False
        
        # Get record ID
        record_id = record.get("id") or record.get("task_id") or record.get("sub_task_id")
        if not record_id:
            logger.error(f"No ID found in {entity_type.value} record")
            return False
        
        # Build metadata
        metadata = {
            "entity_type": entity_type.value,
            "record_id": str(record_id),
            "indexed_at": datetime.utcnow().isoformat(),
            "tenant_id": self.tenant_id,
        }
        
        # Add key fields to metadata for filtering
        if entity_type == EntityType.LEAD:
            metadata.update({
                "company_name": record.get("company_name", ""),
                "enrichment_status": record.get("enrichment_status", ""),
            })
        elif entity_type == EntityType.CONVERSATION:
            metadata.update({
                "channel": record.get("channel", ""),
                "status": record.get("status", ""),
            })
        elif entity_type == EntityType.CAMPAIGN:
            metadata.update({
                "campaign_type": record.get("campaign_type", ""),
                "status": record.get("status", ""),
            })
        
        # Upsert to vector DB
        vector_id = f"{entity_type.value}:{record_id}"
        namespace = entity_type.value  # Namespace per entity type
        
        success = self.vector_db.upsert_vector(
            vector_id=vector_id,
            embedding=embedding,
            metadata=metadata,
            namespace=namespace
        )
        
        if success:
            logger.info(f"Indexed {entity_type.value} {record_id} in vector DB")
        else:
            logger.error(f"Failed to index {entity_type.value} {record_id}")
        
        return success
    
    async def index_entities_batch(
        self,
        entity_type: EntityType,
        records: List[Dict[str, Any]]
    ) -> int:
        """
        Batch index multiple entities.
        
        Args:
            entity_type: Type of entities
            records: List of entity records
        
        Returns:
            Number of successfully indexed records
        """
        if not self.vector_db:
            logger.error("VectorDBClient not available")
            return 0
        
        # Extract texts
        texts = [
            self.extract_text_for_embedding(entity_type, record)
            for record in records
        ]
        
        # Generate embeddings
        embeddings = await self.generate_embeddings_batch(texts)
        
        # Build vectors for batch upsert
        vectors: List[Tuple[str, List[float], Dict[str, Any]]] = []
        for i, (record, embedding) in enumerate(zip(records, embeddings)):
            if not embedding:
                continue
            
            record_id = record.get("id") or record.get("task_id") or record.get("sub_task_id")
            if not record_id:
                continue
            
            vector_id = f"{entity_type.value}:{record_id}"
            metadata = {
                "entity_type": entity_type.value,
                "record_id": str(record_id),
                "indexed_at": datetime.utcnow().isoformat(),
                "tenant_id": self.tenant_id,
            }
            
            vectors.append((vector_id, embedding, metadata))
        
        # Batch upsert
        if vectors:
            count = self.vector_db.upsert_batch(
                vectors=vectors,
                namespace=entity_type.value
            )
            logger.info(f"Batch indexed {count}/{len(records)} {entity_type.value} records")
            return count
        else:
            logger.warning(f"No valid vectors to index for {entity_type.value}")
            return 0
    
    async def search_similar(
        self,
        entity_type: EntityType,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar entities.
        
        Args:
            entity_type: Type of entity to search
            query: Search query text
            limit: Maximum results
            filters: Metadata filters
        
        Returns:
            List of matching records with similarity scores
        
        Example:
            >>> results = await pipeline.search_similar(
            ...     EntityType.LEAD,
            ...     "AI startup CEO in San Francisco",
            ...     limit=10,
            ...     filters={"enrichment_status": "completed"}
            ... )
        """
        if not self.vector_db:
            logger.error("VectorDBClient not available")
            return []
        
        # Generate query embedding
        query_embedding = await self.generate_embedding(f"[{entity_type.value}] {query}")
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []
        
        # Search vector DB
        matches = self.vector_db._search(
            query_embedding=query_embedding,
            limit=limit,
            namespace=entity_type.value,
            filters=filters
        )
        
        # Format results
        results = []
        for match in matches:
            results.append({
                "record_id": match.metadata.get("record_id"),
                "similarity_score": match.similarity_score,
                "entity_type": match.item_type,
                "metadata": match.metadata
            })
        
        return results


__all__ = [
    "EmbeddingPipeline",
]
