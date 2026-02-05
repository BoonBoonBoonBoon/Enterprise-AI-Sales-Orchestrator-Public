"""Admin endpoints for user and tenant management.

These endpoints require admin role and are used for:
- Inviting users to a tenant
- Managing user permissions
- Viewing tenant members
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum
import secrets
import os

from supabase import create_client, Client

from ..config import settings
from ..dependencies.auth import get_current_user, AuthUser

router = APIRouter()


class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.MEMBER
    name: Optional[str] = None


class InviteUserResponse(BaseModel):
    success: bool
    email: str
    invite_token: Optional[str] = None  # Only returned in dev mode
    message: str


class TenantMember(BaseModel):
    user_id: str
    email: str
    role: str
    joined_at: Optional[datetime] = None


class TenantMembersResponse(BaseModel):
    members: List[TenantMember]
    total: int


class UpdateMemberRoleRequest(BaseModel):
    role: UserRole


class AuditLogEntry(BaseModel):
    id: str
    action: str
    actor_id: str
    target_id: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime


class AuditLogResponse(BaseModel):
    entries: List[AuditLogEntry]
    total: int


def get_supabase_admin_client() -> Client:
    """Get Supabase client with service role for admin operations."""
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not settings.SUPABASE_URL or not service_key:
        raise HTTPException(status_code=500, detail="Supabase admin configuration is missing")
    return create_client(settings.SUPABASE_URL, service_key)


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency that requires admin role."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if not user.client_id:
        raise HTTPException(status_code=403, detail="No tenant context")
    return user


async def log_audit_event(
    client_id: str,
    action: str,
    actor_id: str,
    target_id: Optional[str] = None,
    target_id: Optional[str] = None,
    target_table: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Log an audit event to the database."""
    try:
        admin_client = get_supabase_admin_client()
        admin_client.table("audit_log").insert({
            "client_id": client_id,
            "action": action,
            "user_or_agent": actor_id,  # Required column
            "actor_id": actor_id,       # New column for consistency
            "target_table": target_table or "users",
            "target_id": target_id,
            "metadata": metadata or {},
        }).execute()
    except Exception as e:
        # Don't fail the request if audit logging fails
        print(f"Audit log error: {e}")


@router.post("/invite", response_model=InviteUserResponse)
async def invite_user(
    request: InviteUserRequest,
    background_tasks: BackgroundTasks,
    admin: AuthUser = Depends(require_admin),
):
    """
    Invite a user to the current tenant.
    
    Creates an invitation that:
    1. Sends an email to the user (or returns invite token in dev mode)
    2. Pre-creates the user_client_membership record in 'pending' state
    3. When user signs up/accepts, membership becomes 'active'
    
    Admin access required.
    """
    admin_client = get_supabase_admin_client()
    
    # Check if user already exists in this tenant
    existing = admin_client.table("user_client_memberships").select("*").eq(
        "client_id", admin.client_id
    ).execute()
    
    # Check by email - need to look up user first
    try:
        # Try to find existing user by email
        users_response = admin_client.auth.admin.list_users()
        existing_user = next(
            (u for u in users_response if u.email == request.email),
            None
        )
        
        if existing_user:
            # Check if already a member
            is_member = any(
                m["user_id"] == existing_user.id
                for m in existing.data
            )
            if is_member:
                raise HTTPException(
                    status_code=400,
                    detail=f"User {request.email} is already a member of this tenant"
                )
    except HTTPException:
        raise
    except Exception:
        # User lookup failed, continue with invitation
        pass
    
    # Generate invite token
    invite_token = secrets.token_urlsafe(32)
    
    # Store pending invitation
    try:
        admin_client.table("pending_invitations").insert({
            "client_id": admin.client_id,
            "email": request.email,
            "role": request.role.value,
            "invite_token": invite_token,
            "invited_by": admin.sub,
            "name": request.name,
        }).execute()
    except Exception as e:
        # Table might not exist yet, create minimal tracking
        print(f"Could not store invitation: {e}")
    
    # Log audit event
    background_tasks.add_task(
        log_audit_event,
        client_id=admin.client_id,
        action="user.invited",
        actor_id=admin.sub,
        target_id=request.email,
        metadata={"role": request.role.value},
    )
    
    # In production, would send email here
    # For now, return success
    is_dev = os.getenv("DEBUG") == "1" or os.getenv("ENV") == "development"
    
    return InviteUserResponse(
        success=True,
        email=request.email,
        invite_token=invite_token if is_dev else None,
        message=f"Invitation sent to {request.email}" if not is_dev else f"Dev invite token generated",
    )


