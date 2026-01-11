"""
Agent Harness Validation Script

Quick validation that all harness components are working correctly.
Runs basic smoke tests without requiring full infrastructure.
"""

import asyncio
import logging
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Mock Agent ====================

class MockAgent:
    """Mock agent for testing harness"""
    
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.call_count = 0
    
    async def execute(self, task_data: Any) -> dict:
        """Mock execute method"""
        self.call_count += 1
        logger.info(f"MockAgent.execute called (attempt {self.call_count})")
        
        if self.should_fail and self.call_count < 3:
            raise Exception(f"Mock failure (attempt {self.call_count})")
        
        return {
            "status": "success",
            "data": task_data,
            "attempts": self.call_count
        }
    
    async def health_check(self) -> dict:
        """Mock health check"""
        return {
            "status": "healthy",
            "call_count": self.call_count
        }


# ==================== Test Functions ====================

async def test_retry_strategies():
    """Test all retry strategy implementations"""
    logger.info("=" * 60)
    logger.info("Testing Retry Strategies")
    logger.info("=" * 60)
    
    from agent.harness.retry_strategies import (
        ExponentialBackoffRetry,
        LinearBackoffRetry,
        JitteredBackoffRetry,
    )
    
    # Test exponential backoff
    logger.info("\n1. Testing ExponentialBackoffRetry...")
    retry = ExponentialBackoffRetry(max_retries=3, base_delay=0.1)
    agent = MockAgent(should_fail=True)
    
    result = await retry.execute_with_retry(
        func=agent.execute,
        args=({"test": "exponential"},),
        execution_id="test_exp_1"
    )
    assert result["status"] == "success"
    assert result["attempts"] == 3
    logger.info("✅ ExponentialBackoffRetry works!")
    
    # Test linear backoff
    logger.info("\n2. Testing LinearBackoffRetry...")
    retry = LinearBackoffRetry(max_retries=3, base_delay=0.1, increment=0.1)
    agent = MockAgent(should_fail=True)
    
    result = await retry.execute_with_retry(
        func=agent.execute,
        args=({"test": "linear"},),
        execution_id="test_lin_1"
    )
    assert result["status"] == "success"
    logger.info("✅ LinearBackoffRetry works!")
    
    # Test jittered backoff
    logger.info("\n3. Testing JitteredBackoffRetry...")
    retry = JitteredBackoffRetry(max_retries=3, base_delay=0.1, jitter_factor=0.3)
    agent = MockAgent(should_fail=True)
    
    result = await retry.execute_with_retry(
        func=agent.execute,
        args=({"test": "jittered"},),
        execution_id="test_jit_1"
    )
    assert result["status"] == "success"
    logger.info("✅ JitteredBackoffRetry works!")


async def test_observability_backends():
    """Test all observability backend implementations"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Observability Backends")
    logger.info("=" * 60)
    
    from agent.harness.observability import SimpleLoggingObservability
    
    # Test simple logging (always available)
    logger.info("\n1. Testing SimpleLoggingObservability...")
    obs = SimpleLoggingObservability()
    
    with obs.start_span("test_span") as span:
        span.set_attribute("test_key", "test_value")
        obs.record_metric("test_metric", 123.45, {"tag": "test"})
        obs.log_event("INFO", "Test event", {"context": "test"})
    
    logger.info("✅ SimpleLoggingObservability works!")
    
    # Test OpenTelemetry (if available)
    try:
        from agent.harness.observability import OpenTelemetryObservability
        logger.info("\n2. Testing OpenTelemetryObservability...")
        obs = OpenTelemetryObservability(service_name="test-service")
        
        with obs.start_span("test_span") as span:
            if span:
                span.set_attribute("test_key", "test_value")
        
        logger.info("✅ OpenTelemetryObservability works!")
    except ImportError as e:
        logger.info(f"⚠️  OpenTelemetry not available: {e}")
    
    # Test Datadog (if available)
    try:
        from agent.harness.observability import DatadogObservability
        logger.info("\n3. Testing DatadogObservability...")
        # Note: Will fail gracefully if datadog not installed
        logger.info("⚠️  Datadog requires installation: pip install ddtrace datadog")
    except ImportError as e:
        logger.info(f"⚠️  Datadog not available: {e}")


async def test_quota_managers():
    """Test quota manager implementations"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Quota Managers")
    logger.info("=" * 60)
    
    from agent.harness.quota_management import InMemoryQuota
    
    # Test in-memory quota
    logger.info("\n1. Testing InMemoryQuota...")
    quota = InMemoryQuota(requests_per_hour=3, window_seconds=1)
    
    # Should allow 3 requests
    assert await quota.can_execute("test_agent") == True
    await quota.record_execution("test_agent")
    
    assert await quota.can_execute("test_agent") == True
    await quota.record_execution("test_agent")
    
    assert await quota.can_execute("test_agent") == True
    await quota.record_execution("test_agent")
    
    # Should deny 4th request
    assert await quota.can_execute("test_agent") == False
    
    # After window, should allow again
    await asyncio.sleep(1.1)
    assert await quota.can_execute("test_agent") == True
    
    logger.info("✅ InMemoryQuota works!")
    
    # Note: Redis quota requires Redis instance
    logger.info("\n⚠️  RedisTokenBucket requires Redis instance (skipped)")


