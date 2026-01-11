"""Small JSON envelope helpers for agent-to-agent communication.

This module provides a compact Envelope dataclass and a couple of small
helper functions to produce and validate envelopes exchanged between
agents. Keep envelopes minimal by default and include full raw rows only
when explicitly requested (`include_raw=True`).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import hashlib

# Optional pydantic support: if available, use shared models in agent.utils.schemas
try:
    import pydantic  # type: ignore
    from agent.utils import schemas  # our optional schema module
    _HAS_PYDANTIC = True
except Exception:
    _HAS_PYDANTIC = False


def _now_iso() -> str:
    # Use timezone-aware UTC timestamps to avoid deprecation warnings
    return datetime.now(timezone.utc).isoformat()


def make_metadata(source: str, task_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "source": source,
        "task_id": task_id,
        "retrieved_at": _now_iso(),
        "filters": filters or {},
    }


def _row_hash(row: Dict[str, Any]) -> str:
    return hashlib.sha256(repr(sorted(row.items())).encode("utf-8")).hexdigest()


@dataclass
class Envelope:
    """Dataclass representing a standard agent-to-agent JSON envelope.

    Fields:
    - metadata: contains source, task_id, retrieved_at, filters
    - records: list of record dicts; each record will have a `provenance` key
    - status: e.g., SUCCESS, NO_RESULTS, ERROR
    - error: optional error message

    Usage:
        env = Envelope.from_records('supabase.leads', records, task_id='t1')
        s = env.to_json()

    # Minimal class. Extend with JSON Schema or pydantic for stricter validation if needed.
    """

    metadata: Dict[str, Any]
    records: List[Dict[str, Any]]
    status: str = "SUCCESS"
    error: Optional[str] = None

    @classmethod
    def from_records(cls, source: str, records: Optional[List[Dict[str, Any]]] = None, task_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None, include_raw: bool = False) -> "Envelope":
        records = records or []
        metadata = make_metadata(source, task_id=task_id, filters=filters)
        now = metadata["retrieved_at"]
        out_records: List[Dict[str, Any]] = []
        for r in records:
            rec = dict(r)
            prov = {
                "source": source,
                "row_id": r.get("id"),
                "row_hash": _row_hash(r),
                "retrieved_at": now,
            }
            if include_raw:
                prov["raw_row"] = dict(r)
            rec["provenance"] = prov
            out_records.append(rec)

        status = "SUCCESS" if records else "NO_RESULTS"
        return cls(metadata=metadata, records=out_records, status=status, error=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata,
            "records": self.records,
            "status": self.status,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Envelope":
        return cls(metadata=d.get("metadata", {}), records=d.get("records", []), status=d.get("status", "SUCCESS"), error=d.get("error"))

    @classmethod
    def from_json(cls, s: str) -> "Envelope":
        return cls.from_dict(json.loads(s))

    def validate(self) -> bool:
        return validate_envelope(self.to_dict())


def make_envelope(source: str, records: Optional[list] = None, task_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None, include_raw: bool = False) -> Dict[str, Any]:
    # Convenience wrapper that returns a plain dict envelope.
    env = Envelope.from_records(source, records=records, task_id=task_id, filters=filters, include_raw=include_raw)
    return env.to_dict()


def validate_envelope(env: Dict[str, Any]) -> bool:
    # If pydantic models are available, use them for stricter validation.
    if _HAS_PYDANTIC:
        try:
            # schemas.EnvelopeModel may support model_validate (pydantic v2) or parse_obj (v1)
            if hasattr(schemas.EnvelopeModel, "model_validate"):
                schemas.EnvelopeModel.model_validate(env)
            else:
                schemas.EnvelopeModel.parse_obj(env)
            # quick structural check for provenance inside records
            if isinstance(env.get("records"), list) and env["records"]:
                first = env["records"][0]
                if "provenance" not in first:
                    return False
            return True
        except Exception:
            return False

    # Fallback: minimal structural checks (fast, dependency-free)
    if not isinstance(env, dict):
        return False
    if "metadata" not in env or "records" not in env:
        return False
    return True


def to_json(env: Dict[str, Any]) -> str:
    return json.dumps(env, default=str)


def from_json(s: str) -> Dict[str, Any]:
    return json.loads(s)