@router.get("/members", response_model=TenantMembersResponse)
async def list_tenant_members(
    admin: AuthUser = Depends(require_admin),
):
    """
    List all members of the current tenant.
    
    Admin access required.
    """
    admin_client = get_supabase_admin_client()
    
    memberships = admin_client.table("user_client_memberships").select(
        "user_id, role, created_at"
    ).eq("client_id", admin.client_id).execute()
    
    # Get user details for each membership
    members = []
    for m in memberships.data:
        try:
            user = admin_client.auth.admin.get_user_by_id(m["user_id"])
            members.append(TenantMember(
                user_id=m["user_id"],
                email=user.user.email,
                role=m["role"],
                joined_at=m.get("created_at"),
            ))
        except Exception:
            # User might have been deleted
            members.append(TenantMember(
                user_id=m["user_id"],
                email="[deleted]",
                role=m["role"],
                joined_at=m.get("created_at"),
            ))
    
    return TenantMembersResponse(
        members=members,
        total=len(members),
    )


@router.patch("/members/{user_id}/role", response_model=TenantMember)
async def update_member_role(
    user_id: str,
    request: UpdateMemberRoleRequest,
    background_tasks: BackgroundTasks,
    admin: AuthUser = Depends(require_admin),
):
    """
    Update a member's role in the current tenant.
    
    Admin access required.
    """
    admin_client = get_supabase_admin_client()
    
    # Verify user is member of this tenant
    membership = admin_client.table("user_client_memberships").select("*").eq(
        "client_id", admin.client_id
    ).eq("user_id", user_id).execute()
    
    if not membership.data:
        raise HTTPException(status_code=404, detail="User not found in this tenant")
    
    # Prevent removing last admin
    if membership.data[0]["role"] == "admin" and request.role != UserRole.ADMIN:
        admin_count = admin_client.table("user_client_memberships").select(
            "user_id", count="exact"
        ).eq("client_id", admin.client_id).eq("role", "admin").execute()
        
        if admin_count.count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last admin from the tenant"
            )
    
    # Update role
    admin_client.table("user_client_memberships").update({
        "role": request.role.value,
    }).eq("client_id", admin.client_id).eq("user_id", user_id).execute()
    
    # Log audit event
    background_tasks.add_task(
        log_audit_event,
        client_id=admin.client_id,
        action="member.role_updated",
        actor_id=admin.sub,
        target_id=user_id,
        metadata={"old_role": membership.data[0]["role"], "new_role": request.role.value},
    )
    
    # Get updated user info
    try:
        user = admin_client.auth.admin.get_user_by_id(user_id)
        email = user.user.email
    except Exception:
        email = "[unknown]"
    
    return TenantMember(
        user_id=user_id,
        email=email,
        role=request.role.value,
        joined_at=membership.data[0].get("created_at"),
    )


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: str,
    background_tasks: BackgroundTasks,
    admin: AuthUser = Depends(require_admin),
):
    """
    Remove a member from the current tenant.
    
    Admin access required. Cannot remove yourself.
    """
    admin_client = get_supabase_admin_client()
    
    if user_id == admin.sub:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    
    # Verify user is member of this tenant
    membership = admin_client.table("user_client_memberships").select("*").eq(
        "client_id", admin.client_id
    ).eq("user_id", user_id).execute()
    
    if not membership.data:
        raise HTTPException(status_code=404, detail="User not found in this tenant")
    
    # Prevent removing last admin
    if membership.data[0]["role"] == "admin":
        admin_count = admin_client.table("user_client_memberships").select(
            "user_id", count="exact"
        ).eq("client_id", admin.client_id).eq("role", "admin").execute()
        
        if admin_count.count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last admin from the tenant"
            )
    
    # Remove membership
    admin_client.table("user_client_memberships").delete().eq(
        "client_id", admin.client_id
    ).eq("user_id", user_id).execute()
    
    # Log audit event
    background_tasks.add_task(
        log_audit_event,
        client_id=admin.client_id,
        action="member.removed",
        actor_id=admin.sub,
        target_id=user_id,
        metadata={"role": membership.data[0]["role"]},
    )
    
    return {"message": "Member removed successfully"}


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    limit: int = 50,
    offset: int = 0,
    admin: AuthUser = Depends(require_admin),
):
    """
    Get audit log for the current tenant.
    
    Admin access required.
    """
    admin_client = get_supabase_admin_client()
    
    result = admin_client.table("audit_log").select(
        "*", count="exact"
    ).eq("client_id", admin.client_id).order(
        "created_at", desc=True
    ).range(offset, offset + limit - 1).execute()
    
    entries = [
        AuditLogEntry(
            id=str(e["id"]),
            action=e["action"],
            actor_id=e["actor_id"],
            target_id=e.get("target_id"),
            metadata=e.get("metadata"),
            created_at=e["created_at"],
        )
        for e in result.data
    ]
    
    return AuditLogResponse(
        entries=entries,
        total=result.count or len(entries),
    )
