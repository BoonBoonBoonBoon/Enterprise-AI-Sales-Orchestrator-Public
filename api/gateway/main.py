"""
Agentic API Gateway

This is the customer-facing REST API that the portal talks to.
It enforces authentication, tenant isolation, and rate limiting
before delegating to the internal orchestration engine.

The gateway NEVER exposes Redis streams directly.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from jose import jwt, JWTError

from .routers import auth, drafts, leads, mailboxes, conversations, health, admin, stats
from .middleware.rate_limit import RateLimitMiddleware
from .config import settings


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract tenant/client ID from JWT and add to request state.
    
    This enables downstream handlers and Supabase calls to enforce tenant isolation.
    The client_id is extracted from the JWT and stored in request.state.client_id.
    """

    async def dispatch(self, request: Request, call_next):
        client_id = None

        # Try to extract client_id from Authorization header
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                # Decode without verification just to extract claims
                # (actual verification happens in auth dependency)
                payload = jwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET or settings.JWT_SECRET or "dummy",
                    algorithms=["HS256"],
                    options={"verify_signature": False, "verify_aud": False, "verify_exp": False},
                )
                client_id = (
                    payload.get("tenant_id")
                    or payload.get("client_id")
                    or payload.get("app_metadata", {}).get("tenant_id")
                    or payload.get("app_metadata", {}).get("client_id")
                )
            except JWTError:
                pass  # Invalid token - will be caught by auth dependency

        # Store in request state for use by route handlers
        request.state.client_id = client_id

        response = await call_next(request)

        # Optionally add client_id to response headers for debugging (dev only)
        if settings.DEBUG and client_id:
            response.headers["X-Client-ID"] = str(client_id)

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"🚀 Agentic Gateway starting on {settings.HOST}:{settings.PORT}")
    yield
    # Shutdown
    print("👋 Agentic Gateway shutting down")


app = FastAPI(
    title="Agentic API Gateway",
    description="Customer-facing API for the Agentic email automation platform",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware - must be added before other middleware
app.add_middleware(RateLimitMiddleware)

# Tenant context middleware - extracts client_id from JWT for RLS
app.add_middleware(TenantContextMiddleware)

# Mount routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["Stats"])
app.include_router(drafts.router, prefix="/api/v1/drafts", tags=["Drafts"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(mailboxes.router, prefix="/api/v1/mailboxes", tags=["Mailboxes"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["Conversations"])


@app.get("/")
async def root():
    return {
        "name": "Agentic API Gateway",
        "version": "1.0.0",
        "docs": "/api/v1/docs",
    }
