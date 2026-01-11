"""
Import smoke tests to verify all modules are importable.

These tests catch:
- Circular import issues
- Missing dependencies
- Syntax errors
- __init__.py problems
"""

import pytest


@pytest.mark.unit
def test_import_schemas():
    """Verify all schema modules can be imported."""
    from core.envelope.typed_envelope import Envelope
    from core.schemas import (
        RAGTaskPayload,
        RAGResultPayload,
        CopywriterTaskPayload,
        CopywriterResultPayload,
        PersistenceTaskPayload,
        PersistenceResultPayload,
    )
    
    assert Envelope is not None
    assert RAGTaskPayload is not None
    assert CopywriterTaskPayload is not None
    assert PersistenceTaskPayload is not None


@pytest.mark.unit
def test_import_utils():
    """Verify all utility modules can be imported."""
    from core.utils.graceful_shutdown import GracefulShutdownMixin
    from core.utils.rate_limiter import RateLimiter, RateLimitConfig, TokenBucket, SlidingWindow
    from core.utils.secrets import SecretsProvider, init_secrets_manager
    
    assert GracefulShutdownMixin is not None
    assert RateLimiter is not None
    assert RateLimitConfig is not None
    assert TokenBucket is not None
    assert SlidingWindow is not None
    assert SecretsProvider is not None


@pytest.mark.unit
def test_import_workers():
    """Verify all worker modules can be imported."""
    from tiers.tier_3.rag_agent.worker import RAGWorker
    from tiers.tier_3.copywriter_agent.worker import CopyWorker
    from tiers.tier_3.persistence_agent.write_worker import WriteWorker
    
    assert RAGWorker is not None
    assert RAGWorker is not None
    assert CopyWorker is not None
    assert WriteWorker is not None


@pytest.mark.unit
def test_import_orchestrators():
    """Verify orchestrator modules can be imported."""
    from tiers.tier_2.leads_orchestrator.leads_orchestrator import LeadsOrchestrator
    
    assert LeadsOrchestrator is not None


@pytest.mark.unit
def test_import_ab_testing():
    """Verify A/B testing module can be imported."""
    from core.utils.ab_testing import ExperimentConfig, VariantConfig, BucketStrategy
    
    assert ExperimentConfig is not None
    assert VariantConfig is not None
    assert BucketStrategy is not None


@pytest.mark.unit
def test_import_all_critical_modules():
    """Comprehensive import test for all critical modules."""
    # Schemas
    from core.envelope.typed_envelope import Envelope
    
    # Utils
    from core.utils.graceful_shutdown import GracefulShutdownMixin
    from core.utils.rate_limiter import RateLimiter, RateLimitConfig
    from core.utils.secrets import SecretsProvider
    from core.utils.ab_testing import ExperimentConfig
    
    # Workers
    from tiers.tier_3.rag_agent.worker import RAGWorker
    from tiers.tier_3.copywriter_agent.worker import CopyWorker
    from tiers.tier_3.persistence_agent.write_worker import WriteWorker
    
    # Orchestrators
    from tiers.tier_2.leads_orchestrator.leads_orchestrator import LeadsOrchestrator
    
    # Verify all imports succeeded
    assert all([
        Envelope,
        GracefulShutdownMixin,
        RateLimiter,
        RateLimitConfig,
        SecretsProvider,
        ExperimentConfig,
        RAGWorker,
        CopyWorker,
        WriteWorker,
        LeadsOrchestrator,
    ])
    
    print("✅ All critical modules imported successfully")
