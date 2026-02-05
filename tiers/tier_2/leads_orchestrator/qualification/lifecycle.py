"""Qualification lifecycle helpers.

Centralizes how QualificationScorer outputs map to persisted DB fields.

We intentionally keep this small and dependency-free so Tier-2 code can
consistently store `qualification_status` and related flags across:
- inbound auto-promotion
- manual qualify_lead intent
- fast-track writes to `leads`
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional


def normalize_qualification_status(decision: Optional[str]) -> str:
    """Normalize scorer decision into a safe persisted qualification_status.

    Expected scorer decisions:
    - qualified
    - nurture
    - disqualified
    - fast_track

    For unknown/empty values we default to "pending".
    """

    if not decision:
        return "pending"

    normalized = str(decision).strip().lower()
    if not normalized:
        return "pending"

    allowed = {"pending", "qualified", "nurture", "disqualified", "fast_track"}
    return normalized if normalized in allowed else "pending"


def build_staging_qualification_update(
    *,
    decision: Optional[str],
    promote: bool,
    score: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a minimal staging_leads update payload after scoring."""

    update: Dict[str, Any] = {
        "qualification_status": normalize_qualification_status(decision),
        "promotion_ready": bool(promote),
    }

    if isinstance(score, int):
        # Existing code stores completeness_score as 0-1 float.
        update["completeness_score"] = max(0.0, min(1.0, float(score) / 100.0))

    return update


def build_message_qualification_metadata(
    *,
    decision: Optional[str],
    score: Optional[int],
    signals: Optional[list],
    fast_track: bool,
) -> Dict[str, Any]:
    """Attach qualification metadata to message.metadata."""

    meta: Dict[str, Any] = {
        "decision": normalize_qualification_status(decision),
        "fast_track": bool(fast_track),
    }
    if isinstance(score, int):
        meta["score"] = score
    if isinstance(signals, list):
        meta["signals"] = signals[:10]
    return meta


def build_promotion_task_payload(
    *,
    staging_lead_id: str,
    decision: Optional[str],
    score: int,
    campaign_id: Optional[str],
    delegated_by: str,
    timestamp: str,
) -> Dict[str, Any]:
    """Build PersistenceAgent promote_staging_lead task payload."""

    return {
        "operation": "promote_staging_lead",
        "staging_lead_id": staging_lead_id,
        "lead_score": int(score),
        "campaign_id": campaign_id,
        "qualification_status": normalize_qualification_status(decision),
        "delegated_by": delegated_by,
        "timestamp": timestamp,
    }


def qualification_result_to_dict(result: Any) -> Dict[str, Any]:
    """Best-effort serialize QualificationResult for API responses."""

    try:
        return asdict(result)
    except Exception:
        if isinstance(result, dict):
            return result
        return {
            "score": getattr(result, "score", None),
            "decision": getattr(result, "decision", None),
            "promote": getattr(result, "promote", None),
            "fast_track": getattr(result, "fast_track", None),
            "signals": getattr(result, "signals", None),
            "reasoning": getattr(result, "reasoning", None),
        }
