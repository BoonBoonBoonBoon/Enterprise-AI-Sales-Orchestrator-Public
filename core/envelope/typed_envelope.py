"""Production-ready envelope system for agent-to-agent messaging.

Supports:
- Typed metadata with correlation IDs, priorities, and multi-tenancy
- Enum-based status for type safety
- Retry/DLQ lifecycle tracking
- Optional distributed tracing
- Context forwarding for multi-agent pipelines
"""
from __future__ import annotations

from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import uuid
import json


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Status(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    RETRY = "retry"
    DLQ = "dlq"


class Metadata(BaseModel):
    """Core routing and tracking metadata"""
    # Identity
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    correlation_id: Optional[str] = None  # Links related messages across streams
    
    # Routing
    source: str  # e.g., "orchestrator", "rag_worker", "copywriter"
    destination: Optional[str] = None  # Target stream/worker if known
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    # Context
    req_id: Optional[str] = None  # Original client request ID
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    campaign_id: Optional[str] = None
    
    # Operations
    priority: Priority = Priority.NORMAL
    retry_count: int = 0
    max_retries: int = 3
    tags: Dict[str, str] = Field(default_factory=dict)

    # Debug (optional): keep short to avoid token bloat.
    # Use for brief, non-sensitive reasoning summaries (NOT chain-of-thought).
    debug: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True


class TraceSpan(BaseModel):
    """Optional distributed tracing span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    service_name: str
    duration_ms: Optional[float] = None


class Envelope(BaseModel):
    """Universal message envelope for all streams"""
    metadata: Metadata
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: Status = Status.PENDING
    error: Optional[str] = None
    error_code: Optional[str] = None  # e.g., "23505" for duplicate key
    warnings: List[str] = Field(default_factory=list)
    trace: Optional[TraceSpan] = None
    
    @validator('status', pre=True)
    def normalize_status(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v
    
    def to_json(self) -> str:
        """Serialize for XADD"""
        return self.model_dump_json(exclude_none=True)
    
    def mark_processed(self) -> "Envelope":
        """Mark as successfully processed"""
        self.metadata.processed_at = datetime.utcnow()
        self.status = Status.SUCCESS
        return self
    
    def mark_error(self, error: str, code: Optional[str] = None) -> "Envelope":
        """Mark as failed"""
        self.metadata.processed_at = datetime.utcnow()
        self.status = Status.ERROR
        self.error = error
        self.error_code = code
        return self
    
    def increment_retry(self) -> "Envelope":
        """Bump retry count; check if should go to DLQ"""
        self.metadata.retry_count += 1
        if self.metadata.retry_count >= self.metadata.max_retries:
            self.status = Status.DLQ
        else:
            self.status = Status.RETRY
        return self
    
    class Config:
        use_enum_values = True


# ============ Builders ============

def task(
    source: str,
    task_id: str,
    payload: Dict[str, Any],
    destination: Optional[str] = None,
    priority: Priority = Priority.NORMAL,
    correlation_id: Optional[str] = None,
    **metadata_overrides
) -> Envelope:
    """Create a new task envelope"""
    return Envelope(
        metadata=Metadata(
            source=source,
            task_id=task_id,
            destination=destination,
            priority=priority,
            correlation_id=correlation_id or str(uuid.uuid4()),
            **metadata_overrides
        ),
        payload=payload,
        status=Status.PENDING
    )


def result(
    original: Envelope,
    payload: Dict[str, Any],
    source: str
) -> Envelope:
    """Create a result envelope from an original task"""
    return Envelope(
        metadata=Metadata(
            message_id=str(uuid.uuid4()),
            task_id=original.metadata.task_id,
            correlation_id=original.metadata.correlation_id,
            source=source,
            req_id=original.metadata.req_id,
            user_id=original.metadata.user_id,
            tenant_id=original.metadata.tenant_id,
            campaign_id=original.metadata.campaign_id,
            tags=original.metadata.tags,
            debug=original.metadata.debug,
        ),
        payload=payload,
        status=Status.SUCCESS
    )


def error(
    original: Envelope,
    error_msg: str,
    source: str,
    code: Optional[str] = None
) -> Envelope:
    """Create an error envelope from an original task"""
    return Envelope(
        metadata=Metadata(
            message_id=str(uuid.uuid4()),
            task_id=original.metadata.task_id,
            correlation_id=original.metadata.correlation_id,
            source=source,
            req_id=original.metadata.req_id,
            user_id=original.metadata.user_id,
            tenant_id=original.metadata.tenant_id,
            campaign_id=original.metadata.campaign_id,
            retry_count=original.metadata.retry_count,
            max_retries=original.metadata.max_retries,
            tags=original.metadata.tags,
            debug=original.metadata.debug,
        ),
        payload=original.payload,
        status=Status.ERROR,
        error=error_msg,
        error_code=code
    )


# ============ Parsers ============

def from_redis_message(fields: Dict[str, Any]) -> Envelope:
    """Parse envelope from Redis stream message fields"""
    # Handle both string and bytes keys from Redis
    data = fields.get("data") or fields.get(b"data") or "{}"
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return Envelope.model_validate_json(data)


def to_redis_fields(envelope: Envelope) -> Dict[str, str]:
    """Convert envelope to Redis XADD fields dict"""
    return {"data": envelope.to_json()}
