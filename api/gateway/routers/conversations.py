"""Conversation endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

from ..dependencies.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


class ConversationStatus(str, Enum):
    AWAITING_REPLY = "awaiting_reply"
    REPLIED = "replied"
    CLOSED = "closed"


class Message(BaseModel):
    id: str
    from_: str  # "you" or "them"
    content: str
    timestamp: datetime


class Conversation(BaseModel):
    id: str
    from_email: str
    from_name: str
    subject: str
    mailbox: str
    status: ConversationStatus
    last_message_at: datetime
    message_count: int
    unread: bool = False


class ConversationDetail(Conversation):
    messages: List[Message]
    lead_id: Optional[str] = None


class ConversationListResponse(BaseModel):
    conversations: List[Conversation]
    total: int
    page: int
    page_size: int


# Mock data
MOCK_CONVERSATIONS = [
    Conversation(
        id="conv_1",
        from_email="sarah@acme.com",
        from_name="Sarah Johnson",
        subject="Re: Partnership opportunity",
        mailbox="sales@company.com",
        status=ConversationStatus.AWAITING_REPLY,
        last_message_at=datetime.now(),
        message_count=4,
        unread=True,
    ),
    Conversation(
        id="conv_2",
        from_email="mike@startup.io",
        from_name="Mike Chen",
        subject="Product demo request",
        mailbox="sales@company.com",
        status=ConversationStatus.AWAITING_REPLY,
        last_message_at=datetime.now(),
        message_count=1,
        unread=True,
    ),
]

MOCK_MESSAGES = [
    Message(id="msg_1", from_="you", content="Hi Sarah, I wanted to reach out...", timestamp=datetime.now()),
    Message(id="msg_2", from_="them", content="Thanks for reaching out!", timestamp=datetime.now()),
    Message(id="msg_3", from_="you", content="Absolutely! Here's what I'm thinking...", timestamp=datetime.now()),
    Message(id="msg_4", from_="them", content="Could you share some case studies?", timestamp=datetime.now()),
]


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    mailbox: Optional[str] = None,
    status: Optional[ConversationStatus] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List conversations for the current tenant.
    
    TODO: Query from Supabase with tenant_id filter
    """
    conversations = MOCK_CONVERSATIONS

    if mailbox:
        conversations = [c for c in conversations if c.mailbox == mailbox]
    if status:
        conversations = [c for c in conversations if c.status == status]
    if search:
        search_lower = search.lower()
        conversations = [
            c for c in conversations
            if search_lower in c.from_name.lower()
            or search_lower in c.from_email.lower()
            or search_lower in c.subject.lower()
        ]

    return ConversationListResponse(
        conversations=conversations,
        total=len(conversations),
        page=page,
        page_size=page_size,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all messages."""
    for conv in MOCK_CONVERSATIONS:
        if conv.id == conversation_id:
            return ConversationDetail(
                **conv.model_dump(),
                messages=MOCK_MESSAGES,
                lead_id="lead_1",
            )
    raise HTTPException(status_code=404, detail="Conversation not found")
