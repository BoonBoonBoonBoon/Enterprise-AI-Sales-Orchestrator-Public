"""Draft management endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum
import os
import uuid

from core.envelope import task as create_task_envelope
from core.envelope import to_redis_fields, Priority
from services.redis import RedisStreamsClient, config as redis_streams
from ..dependencies.auth import get_current_user, AuthUser
from ..dependencies.supabase import SupabaseClient, get_db

router = APIRouter(dependencies=[Depends(get_current_user)])


def _resolve_tenant_id(user: AuthUser) -> str:
    return (
        user.tenant_id
        or os.getenv("TENANT_ID")
        or os.getenv("REDIS_NAMESPACE")
        or "agentic-dev"
    )


def _enqueue_outbound_task(
    *,
    tenant_id: str,
    user: AuthUser,
    goal: str,
    data: dict,
    priority: Priority,
    correlation_id: Optional[str] = None,
) -> str:
    client = RedisStreamsClient()
    task_id = f"gateway-{uuid.uuid4()}"
    payload = {
        "goal": goal,
        "data": data,
    }
    envelope = create_task_envelope(
        source="api_gateway",
        task_id=task_id,
        payload=payload,
        destination=f"{tenant_id}:orchestrators:outbound:tasks",
        tenant_id=tenant_id,
        user_id=user.sub,
        correlation_id=correlation_id,
    )
    stream = f"{tenant_id}:orchestrators:outbound:tasks"
    return client.xadd(stream, to_redis_fields(envelope), maxlen=redis_streams.STREAM_MAXLEN)


class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"


class LeadContext(BaseModel):
    name: str
    company: Optional[str] = None
    role: Optional[str] = None
    email: str


class MessageContext(BaseModel):
    from_: str
    content: str
    date: str


class Draft(BaseModel):
    id: str
    from_email: str
    from_name: str
    subject: str
    mailbox: str
    status: DraftStatus
    received_at: datetime
    lead: Optional[LeadContext] = None
    context: List[MessageContext] = []
    draft_content: str
    correlation_id: str


class DraftApproveRequest(BaseModel):
    content: Optional[str] = None  # Allow editing before send


class DraftRejectRequest(BaseModel):
    reason: str


class DraftListResponse(BaseModel):
    drafts: List[Draft]
    total: int
    page: int
    page_size: int


# Helper to convert DB row to API Draft model
def _db_to_draft(row: dict) -> Draft:
    """Convert a database row to a Draft model."""
    return Draft(
        id=row["id"],
        from_email=row.get("lead", {}).get("email", "") if row.get("lead") else "",
        from_name=row.get("lead", {}).get("first_name", "Unknown") if row.get("lead") else "Unknown",
        subject=row.get("subject") or "(No Subject)",
        mailbox=row.get("mailbox_id") or "",
        status=DraftStatus(row.get("status", "pending")),
        received_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if row.get("created_at") else datetime.now(),
        lead=LeadContext(
            name=f"{row['lead'].get('first_name', '')} {row['lead'].get('last_name', '')}".strip() or "Unknown",
            company=row["lead"].get("company_name"),
            role=row["lead"].get("job_title"),
            email=row["lead"].get("email", ""),
        ) if row.get("lead") else None,
        context=[],  # Context loaded separately if needed
        draft_content=row.get("body") or "",
        correlation_id=row.get("generation_metadata", {}).get("correlation_id", "") if row.get("generation_metadata") else "",
    )


@router.get("", response_model=DraftListResponse)
async def list_drafts(
    status: Optional[DraftStatus] = None,
    mailbox: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: SupabaseClient = Depends(get_db),
):
    """
    List drafts for the current tenant.
    
    Fetches from drafts table with RLS enforced by user's JWT.
    """
    # Build filters
    filters = {}
    if status:
        filters["status"] = status.value
    if mailbox:
        filters["mailbox_id"] = mailbox
    
    # Query with related lead data via PostgREST embedding
    # Note: Using select with foreign key join syntax
    raw_drafts = await db.select(
        table="drafts",
        columns="*,lead:leads(id,email,first_name,last_name,company_name,job_title)",
        filters=filters,
        order_by="created_at",
        descending=True,
        limit=page_size,
    )
    
    # Get total count for pagination
    total = await db.count("drafts", filters=filters)
    
    # Convert to API models
    drafts = [_db_to_draft(row) for row in raw_drafts] if raw_drafts else []

    return DraftListResponse(
        drafts=drafts,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{draft_id}", response_model=Draft)
async def get_draft(
    draft_id: str,
    db: SupabaseClient = Depends(get_db),
):
    """Get a specific draft by ID."""
    # Query with lead embedding
    raw_drafts = await db.select(
        table="drafts",
        columns="*,lead:leads(id,email,first_name,last_name,company_name,job_title)",
        filters={"id": draft_id},
        limit=1,
    )
    
    if not raw_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    return _db_to_draft(raw_drafts[0])


@router.post("/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    request: Optional[DraftApproveRequest] = None,
    user: AuthUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_db),
):
    """
    Approve a draft for sending.
    
    If content is provided, it will be used instead of the original draft.
    Updates draft status in DB and enqueues for Channel Sequencer.
    """
    # Get the draft first
    raw_drafts = await db.select(
        table="drafts",
        columns="*,lead:leads(id,email,first_name,last_name,company_name,job_title)",
        filters={"id": draft_id},
        limit=1,
    )
    
    if not raw_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    draft_row = raw_drafts[0]
    
    # Update draft status in DB
    update_data = {
        "status": "approved",
        "approved_by": user.sub,
        "approved_at": datetime.utcnow().isoformat(),
    }
    if request and request.content:
        update_data["body"] = request.content
    
    await db.update("drafts", draft_id, update_data)
    
    # Convert to Draft model for envelope
    draft = _db_to_draft(draft_row)
    tenant_id = _resolve_tenant_id(user)
    
    # Enqueue to Channel Sequencer
    message_id = _enqueue_outbound_task(
        tenant_id=tenant_id,
        user=user,
        goal="Send approved draft",
        data={
            "action": "approve_draft",
            "draft_id": draft_id,
            "approved_content": request.content if request else None,
            "draft": draft.model_dump(mode="json"),
        },
        priority=Priority.HIGH,
        correlation_id=draft.correlation_id,
    )
    return {
        "message": "Draft approved and queued for sending",
        "draft_id": draft_id,
        "status": "approved",
        "message_id": message_id,
    }


@router.post("/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    request: DraftRejectRequest,
    user: AuthUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_db),
):
    """
    Reject a draft with a reason.
    Updates draft status in DB.
    """
    # Verify draft exists
    existing = await db.select_one("drafts", draft_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Update status
    await db.update("drafts", draft_id, {
        "status": "rejected",
        "rejection_reason": request.reason,
    })
    
    return {
        "message": "Draft rejected",
        "draft_id": draft_id,
        "status": "rejected",
        "reason": request.reason,
    }


@router.post("/{draft_id}/rewrite")
async def request_rewrite(
    draft_id: str,
    user: AuthUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_db),
):
    """
    Request AI to generate a new draft.
    Updates draft status and enqueues regeneration request.
    """
    # Get the draft
    raw_drafts = await db.select(
        table="drafts",
        columns="*,lead:leads(id,email,first_name,last_name,company_name,job_title)",
        filters={"id": draft_id},
        limit=1,
    )
    
    if not raw_drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    draft_row = raw_drafts[0]
    
    # Mark as being rewritten (using 'edited' status to indicate in-progress)
    await db.update("drafts", draft_id, {"status": "pending"})
    
    draft = _db_to_draft(draft_row)
    tenant_id = _resolve_tenant_id(user)
    
    message_id = _enqueue_outbound_task(
        tenant_id=tenant_id,
        user=user,
        goal="Rewrite draft",
        data={
            "action": "rewrite_draft",
            "draft_id": draft_id,
            "draft": draft.model_dump(mode="json"),
        },
        priority=Priority.NORMAL,
        correlation_id=draft.correlation_id,
    )
    return {
        "message": "Rewrite requested",
        "draft_id": draft_id,
        "message_id": message_id,
    }
