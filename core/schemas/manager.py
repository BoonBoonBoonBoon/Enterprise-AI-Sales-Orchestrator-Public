from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UnifiedManagerRequest(BaseModel):
    """Unified input shape for Tier 1 Manager.

    Can be constructed from free text, JSON dicts, or webhook-like payloads.
    """

    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    subject: Optional[str] = None
    text: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    source: str = Field(default="unknown")  # e.g., "redis", "webhook", "cli"
    content_type: Optional[str] = None  # e.g., "application/json", "text/plain"
    meta: Dict[str, Any] = Field(default_factory=dict)


class ManagerDecision(BaseModel):
    """Decision produced by Tier 1: detected intent and downstream plan."""

    intent: str = "unknown"
    confidence: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    used_fallback: bool = False  # whether a routing fallback was applied
    context_depth: str = "shallow"  # "shallow" or "deep" (controls downstream planning)
    # downstream actions (Tier 2)
    orchestrators: List[str] = Field(default_factory=list)  # e.g. ["leads", "outreach"]
    tasks: List[Dict[str, Any]] = Field(default_factory=list)  # ready-to-enqueue task payloads
    correlation_id: Optional[str] = None


__all__ = [
    "UnifiedManagerRequest",
    "ManagerDecision",
]
