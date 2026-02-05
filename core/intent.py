"""Canonical Intent enum for classification.

All intent values across the system should use these enums
instead of hardcoded strings for type safety and consistency.
"""
from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    """
    Canonical intents recognized by the Manager and orchestrators.
    
    Using str as base allows comparison with string values:
        intent == Intent.INBOUND  # works
        intent == "inbound"       # also works when Intent is used
    """
    
    # ---- High-level routing intents (Manager → Tier 2) ----
    INBOUND = "inbound"
    """Inbound email received; route to LeadsOrchestrator for triage."""
    
    OUTREACH = "outreach"
    """Outreach campaign request; route to OutreachOrchestrator."""
    
    LEAD_ENRICHMENT = "lead_enrichment"
    """Lead enrichment/discovery request."""
    
    START_CAMPAIGN = "start_campaign"
    """Start or launch a campaign."""
    
    AUDIT = "audit"
    """Audit/QA/compliance request."""
    
    CONTROL = "control"
    """Control command (pause, resume, throttle, etc.)."""
    
    # ---- Shortcut intents (deterministic routing) ----
    SHORTCUT = "shortcut"
    """Shortcut-based routing bypassing LLM classification."""
    
    # ---- Specialized intents ----
    REPLY_EMAIL = "reply_email"
    """Generate and send a reply email."""
    
    QUALIFY_LEAD = "qualify_lead"
    """Qualify/score a lead."""
    
    LEAD_LOOKUP = "lead_lookup"
    """Look up lead information."""
    
    STORE_LEAD = "store_lead"
    """Store a lead in the database."""
    
    PROMOTE_LEAD = "promote_lead"
    """Promote staging lead to qualified lead."""
    
    # ---- Fallback ----
    UNKNOWN = "unknown"
    """Unknown intent; may trigger LLM fallback."""
    
    @classmethod
    def from_string(cls, value: str) -> "Intent":
        """
        Parse a string into an Intent enum.
        
        Args:
            value: String intent value (case-insensitive)
            
        Returns:
            Matching Intent enum or UNKNOWN if not found
        """
        if not value:
            return cls.UNKNOWN
        normalized = value.lower().strip()
        for member in cls:
            if member.value == normalized:
                return member
        return cls.UNKNOWN
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid intent."""
        return cls.from_string(value) != cls.UNKNOWN or value.lower() == "unknown"


# Convenience sets for grouping
ROUTING_INTENTS = frozenset({
    Intent.INBOUND,
    Intent.OUTREACH,
    Intent.LEAD_ENRICHMENT,
    Intent.START_CAMPAIGN,
    Intent.AUDIT,
    Intent.CONTROL,
})

ACTION_INTENTS = frozenset({
    Intent.REPLY_EMAIL,
    Intent.QUALIFY_LEAD,
    Intent.LEAD_LOOKUP,
    Intent.STORE_LEAD,
    Intent.PROMOTE_LEAD,
})


__all__ = ["Intent", "ROUTING_INTENTS", "ACTION_INTENTS"]
