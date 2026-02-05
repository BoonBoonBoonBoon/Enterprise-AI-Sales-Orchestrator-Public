"""Dashboard statistics endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from ..dependencies.auth import get_current_user, AuthUser
from ..dependencies.supabase import SupabaseClient, get_db

router = APIRouter(dependencies=[Depends(get_current_user)])


class DashboardStats(BaseModel):
    """Aggregated stats for the dashboard."""
    # Core metrics
    pending_drafts: int = 0
    drafts_approved_today: int = 0
    drafts_rejected_today: int = 0
    
    # Lead metrics
    total_leads: int = 0
    new_leads_today: int = 0
    active_conversations: int = 0
    
    # Email metrics
    emails_sent_today: int = 0
    emails_received_today: int = 0
    response_rate: float = 0.0
    
    # Mailbox status
    connected_mailboxes: int = 0
    mailbox_errors: int = 0


class LeadStatusBreakdown(BaseModel):
    """Breakdown of leads by status."""
    new: int = 0
    contacted: int = 0
    qualified: int = 0
    converted: int = 0
    lost: int = 0


class StatsResponse(BaseModel):
    """Full statistics response."""
    dashboard: DashboardStats
    lead_breakdown: LeadStatusBreakdown
    period_start: datetime
    period_end: datetime


@router.get("", response_model=StatsResponse)
async def get_stats(
    days: int = 1,
    user: AuthUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_db),
):
    """
    Get dashboard statistics for the current tenant.
    
    Args:
        days: Number of days to look back for "today" metrics (default 1)
    """
    now = datetime.utcnow()
    period_start = now - timedelta(days=days)
    period_start_iso = period_start.isoformat() + "Z"
    
    # ─────────────────────────────────────────────────────────────────
    # Draft counts
    # ─────────────────────────────────────────────────────────────────
    pending_drafts = await db.count("drafts", filters={"status": "pending"})
    approved_drafts = await db.count(
        "drafts",
        filters={
            "status": "approved",
            "approved_at": ("gte", period_start_iso),
        },
    )
    rejected_drafts = await db.count(
        "drafts",
        filters={
            "status": "rejected",
            "updated_at": ("gte", period_start_iso),
        },
    )
    
    # ─────────────────────────────────────────────────────────────────
    # Lead counts
    # ─────────────────────────────────────────────────────────────────
    total_leads = await db.count("leads")
    
    # Lead breakdown by status
    leads_new_today = await db.count(
        "leads",
        filters={
            "current_status": "new",
            "created_at": ("gte", period_start_iso),
        },
    )
    leads_new = await db.count("leads", filters={"current_status": "new"})
    leads_contacted = await db.count("leads", filters={"current_status": "contacted"})
    leads_qualified = await db.count("leads", filters={"current_status": "qualified"})
    leads_converted = await db.count("leads", filters={"current_status": "converted"})
    leads_lost = await db.count("leads", filters={"current_status": "lost"})
    
    # ─────────────────────────────────────────────────────────────────
    # Conversation counts
    # ─────────────────────────────────────────────────────────────────
    active_conversations = await db.count("conversations", filters={"status": "active"})
    
    # ─────────────────────────────────────────────────────────────────
    # Mailbox counts
    # ─────────────────────────────────────────────────────────────────
    connected_mailboxes = await db.count("mailboxes", filters={"is_active": True})
    disconnected_mailboxes = await db.count("mailboxes", filters={"is_active": False})

    # ─────────────────────────────────────────────────────────────────
    # Message counts
    # ─────────────────────────────────────────────────────────────────
    try:
        emails_sent_today = await db.count(
            "messages",
            filters={
                "direction": "outbound",
                "created_at": ("gte", period_start_iso),
            },
        )
        emails_received_today = await db.count(
            "messages",
            filters={
                "direction": "inbound",
                "created_at": ("gte", period_start_iso),
            },
        )
    except HTTPException:
        # Fallback for legacy schema that uses sender_type instead of direction
        emails_sent_today = await db.count(
            "messages",
            filters={
                "sender_type": "agent",
                "created_at": ("gte", period_start_iso),
            },
        )
        emails_received_today = await db.count(
            "messages",
            filters={
                "sender_type": "lead",
                "created_at": ("gte", period_start_iso),
            },
        )
    response_rate = (
        float(emails_received_today) / float(emails_sent_today)
        if emails_sent_today
        else 0.0
    )
    
    # ─────────────────────────────────────────────────────────────────
    # Build response
    # ─────────────────────────────────────────────────────────────────
    dashboard = DashboardStats(
        pending_drafts=pending_drafts,
        drafts_approved_today=approved_drafts,
        drafts_rejected_today=rejected_drafts,
        total_leads=total_leads,
        new_leads_today=leads_new_today,
        active_conversations=active_conversations,
        emails_sent_today=emails_sent_today,
        emails_received_today=emails_received_today,
        response_rate=response_rate,
        connected_mailboxes=connected_mailboxes,
        mailbox_errors=disconnected_mailboxes,
    )
    
    lead_breakdown = LeadStatusBreakdown(
        new=leads_new,
        contacted=leads_contacted,
        qualified=leads_qualified,
        converted=leads_converted,
        lost=leads_lost,
    )
    
    return StatsResponse(
        dashboard=dashboard,
        lead_breakdown=lead_breakdown,
        period_start=period_start,
        period_end=now,
    )


@router.get("/quick")
async def get_quick_stats(
    user: AuthUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_db),
):
    """
    Get minimal stats for dashboard header.
    Optimized for speed - only essential counts.
    """
    pending_drafts = await db.count("drafts", filters={"status": "pending"})
    total_leads = await db.count("leads")
    connected_mailboxes = await db.count("mailboxes", filters={"is_active": True})
    
    return {
        "pending_drafts": pending_drafts,
        "total_leads": total_leads,
        "connected_mailboxes": connected_mailboxes,
    }
