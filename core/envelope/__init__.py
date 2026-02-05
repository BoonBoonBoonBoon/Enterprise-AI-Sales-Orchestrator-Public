"""
Typed Envelope System - Universal message format for agent communication.

Provides two envelope systems:

1. **Typed Envelope (New)**: Production-ready typed system with:
   - Envelope: Universal message container with metadata
   - Metadata: Routing, tracking, and context information
   - Status: Standardized status enum for message lifecycle
   - Priority: Priority levels for message processing
   - Builders: Factory functions for creating task, result, and error envelopes
   - Serialization: JSON serialization for Redis Streams

2. **Legacy Envelope (Compatibility)**: Lightweight dataclass system:
   - Envelope: Simple dataclass envelope
   - make_envelope: Factory function
   - validate_envelope: Validation helper
   - Supports both pydantic (strict) and fallback (fast) modes

Architecture:
- typed_envelope.py: New production system (Pydantic BaseModel)
- envelope.py: Legacy system (dataclass)
- Both systems can coexist during migration
- Gradual migration from envelope.py to typed_envelope.py recommended

Usage:

    # New typed envelope system (recommended)
    from core.envelope import Envelope, task, result, error, Status
    
    # Create task
    task_env = task(
        source="orchestrator",
        task_id="t123",
        payload={"lead_id": "l456"},
        priority=Priority.HIGH
    )
    
    # Create result
    result_env = result(
        original=task_env,
        payload={"enriched_data": {...}},
        source="rag_agent"
    )
    
    # Legacy envelope system (backward compatibility)
    from core.envelope.envelope import Envelope as LegacyEnvelope, make_envelope
    
    env = make_envelope(
        source="rag_agent",
        records=[{"id": 1, "name": "Acme"}],
        task_id="t123"
    )
"""

from .typed_envelope import (
    Envelope,
    Metadata,
    Status,
    Priority,
    TraceSpan,
    task,
    result,
    error,
    from_redis_message,
    to_redis_fields,
    normalize_envelope,
)

# Also expose legacy envelope for compatibility
from . import envelope as legacy_envelope

__all__ = [
    # Typed envelope (new)
    "Envelope",
    "Metadata",
    "Status",
    "Priority",
    "TraceSpan",
    "task",
    "result",
    "error",
    "from_redis_message",
    "to_redis_fields",
    "normalize_envelope",
    # Legacy envelope (compatibility)
    "legacy_envelope",
]
