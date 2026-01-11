"""Type-safe schemas for Persistence agent task and result payloads."""
from __future__ import annotations

from typing import Any, Dict, Optional, List, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum


class WriteOperation(str, Enum):
    """Supported write operations"""
    INSERT = "insert"
    UPDATE = "update"
    UPSERT = "upsert"
    DELETE = "delete"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies"""
    ERROR = "error"  # Fail on conflict
    IGNORE = "ignore"  # Skip conflicting rows
    UPDATE = "update"  # Update on conflict
    MERGE = "merge"  # Merge fields on conflict


class WriteSpec(BaseModel):
    """Specification for a database write operation"""
    table: str = Field(..., min_length=1, max_length=100, description="Target table name")
    operation: WriteOperation = Field(..., description="Write operation type")
    data: List[Dict[str, Any]] = Field(..., min_items=1, description="Records to write")
    conflict_columns: Optional[List[str]] = Field(None, description="Columns for conflict detection (upsert)")
    conflict_resolution: ConflictResolution = Field(default=ConflictResolution.ERROR, description="How to handle conflicts")
    returning: Optional[List[str]] = Field(None, description="Columns to return after write")
    
    @validator('table')
    def validate_table_name(cls, v):
        """Ensure table name is safe"""
        if not v.replace('_', '').isalnum():
            raise ValueError(f"Invalid table name: {v}")
        return v
    
    @validator('data')
    def validate_data_not_empty(cls, v):
        """Ensure at least one record"""
        if not v:
            raise ValueError("Data cannot be empty")
        return v
    
    @validator('conflict_columns')
    def validate_conflict_columns(cls, v, values):
        """Ensure conflict columns specified for upsert"""
        if 'operation' in values and values['operation'] == WriteOperation.UPSERT:
            if not v:
                raise ValueError("conflict_columns required for upsert operation")
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "table": "leads",
                    "operation": "upsert",
                    "data": [
                        {"id": "lead-123", "email": "john@example.com", "name": "John Doe"},
                        {"id": "lead-456", "email": "jane@example.com", "name": "Jane Smith"}
                    ],
                    "conflict_columns": ["id"],
                    "conflict_resolution": "update",
                    "returning": ["id", "updated_at"]
                }
            ]
        }


class ValidationRule(BaseModel):
    """Data validation rule"""
    field: str = Field(..., description="Field to validate")
    rule: str = Field(..., description="Validation rule (required, email, min_length, etc.)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Rule parameters")
    error_message: Optional[str] = Field(None, description="Custom error message")


class PersistenceTaskPayload(BaseModel):
    """Payload for persistence tasks"""
    write: WriteSpec = Field(..., description="Write operation specification")
    validation_rules: List[ValidationRule] = Field(default_factory=list, description="Pre-write validation")
    timeout_ms: int = Field(default=30000, ge=100, le=300000, description="Write timeout")
    atomic: bool = Field(default=True, description="Use transaction (all-or-nothing)")
    dry_run: bool = Field(default=False, description="Validate without writing")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "write": {
                        "table": "leads",
                        "operation": "insert",
                        "data": [{"email": "test@example.com", "name": "Test User"}],
                        "conflict_resolution": "error"
                    },
                    "validation_rules": [
                        {"field": "email", "rule": "email", "error_message": "Invalid email format"}
                    ],
                    "atomic": True,
                    "dry_run": False
                }
            ]
        }


class WriteResult(BaseModel):
    """Result of a single write operation"""
    operation: WriteOperation = Field(..., description="Operation performed")
    rows_affected: int = Field(..., ge=0, description="Number of rows affected")
    rows_returned: Optional[List[Dict[str, Any]]] = Field(None, description="Returned rows (if requested)")
    conflicts_detected: int = Field(default=0, ge=0, description="Number of conflicts encountered")
    conflicts_resolved: int = Field(default=0, ge=0, description="Number of conflicts resolved")
    skipped_rows: int = Field(default=0, ge=0, description="Rows skipped due to conflicts")


class PersistenceResultPayload(BaseModel):
    """Payload for persistence results"""
    write_result: WriteResult = Field(..., description="Write operation result")
    table: str = Field(..., description="Table written to")
    write_time_ms: Optional[float] = Field(None, description="Write execution time")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors encountered")
    dry_run: bool = Field(default=False, description="True if this was a dry run")
    transaction_id: Optional[str] = Field(None, description="Database transaction ID")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "write_result": {
                        "operation": "upsert",
                        "rows_affected": 2,
                        "conflicts_detected": 1,
                        "conflicts_resolved": 1,
                        "skipped_rows": 0
                    },
                    "table": "leads",
                    "write_time_ms": 125.3,
                    "validation_errors": [],
                    "dry_run": False
                }
            ]
        }


# --------------------------- Compound Operations --------------------------- #


class PersistenceOperation(str, Enum):
    """Supported persistence operations (single or compound)."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    UPSERT = "upsert"
    QUERY = "query"
    COMPOUND = "compound"


