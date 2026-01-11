"""Pydantic validators for ChannelSequencerAgent."""
from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Channel(str):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    VOICE = "voice"


class SequenceStep(BaseModel):
    channel: str = Field(..., description="Delivery channel")
    to_email: Optional[str] = Field(None, description="Recipient email for email channel")
    subject: Optional[str] = Field(None, description="Email subject (required for email)")
    body: Optional[str] = Field(None, description="Email body (required for email)")
    from_email: Optional[str] = Field(None, description="Override sender; defaults to configured Gmail sender")
    template_id: Optional[str] = Field(None, description="Content template reference")
    delay_minutes: int = Field(default=0, ge=0, description="Delay from now in minutes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Channel-specific metadata")


class SequenceRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant identifier")
    lead_id: Optional[str] = Field(None, description="Target lead identifier (optional for campaign-level sequencing)")
    steps: List[SequenceStep] = Field(default_factory=list, description="Ordered channel steps")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context for templates and routing")


class SequenceResult(BaseModel):
    status: str = Field(..., description="Result status: scheduled|sent|error")
    dispatched_channels: List[str] = Field(default_factory=list, description="Channels dispatched")
    deliveries: List[Dict[str, Any]] = Field(default_factory=list, description="Per-channel delivery details")
    error: Optional[str] = Field(None, description="Error message if failed")
