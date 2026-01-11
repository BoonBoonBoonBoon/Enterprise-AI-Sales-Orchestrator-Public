"""
Core Utilities Module

Consolidated utilities for the agentic system including:
- A/B testing framework
- Graceful shutdown handling
- Mock data generation
- Rate limiting
- Secrets management
- Distributed tracing
- Workflow progress tracking
"""

# Import common utilities for convenience
from .ab_testing import (
    assign_variant,
    track_conversion,
    ABTestingStore,
    ExperimentConfig,
    VariantConfig,
    ConversionEvent,
    ExperimentStatus
)

from .graceful_shutdown import GracefulShutdownMixin

from .mock_leads import generate_lead_profile, generate_leads

from .rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    init_rate_limiter,
    get_rate_limiter
)

from .secrets import (
    get_secret,
    init_secrets_manager,
    get_all_secrets,
    inject_secrets_into_env
)

from .tracing import (
    init_tracer,
    inject_trace_context,
    extract_trace_context,
    TracedWorker
)

from .workflow_progress import WorkflowProgressTracker, StepStatus, WorkflowStatus

__all__ = [
    # A/B Testing
    "assign_variant",
    "track_conversion",
    "ABTestingStore",
    "ExperimentConfig",
    "VariantConfig",
    "ConversionEvent",
    "ExperimentStatus",
    
    # Graceful Shutdown
    "GracefulShutdownMixin",
    
    # Mock Data
    "generate_lead_profile",
    "generate_leads",
    
    # Rate Limiting
    "RateLimiter",
    "RateLimitConfig",
    "init_rate_limiter",
    "get_rate_limiter",
    
    # Secrets
    "get_secret",
    "init_secrets_manager",
    "get_all_secrets",
    "inject_secrets_into_env",
    
    # Tracing
    "init_tracer",
    "inject_trace_context",
    "extract_trace_context",
    "TracedWorker",
    
    # Workflow Progress
    "WorkflowProgressTracker",
    "StepStatus",
    "WorkflowStatus",
]

