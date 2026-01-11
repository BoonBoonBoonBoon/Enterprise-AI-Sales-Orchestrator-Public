"""Persistence service layer for database operations.

This service layer provides:
- **Unified Persistence Interface**: PersistenceService class with support for multiple adapters
- **Adapter Implementations**: Supabase, in-memory, and custom adapters
- **Permission Model**: Table-level read/write allowlists for security
- **Metrics & Observability**: Built-in operation counters and latency tracking
- **RAG Context Assembly**: Build prompt contexts from persistence data

Exported Components
-------------------
- PersistenceService: Main facade for database operations
- PersistenceAdapter: Protocol for implementing new adapters
- SupabaseAdapter: Production adapter using Supabase
- InMemoryAdapter: Test adapter using in-memory storage
- ReadOnlyPersistenceFacade: Limited interface for read-only flows
- RAGContext: Data structure for LLM prompt assembly
- build_rag_context(): Utility to build context from persistence queries
- build_supabase_service(): Factory to create Supabase-backed service
- Metrics functions: inc(), observe(), snapshot()
- Exception classes: PersistenceError, TableNotAllowedError, etc.

Design Principles
-----------------
- **Separation of Concerns**: Adapter handles transport; service handles policy
- **Type Safety**: Protocol-based adapter interface
- **Security**: Allowlist-based access control per operation
- **Testability**: In-memory adapter for development/testing
- **Observability**: Metrics collection without external dependencies

Configuration
--------------
Services configured via environment variables (see config.py):
- SUPABASE_URL: Supabase project URL
- SUPABASE_SERVICE_KEY: Service role key
- PERSIST_ALLOWED_TABLES: Comma-separated table allowlist
- RAG_DEEP_DEBUG: Enable detailed operation tracing

Examples
--------
```python
from services.persistence import PersistenceService, SupabaseAdapter

# Create service
adapter = SupabaseAdapter(url, key)
service = PersistenceService(adapter, write_allowlist=["clients", "leads"])

# Write
record = service.write("clients", {"name": "Acme Corp", "domain": "acme.com"})

# Query
results = service.query("clients", filters={"domain": "%acme%"})

# Read-only facade
readonly = ReadOnlyPersistenceFacade(service)
context = build_rag_context(readonly)
```
"""

from services.persistence.service import (
    PersistenceService,
    PersistenceAdapter,
    ReadOnlyPersistenceFacade,
    build_supabase_service,
)
from services.persistence.adapters import InMemoryAdapter, SupabaseAdapter
from services.persistence.exceptions import (
    PersistenceError,
    PersistencePermissionError,
    TableNotAllowedError,
    ValidationError,
    AdapterError,
)
from services.persistence.rag_context import RAGContext, build_rag_context
from services.persistence import metrics

__all__ = [
    # Service
    "PersistenceService",
    "PersistenceAdapter",
    "ReadOnlyPersistenceFacade",
    "build_supabase_service",
    # Adapters
    "InMemoryAdapter",
    "SupabaseAdapter",
    # Exceptions
    "PersistenceError",
    "PersistencePermissionError",
    "TableNotAllowedError",
    "ValidationError",
    "AdapterError",
    # RAG Context
    "RAGContext",
    "build_rag_context",
    # Metrics
    "metrics",
]
