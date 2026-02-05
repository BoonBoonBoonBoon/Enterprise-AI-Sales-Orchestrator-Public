"""Mailbox management endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

from ..dependencies.auth import get_current_user, AuthUser
from ..dependencies.supabase import SupabaseClient, get_db

router = APIRouter(dependencies=[Depends(get_current_user)])


class MailboxProvider(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    IMAP = "imap"


class MailboxStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class Mailbox(BaseModel):
    id: str
    email: str
    provider: MailboxProvider
    status: MailboxStatus
    last_sync: Optional[datetime] = None
    messages_received: int = 0
    messages_sent: int = 0
    error: Optional[str] = None


class MailboxConnectRequest(BaseModel):
    provider: MailboxProvider
    email: str
    display_name: Optional[str] = None
    # OAuth token for Gmail/Outlook
    oauth_token: Optional[str] = None
    # IMAP credentials
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None


class MailboxListResponse(BaseModel):
    mailboxes: List[Mailbox]
    total: int


def _db_to_mailbox(row: dict, *, messages_received: int = 0, messages_sent: int = 0) -> Mailbox:
    """Convert a database row to a Mailbox model."""
    is_active = row.get("is_active", True)
    return Mailbox(
        id=row["id"],
        email=row.get("email", ""),
        provider=MailboxProvider(row.get("provider", "gmail")),
        status=MailboxStatus.CONNECTED if is_active else MailboxStatus.DISCONNECTED,
        last_sync=datetime.fromisoformat(row["last_sync_at"].replace("Z", "+00:00")) if row.get("last_sync_at") else None,
        messages_received=messages_received,
        messages_sent=messages_sent,
        error=None,
    )


async def _get_mailbox_counts(db: SupabaseClient, mailbox_id: str, email: str) -> tuple[int, int]:
    messages_sent = await db.count(
        "drafts",
        filters={
            "mailbox_id": mailbox_id,
            "status": "sent",
        },
    )

    messages_received = 0
    if email:
        try:
            messages_received = await db.count(
                "messages",
                filters={
                    "direction": "inbound",
                    "metadata": ("ilike", f"%{email}%"),
                },
            )
        except HTTPException:
            messages_received = await db.count(
                "messages",
                filters={
                    "sender_type": "lead",
                    "metadata": ("ilike", f"%{email}%"),
                },
            )

    return messages_received, messages_sent


@router.get("", response_model=MailboxListResponse)
async def list_mailboxes(db: SupabaseClient = Depends(get_db)):
    """List all mailboxes for the current tenant."""
    raw_mailboxes = await db.select(
        table="mailboxes",
        columns="id,email,provider,is_active,last_sync_at,display_name",
        order_by="created_at",
        descending=True,
    )
    
    mailboxes = []
    for row in raw_mailboxes or []:
        email = row.get("email", "")
        messages_received, messages_sent = await _get_mailbox_counts(db, row["id"], email)
        mailboxes.append(
            _db_to_mailbox(
                row,
                messages_received=messages_received,
                messages_sent=messages_sent,
            )
        )
    
    return MailboxListResponse(
        mailboxes=mailboxes,
        total=len(mailboxes),
    )


@router.get("/{mailbox_id}", response_model=Mailbox)
async def get_mailbox(mailbox_id: str, db: SupabaseClient = Depends(get_db)):
    """Get a specific mailbox by ID."""
    row = await db.select_one("mailboxes", mailbox_id)
    if not row:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    email = row.get("email", "")
    messages_received, messages_sent = await _get_mailbox_counts(db, row["id"], email)
    return _db_to_mailbox(
        row,
        messages_received=messages_received,
        messages_sent=messages_sent,
    )


@router.post("", response_model=Mailbox)
async def connect_mailbox(
    request: MailboxConnectRequest,
    user: AuthUser = Depends(get_current_user),
    db: SupabaseClient = Depends(get_db),
):
    """
    Connect a new mailbox.
    
    For Gmail/Outlook: Use OAuth token from frontend auth flow
    For IMAP: Use provided credentials
    """
    # Build credentials JSON based on provider
    oauth_credentials = None
    if request.provider == MailboxProvider.IMAP:
        oauth_credentials = {
            "imap_host": request.imap_host,
            "imap_port": request.imap_port,
            "imap_username": request.imap_username,
            "smtp_host": request.smtp_host,
            "smtp_port": request.smtp_port,
        }
    elif request.oauth_token:
        oauth_credentials = {"token": request.oauth_token}
    
    # Get client_id from user's tenant
    client_id = user.client_id or user.tenant_id
    if not client_id:
        raise HTTPException(status_code=400, detail="No tenant context available")
    
    new_mailbox = await db.insert("mailboxes", {
        "client_id": client_id,
        "email": request.email,
        "provider": request.provider.value,
        "display_name": request.display_name,
        "is_active": True,
        "oauth_credentials": oauth_credentials,
    })
    
    return _db_to_mailbox(new_mailbox)


@router.post("/{mailbox_id}/reconnect")
async def reconnect_mailbox(mailbox_id: str, db: SupabaseClient = Depends(get_db)):
    """
    Reconnect a mailbox (refresh OAuth token or retry IMAP connection).
    """
    existing = await db.select_one("mailboxes", mailbox_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    
    await db.update("mailboxes", mailbox_id, {"is_active": True})
    
    return {
        "message": "Mailbox reconnection initiated",
        "mailbox_id": mailbox_id,
    }


@router.post("/{mailbox_id}/sync")
async def sync_mailbox(mailbox_id: str, db: SupabaseClient = Depends(get_db)):
    """
    Trigger an immediate sync for a mailbox.
    """
    existing = await db.select_one("mailboxes", mailbox_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    
    # Update last_sync_at timestamp
    await db.update("mailboxes", mailbox_id, {
        "last_sync_at": datetime.utcnow().isoformat(),
    })
    
    # TODO: Enqueue sync task to InboxPoller
    
    return {
        "message": "Sync triggered",
        "mailbox_id": mailbox_id,
    }


@router.delete("/{mailbox_id}")
async def disconnect_mailbox(mailbox_id: str, db: SupabaseClient = Depends(get_db)):
    """
    Disconnect and remove a mailbox.
    """
    existing = await db.select_one("mailboxes", mailbox_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    
    # Soft delete by deactivating rather than hard delete
    await db.update("mailboxes", mailbox_id, {
        "is_active": False,
        "oauth_credentials": None,  # Clear credentials
    })
    
    return {
        "message": "Mailbox disconnected",
        "mailbox_id": mailbox_id,
    }

