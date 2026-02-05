from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LeadResolution(BaseModel):
    status: str = Field(default="unknown")  # found|new|ambiguous|unknown
    lead_id: Optional[str] = None
    confidence: float = 0.0
    source: Optional[str] = None  # e.g., "deterministic_lookup", "rag"
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    # Full lead record when found (first_name, last_name, company, title, email, etc.)
    lead_data: Optional[Dict[str, Any]] = None


class ConversationSummary(BaseModel):
    conversation_id: Optional[str] = None
    summary: Optional[str] = None
    recent_messages: List[Dict[str, Any]] = Field(default_factory=list)
    last_message_at: Optional[str] = None


class Facts(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    intent: Optional[str] = None
    risk_flags: List[str] = Field(default_factory=list)
    extras: Dict[str, Any] = Field(default_factory=dict)


class ActionsTaken(BaseModel):
    stored: bool = False
    enriched: bool = False
    writes: List[str] = Field(default_factory=list)


class NextStep(BaseModel):
    delegate_to: List[str] = Field(default_factory=list)  # e.g., ["outbound"]
    reason: Optional[str] = None


class ReplyPacket(BaseModel):
    lead_resolution: LeadResolution = Field(default_factory=LeadResolution)
    conversation: ConversationSummary = Field(default_factory=ConversationSummary)
    facts: Facts = Field(default_factory=Facts)
    actions_taken: ActionsTaken = Field(default_factory=ActionsTaken)
    inbound_email_event: Dict[str, Any] = Field(default_factory=dict)
    recommended_strategy: Optional[str] = None
    next: NextStep = Field(default_factory=NextStep)
    # Debug: shows which tables were queried, in what order, and what was found
    query_trace: Optional[Dict[str, Any]] = None


__all__ = [
    "LeadResolution",
    "ConversationSummary",
    "Facts",
    "ActionsTaken",
    "NextStep",
    "ReplyPacket",
]
