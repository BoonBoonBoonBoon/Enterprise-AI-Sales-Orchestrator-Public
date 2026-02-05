"""Lead management endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

from ..dependencies.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


class LeadStatus(str, Enum):
    NEW = "new"
    NURTURING = "nurturing"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"


class LeadSource(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    REFERRAL = "referral"


class Lead(BaseModel):
    id: str
    name: str
    email: str
    company: Optional[str] = None
    role: Optional[str] = None
    status: LeadStatus
    score: int
    source: LeadSource
    last_contact: Optional[datetime] = None
    conversations: int = 0
    created_at: datetime


class LeadListResponse(BaseModel):
    leads: List[Lead]
    total: int
    page: int
    page_size: int


class LeadStats(BaseModel):
    total: int
    new: int
    nurturing: int
    qualified: int
    disqualified: int


# Mock data
MOCK_LEADS = [
    Lead(
        id="lead_1",
        name="Sarah Johnson",
        email="sarah@acme.com",
        company="Acme Corp",
        role="VP of Business Development",
        status=LeadStatus.QUALIFIED,
        score=85,
        source=LeadSource.INBOUND,
        last_contact=datetime.now(),
        conversations=4,
        created_at=datetime.now(),
    ),
    Lead(
        id="lead_2",
        name="Mike Chen",
        email="mike@startup.io",
        company="Startup.io",
        role="CTO",
        status=LeadStatus.NEW,
        score=72,
        source=LeadSource.INBOUND,
        last_contact=datetime.now(),
        conversations=1,
        created_at=datetime.now(),
    ),
]


@router.get("", response_model=LeadListResponse)
async def list_leads(
    status: Optional[LeadStatus] = None,
    source: Optional[LeadSource] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List leads for the current tenant.
    
    TODO: Query from Supabase with tenant_id filter + search
    """
    leads = MOCK_LEADS

    if status:
        leads = [l for l in leads if l.status == status]
    if source:
        leads = [l for l in leads if l.source == source]
    if search:
        search_lower = search.lower()
        leads = [
            l for l in leads
            if search_lower in l.name.lower()
            or search_lower in l.email.lower()
            or (l.company and search_lower in l.company.lower())
        ]

    return LeadListResponse(
        leads=leads,
        total=len(leads),
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=LeadStats)
async def get_lead_stats():
    """Get lead statistics for the current tenant."""
    return LeadStats(
        total=len(MOCK_LEADS),
        new=len([l for l in MOCK_LEADS if l.status == LeadStatus.NEW]),
        nurturing=len([l for l in MOCK_LEADS if l.status == LeadStatus.NURTURING]),
        qualified=len([l for l in MOCK_LEADS if l.status == LeadStatus.QUALIFIED]),
        disqualified=len([l for l in MOCK_LEADS if l.status == LeadStatus.DISQUALIFIED]),
    )


@router.get("/{lead_id}", response_model=Lead)
async def get_lead(lead_id: str):
    """Get a specific lead by ID."""
    for lead in MOCK_LEADS:
        if lead.id == lead_id:
            return lead
    raise HTTPException(status_code=404, detail="Lead not found")


@router.patch("/{lead_id}/status")
async def update_lead_status(lead_id: str, status: LeadStatus):
    """Update lead status."""
    return {
        "message": "Lead status updated",
        "lead_id": lead_id,
        "status": status,
    }
