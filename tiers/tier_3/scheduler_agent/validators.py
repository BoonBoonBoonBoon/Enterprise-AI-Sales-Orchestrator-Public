"""Pydantic validators for SchedulerAgent."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CalendarProvider(str):
    GOOGLE = "google"
    OUTLOOK = "outlook"
    ICAL = "ical"


class Attendee(BaseModel):
    email: str = Field(..., description="Attendee email")
    name: Optional[str] = Field(None, description="Attendee display name")


class ScheduleRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant identifier")
    event_title: str = Field(..., description="Event title")
    start_time: datetime = Field(..., description="Start time (UTC)")
    end_time: datetime = Field(..., description="End time (UTC)")
    attendees: List[Attendee] = Field(default_factory=list, description="List of attendees")
    provider: str = Field(default=CalendarProvider.GOOGLE, description="Calendar provider")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    conference_link: Optional[str] = Field(None, description="Pre-created meeting link")


class ScheduleResult(BaseModel):
    status: str = Field(..., description="Result status: success|error")
    event_id: Optional[str] = Field(None, description="External calendar event ID")
    provider: Optional[str] = Field(None, description="Calendar provider")
    error: Optional[str] = Field(None, description="Error message if failed")
