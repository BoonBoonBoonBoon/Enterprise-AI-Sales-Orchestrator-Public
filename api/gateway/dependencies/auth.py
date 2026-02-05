"""Auth dependencies for gateway endpoints."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError, ExpiredSignatureError
from pydantic import BaseModel
from typing import Optional
import os

from ..config import settings

bearer_scheme = HTTPBearer(auto_error=True)


class AuthUser(BaseModel):
    sub: str
    email: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None  # Alias for tenant_id, used in RLS
    aud: Optional[str] = None
    iss: Optional[str] = None


def _get_jwt_secret() -> str:
    """Get JWT secret, raising if not configured."""
    secret = settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET
    if not secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    return secret


def _is_production() -> bool:
    """Check if running in production mode."""
    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower().strip()
    return env in {"prod", "production"} or not settings.DEBUG


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> AuthUser:
    """Extract and validate user from JWT token.
    
    Security measures:
    - Verifies signature using HS256
    - Validates expiration
    - Optionally validates issuer in production
    """
    token = credentials.credentials
    secret = _get_jwt_secret()
    
    # Configure validation options
    options = {
        "verify_aud": False,  # Supabase sets 'authenticated' as audience
        "verify_exp": True,   # Always verify expiration
        "verify_iss": False,  # We check issuer manually for flexibility
    }

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options=options,
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    # Verify issuer in production if configured
    expected_issuer = os.getenv("SUPABASE_JWT_ISSUER")
    if _is_production() and expected_issuer:
        actual_issuer = payload.get("iss", "")
        if actual_issuer and expected_issuer not in actual_issuer:
            raise HTTPException(status_code=401, detail="Invalid token issuer")

    # Extract tenant/client ID from various possible locations in the JWT
    tenant_id = (
        payload.get("tenant_id")
        or payload.get("client_id")
        or payload.get("app_metadata", {}).get("tenant_id")
        or payload.get("app_metadata", {}).get("client_id")
    )

    return AuthUser(
        sub=str(payload.get("sub", "")),
        email=payload.get("email"),
        role=payload.get("role") or payload.get("app_metadata", {}).get("role"),
        tenant_id=tenant_id,
        client_id=tenant_id,  # Normalize to client_id for RLS compatibility
        aud=payload.get("aud"),
        iss=payload.get("iss"),
    )


def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[AuthUser]:
    """Optionally extract user from JWT - returns None if no valid token."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None


def get_rls_headers(user: AuthUser) -> dict:
    """Generate headers to set Postgres session variables for RLS.
    
    These headers should be passed to Supabase client requests to enable
    row-level security based on the authenticated user's tenant.
    """
    headers = {}
    if user.client_id:
        # This sets the app.current_client session variable in Postgres
        # which is read by the get_current_client_id() function in RLS policies
        headers["x-client-id"] = user.client_id
    return headers


def require_tenant(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency that requires a valid tenant context."""
    if not user.client_id:
        raise HTTPException(
            status_code=403,
            detail="No tenant context. User must belong to an organization."
        )
    return user
