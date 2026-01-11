"""Optional pydantic models for Envelope validation.

This module is optional: the codebase should work without pydantic installed.
When pydantic is available, `agent.utils.envelope.validate_envelope` will import
these models and use them for stricter validation.
"""
from typing import Any, Dict, List, Optional

try:
    # Support both pydantic v1 and v2 styles minimally
    from pydantic import BaseModel
except Exception:  # pragma: no cover - optional dependency
    BaseModel = object  # type: ignore


class ProvenanceModel(BaseModel):
    source: str
    row_id: Optional[str] = None
    row_hash: Optional[str] = None
    retrieved_at: Optional[str] = None


class RecordModel(BaseModel):
    provenance: ProvenanceModel


class EnvelopeModel(BaseModel):
    metadata: Dict[str, Any]
    records: List[Dict[str, Any]]
    status: Optional[str] = "SUCCESS"
    error: Optional[str] = None
