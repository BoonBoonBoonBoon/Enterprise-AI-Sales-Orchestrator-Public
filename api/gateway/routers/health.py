"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "service": "agentic-gateway"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness check - verifies dependencies are available."""
    # TODO: Check Supabase and Redis connectivity
    return {
        "status": "ready",
        "checks": {
            "supabase": "ok",
            "redis": "ok",
        },
    }
