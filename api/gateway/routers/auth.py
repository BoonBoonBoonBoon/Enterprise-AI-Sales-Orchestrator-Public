"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Header, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import os

from jose import jwt

from supabase import create_client

from ..config import settings
from ..dependencies.auth import get_current_user, AuthUser

router = APIRouter()


def _is_dev_mode() -> bool:
    """True only for local/dev runs. Never enable in production."""

    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower().strip()
    node_env = (os.getenv("NODE_ENV") or "").lower().strip()

    if settings.DEBUG:
        return True
    if getattr(settings, "DEV_LOGIN_ENABLED", False):
        return True
    if env in {"dev", "development", "local"}:
        return True
    if node_env and node_env != "production":
        return True
    return False


async def log_auth_event(
    action: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    client_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Log authentication events to audit log."""
    try:
        service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not service_key:
            return
        client = create_client(settings.SUPABASE_URL, service_key)
        client.table("audit_log").insert({
            "client_id": client_id,
            "action": action,
            "user_or_agent": user_id or email or "unknown",  # Required column
            "target_table": "auth",
            "actor_id": user_id,
            "actor_email": email,
            "ip_address": ip_address,
            "metadata": metadata or {},
        }).execute()
    except Exception as e:
        print(f"Audit log error: {e}")


# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    company: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    tenant_id: str
    role: str


class DevLoginRequest(BaseModel):
    """Optional overrides for local development."""

    tenant_id: str = "agentic-dev"
    email: EmailStr = "dev-admin@example.com"
    role: str = "admin"


# Endpoints
def get_supabase_client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="Supabase configuration is missing")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return access token.
    
    Uses Supabase Auth to issue a JWT.
    """
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": request.email, "password": request.password})

    if not result.session:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(
        access_token=result.session.access_token,
        expires_at=datetime.fromtimestamp(result.session.expires_at),
        user={
            "id": result.user.id,
            "email": result.user.email,
            "name": (result.user.user_metadata or {}).get("name"),
            "tenant_id": (result.user.app_metadata or {}).get("tenant_id"),
            "role": (result.user.app_metadata or {}).get("role"),
        },
    )


@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest):
    """
    Create new user account and tenant.
    
    Uses Supabase Auth to register a user.
    """
    client = get_supabase_client()
    result = client.auth.sign_up(
        {
            "email": request.email,
            "password": request.password,
            "options": {"data": {"name": request.name, "company": request.company}},
        }
    )

    if not result.session:
        raise HTTPException(status_code=401, detail="Signup failed")

    return TokenResponse(
        access_token=result.session.access_token,
        expires_at=datetime.fromtimestamp(result.session.expires_at),
        user={
            "id": result.user.id,
            "email": result.user.email,
            "name": (result.user.user_metadata or {}).get("name"),
            "tenant_id": (result.user.app_metadata or {}).get("tenant_id"),
            "role": (result.user.app_metadata or {}).get("role"),
        },
    )


@router.post("/logout")
async def logout():
    """
    Logout current user.
    
    For JWT-based auth, this is typically handled client-side.
    Can be used to invalidate refresh tokens if implemented.
    """
    return {"message": "Logged out successfully"}


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(
    http_request: Request,
    request: DevLoginRequest = DevLoginRequest(),
    x_dev_login_secret: Optional[str] = Header(default=None, alias="X-Dev-Login-Secret"),
):
    """DEV ONLY: issue a local JWT without Supabase.

    This endpoint is intentionally disabled in production.
    """

    # Block in production - this is a security-critical check
    if not _is_dev_mode():
        raise HTTPException(status_code=404, detail="Not found")

    now = datetime.utcnow()
    expires_at = now + timedelta(hours=12)

    payload = {
        "sub": "dev-admin",
        "email": str(request.email),
        "role": request.role,
        "tenant_id": request.tenant_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
    if not secret:
        raise HTTPException(status_code=500, detail="JWT secret is missing")

    token = jwt.encode(payload, secret, algorithm="HS256")

    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user={
            "id": payload["sub"],
            "email": payload["email"],
            "name": "Dev Admin",
            "tenant_id": payload["tenant_id"],
            "role": payload["role"],
        },
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(user: AuthUser = Depends(get_current_user)):
    """
    Get current authenticated user.
    """
    return UserResponse(
        id=user.sub,
        email=user.email or "",
        name="",
        tenant_id=user.tenant_id or "",
        role=user.role or "user",
    )


class AcceptInviteRequest(BaseModel):
    invite_token: str


class AcceptInviteResponse(BaseModel):
    success: bool
    client_id: Optional[str] = None
    role: Optional[str] = None
    message: str


@router.post("/accept-invite", response_model=AcceptInviteResponse)
async def accept_invitation(
    request: AcceptInviteRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    user: AuthUser = Depends(get_current_user),
):
    """
    Accept a tenant invitation.
    
    The user must be authenticated. The invite token is validated and
    the user is added to the tenant with the specified role.
    """
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not settings.SUPABASE_URL or not service_key:
        raise HTTPException(status_code=500, detail="Supabase configuration is missing")
    
    client = create_client(settings.SUPABASE_URL, service_key)
    
    # Call the accept_invitation function in Postgres
    result = client.rpc("accept_invitation", {
        "p_invite_token": request.invite_token,
        "p_user_id": user.sub,
    }).execute()
    
    if not result.data or not result.data.get("success"):
        error = result.data.get("error", "Failed to accept invitation") if result.data else "Failed to accept invitation"
        raise HTTPException(status_code=400, detail=error)
    
    # Get client IP for audit
    client_ip = (
        http_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or http_request.headers.get("x-real-ip")
        or (http_request.client.host if http_request.client else None)
    )
    
    # Log the event
    background_tasks.add_task(
        log_auth_event,
        action="invitation.accepted",
        user_id=user.sub,
        email=user.email,
        client_id=result.data.get("client_id"),
        ip_address=client_ip,
        metadata={"role": result.data.get("role")},
    )
    
    return AcceptInviteResponse(
        success=True,
        client_id=result.data.get("client_id"),
        role=result.data.get("role"),
        message="Successfully joined the organization",
    )
    )
