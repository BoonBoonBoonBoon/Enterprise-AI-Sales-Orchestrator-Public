"""Type-safe schemas for RAG agent task and result payloads."""
from __future__ import annotations

from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class FilterOperator(str, Enum):
    """Supported filter operators for database queries"""
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    ILIKE = "ilike"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class QuerySpec(BaseModel):
    """Database query specification"""
    table: str = Field(..., min_length=1, max_length=100, description="Target table name")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filter conditions")
    limit: int = Field(default=100, ge=1, le=10000, description="Maximum rows to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    columns: Optional[List[str]] = Field(None, description="Columns to select (None = all)")
    order_by: Optional[str] = Field(None, description="Column to sort by")
    descending: bool = Field(default=False, description="Sort descending if True")
    
    @validator('table')
    def validate_table_name(cls, v):
        """Ensure table name is safe (alphanumeric + underscore)"""
        if not v.replace('_', '').isalnum():
            raise ValueError(f"Invalid table name: {v}. Must be alphanumeric with underscores")
        return v
    
    @validator('columns')
    def validate_columns(cls, v):
        """Ensure column names are safe"""
        if v:
            for col in v:
                if not col.replace('_', '').replace('.', '').isalnum():
                    raise ValueError(f"Invalid column name: {col}")
        return v
    
    @validator('filters')
    def validate_filters(cls, v):
        """Ensure filters have safe column names"""
        for key in v.keys():
            # Allow nested keys for operator syntax: {"email": {"ilike": "%test%"}}
            col = key.split('.')[0]  # Handle joins: "leads.email"
            if not col.replace('_', '').isalnum():
                raise ValueError(f"Invalid filter column: {key}")
        return v


class ForwardSpec(BaseModel):
    """Specification for forwarding results to another agent"""
    agent: str = Field(..., description="Target agent (e.g., 'copywriter', 'persistence')")
    campaign_context: Dict[str, Any] = Field(default_factory=dict, description="Campaign metadata")
    instructions: Dict[str, Any] = Field(default_factory=dict, description="Agent-specific instructions")
    transform: Optional[str] = Field(None, description="Data transformation to apply before forwarding")


class RAGTaskPayload(BaseModel):
    """Payload for RAG query tasks"""
    query: QuerySpec = Field(..., description="Database query specification")
    forward_to: Optional[ForwardSpec] = Field(None, description="Forward results to another agent")
    cache_key: Optional[str] = Field(None, description="Cache key for result deduplication")
    timeout_ms: int = Field(default=30000, ge=100, le=300000, description="Query timeout in milliseconds")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "query": {
                        "table": "leads",
                        "filters": {"email": {"ilike": "%@example.com"}},
                        "limit": 50,
                        "order_by": "created_at",
                        "descending": True
                    },
                    "forward_to": {
                        "agent": "copywriter",
                        "campaign_context": {"campaign_id": "camp-123", "variant": "A"},
                        "instructions": {"template": "followup_email", "tone": "professional"}
                    }
                }
            ]
        }


class RecordProvenance(BaseModel):
    """Provenance metadata for retrieved records"""
    source: str = Field(..., description="Data source (e.g., 'supabase.leads')")
    row_id: Any = Field(..., description="Primary key of the record")
    row_hash: str = Field(..., description="SHA256 hash of record content")
    retrieved_at: str = Field(..., description="ISO 8601 timestamp of retrieval")
    query_filters: Dict[str, Any] = Field(default_factory=dict, description="Filters used to retrieve")
    raw_row: Optional[Dict[str, Any]] = Field(None, description="Full raw record (optional, for debugging)")


class RAGResultPayload(BaseModel):
    """Payload for RAG query results"""
    records: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved records")
    count: int = Field(..., ge=0, description="Number of records returned")
    table: str = Field(..., description="Source table")
    query_time_ms: Optional[float] = Field(None, description="Query execution time")
    cached: bool = Field(default=False, description="True if result was cached")
    provenance: Optional[List[RecordProvenance]] = Field(None, description="Provenance for each record")
    
    @validator('count')
    def validate_count_matches_records(cls, v, values):
        """Ensure count matches actual records length"""
        if 'records' in values and len(values['records']) != v:
            raise ValueError(f"Count {v} doesn't match records length {len(values['records'])}")
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "records": [
                        {"id": "lead-123", "email": "john@example.com", "name": "John Doe"},
                        {"id": "lead-456", "email": "jane@example.com", "name": "Jane Smith"}
                    ],
                    "count": 2,
                    "table": "leads",
                    "query_time_ms": 45.2,
                    "cached": False
                }
            ]
        }
