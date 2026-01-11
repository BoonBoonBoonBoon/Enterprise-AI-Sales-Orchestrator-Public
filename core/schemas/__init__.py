"""
Core Schemas Module

Type-safe schemas for all agent payloads and configurations.

This module provides Pydantic models for:
- Task payloads (RAG, copywriter, persistence)
- Result payloads
- Configuration schemas
- Validation utilities

Usage:
    from core.schemas.rag import RAGTaskPayload, QuerySpec
    from core.schemas.copywriter import CopywriterTaskPayload
    from core.schemas.persistence import PersistenceTaskPayload
    
    task = RAGTaskPayload(
        query=QuerySpec(table="leads", filters={"email": "test@example.com"})
    )
"""

# Re-export commonly used schemas for convenience
from .rag import RAGTaskPayload, RAGResultPayload, QuerySpec
from .copywriter import CopywriterTaskPayload, CopywriterResultPayload, LeadData, CampaignContext
from .persistence import PersistenceTaskPayload, PersistenceResultPayload, WriteOperation, WriteSpec
from .config import WorkerConfig, RedisConfig, DatabaseConfig
from .validation import validate_payload, ValidationError

__all__ = [
    # RAG
    "RAGTaskPayload",
    "RAGResultPayload",
    "QuerySpec",
    
    # Copywriter
    "CopywriterTaskPayload",
    "CopywriterResultPayload",
    "LeadData",
    "CampaignContext",
    
    # Persistence
    "PersistenceTaskPayload",
    "PersistenceResultPayload",
    "WriteOperation",
    "WriteSpec",
    
    # Config
    "WorkerConfig",
    "RedisConfig",
    "DatabaseConfig",
    
    # Validation
    "validate_payload",
    "ValidationError",
]