class StepOperation(str, Enum):
    """Operations available within a compound step."""
    CREATE = "create"
    UPDATE = "update"
    UPSERT = "upsert"
    DELETE = "delete"


class ConditionalCheck(BaseModel):
    """Conditional execution gate for a step."""

    field: str = Field(..., description="Field to check (can be $ref:step.field)")
    operator: str = Field(
        default="exists",
        description="exists, not_exists, equals, not_equals, gt, lt, gte, lte, in, not_in",
    )
    value: Optional[Any] = Field(
        default=None, description="Comparison value (not needed for exists/not_exists)"
    )


class TableStep(BaseModel):
    """A single step in a compound operation."""

    step_name: str = Field(..., description="Unique name for referencing this step output")
    table: str = Field(..., description="Target table name")
    operation: StepOperation = Field(..., description="Operation type")

    # Data for create/upsert/update (dict or list of dicts for batch)
    data: Optional[Any] = Field(
        default=None,
        description="Payload for create/upsert/update. Use $ref:step.field for FK references. Supports list for batch.",
    )

    # Where clause for update/delete (dict with refs allowed)
    where: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filter for update/delete (e.g., {'id': '$ref:lead.id'}). Required for delete.",
    )

    # Upsert conflict columns
    match_on: Optional[List[str]] = Field(
        default=None,
        description="For upsert: columns to match on (e.g., ['email']).",
    )

    # Optional condition
    condition: Optional[ConditionalCheck] = Field(
        default=None, description="If set, step executes only when condition passes",
    )

    # Error handling strategy per step
    on_error: str = Field(
        default="fail",
        description="fail (stop), skip (skip step), warn (log & continue)",
    )

    # Optional projection for internal queries
    select: Optional[List[str]] = Field(
        default=None, description="Projection for internal query/update flows",
    )

    @validator("data", "where", pre=True)
    def validate_dict_or_list(cls, value):
        if value is None:
            return value
        if isinstance(value, (dict, list)):
            return value
        raise ValueError("data/where must be a dict or list of dicts")


class CompoundPayload(BaseModel):
    """Compound operation across any number of tables with FK resolution."""

    operation: Literal["compound"] = "compound"
    steps: List[TableStep] = Field(
        ..., min_length=1, description="Ordered list of table steps respecting FK dependencies",
    )
    rollback_on_failure: bool = Field(
        default=True,
        description="If true, attempt to rollback creates/upserts on failure",
    )
    continue_on_skip: bool = Field(
        default=True,
        description="If false, stop when a step is skipped (condition or on_error=skip)",
    )
    transaction_id: Optional[str] = Field(
        default=None, description="Optional transaction/correlation id for tracing",
    )

    @validator("steps")
    def validate_unique_step_names(cls, steps: List[TableStep]):
        names = [s.step_name for s in steps]
        if len(names) != len(set(names)):
            raise ValueError("All step_name values must be unique")
        return steps


class StepResult(BaseModel):
    """Result of a single compound step."""

    step_name: str
    table: str
    operation: str
    status: str  # success, skipped, failed, rolled_back
    records_affected: int = 0
    output: Optional[Any] = None
    error: Optional[str] = None
    skipped_reason: Optional[str] = None


class CompoundResult(BaseModel):
    """Result of a compound operation."""

    success: bool
    transaction_id: Optional[str] = None
    total_steps: int
    completed_steps: int
    skipped_steps: int
    failed_step: Optional[str] = None
    error: Optional[str] = None
    step_results: List[StepResult] = Field(default_factory=list)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    rollback_performed: bool = False
    rollback_results: List[StepResult] = Field(default_factory=list)