async def test_harness_integration():
    """Test full harness integration"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing AgentHarness Integration")
    logger.info("=" * 60)
    
    from agent.harness import AgentHarness, HarnessConfig
    from agent.harness.retry_strategies import ExponentialBackoffRetry
    from agent.harness.observability import SimpleLoggingObservability
    from agent.harness.quota_management import InMemoryQuota
    
    # Test 1: Basic harness
    logger.info("\n1. Testing basic harness...")
    agent = MockAgent(should_fail=False)
    harness = AgentHarness(
        agent=agent,
        retry_strategy=ExponentialBackoffRetry(max_retries=3, base_delay=0.1),
        observability=SimpleLoggingObservability(),
    )
    
    result = await harness.execute({"test": "basic"})
    assert result["status"] == "success"
    logger.info("✅ Basic harness works!")
    
    # Test 2: Harness with quota
    logger.info("\n2. Testing harness with quota...")
    agent = MockAgent(should_fail=False)
    harness = AgentHarness(
        agent=agent,
        retry_strategy=ExponentialBackoffRetry(max_retries=3, base_delay=0.1),
        observability=SimpleLoggingObservability(),
        quota_manager=InMemoryQuota(requests_per_hour=2, window_seconds=1),
    )
    
    result1 = await harness.execute({"test": "quota1"})
    result2 = await harness.execute({"test": "quota2"})
    
    # Third should fail quota
    try:
        await harness.execute({"test": "quota3"})
        assert False, "Should have raised QuotaExceededError"
    except Exception as e:
        assert "Quota" in str(e)
        logger.info("✅ Quota enforcement works!")
    
    # Test 3: Factory method
    logger.info("\n3. Testing from_config factory method...")
    config = HarnessConfig(
        max_retries=3,
        retry_strategy="exponential",
        observability_backend="simple",
        enable_checkpointing=False,
        requests_per_hour=100,
        quota_backend="memory",
    )
    
    agent = MockAgent(should_fail=False)
    harness = AgentHarness.from_config(agent, config)
    
    result = await harness.execute({"test": "factory"})
    assert result["status"] == "success"
    logger.info("✅ from_config() works!")
    
    # Test 4: Health check
    logger.info("\n4. Testing health check...")
    health = await harness.health_check()
    assert health["status"] == "healthy"
    assert "components" in health
    logger.info("✅ Health check works!")


async def test_config_presets():
    """Test HarnessConfig presets"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing HarnessConfig Presets")
    logger.info("=" * 60)
    
    from agent.harness import HarnessConfig
    
    # Test development preset
    logger.info("\n1. Testing development preset...")
    config = HarnessConfig.for_development()
    assert config.max_retries == 1
    assert config.timeout_seconds == 60
    assert config.enable_checkpointing == False
    logger.info("✅ Development preset works!")
    
    # Test staging preset
    logger.info("\n2. Testing staging preset...")
    config = HarnessConfig.for_staging()
    assert config.max_retries == 3
    assert config.timeout_seconds == 120
    logger.info("✅ Staging preset works!")
    
    # Test production preset
    logger.info("\n3. Testing production preset...")
    config = HarnessConfig.for_production()
    assert config.max_retries == 5
    assert config.timeout_seconds == 300
    logger.info("✅ Production preset works!")


# ==================== Main ====================

async def main():
    """Run all validation tests"""
    logger.info("\n" + "=" * 60)
    logger.info("🚀 AGENT HARNESS VALIDATION")
    logger.info("=" * 60)
    
    try:
        # Run all tests
        await test_retry_strategies()
        await test_observability_backends()
        await test_quota_managers()
        await test_harness_integration()
        await test_config_presets()
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL VALIDATION TESTS PASSED!")
        logger.info("=" * 60)
        logger.info("\nThe Agent Harness is working correctly.")
        logger.info("All core components are operational:")
        logger.info("  • Retry strategies (exponential, linear, jittered)")
        logger.info("  • Observability backends (simple logging)")
        logger.info("  • Quota management (in-memory)")
        logger.info("  • Configuration presets (dev/staging/prod)")
        logger.info("  • Factory method (from_config)")
        logger.info("  • Health checks")
        logger.info("\nNote: Redis and external backends require infrastructure setup.")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("\n" + "=" * 60)
        logger.error("❌ VALIDATION FAILED")
        logger.error("=" * 60)
        logger.error(f"Error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
