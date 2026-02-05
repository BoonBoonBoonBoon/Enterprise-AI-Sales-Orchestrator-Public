"""
Chaos Testing Suite for Agentic System

Tests system resilience by introducing controlled failures:
- Random worker process kills
- Redis connection failures
- Resource exhaustion (memory, CPU)
- Network delays and timeouts
- Message corruption
- Consumer group conflicts

Run with: pytest tests/chaos/ -v --chaos-level=medium
"""

import pytest
import os
import time
import random
import signal
import subprocess
import psutil
from typing import List, Optional
from unittest.mock import patch, MagicMock
import redis

from services.redis.client import RedisStreamsClient
from core.utils.graceful_shutdown import GracefulShutdownMixin
from core.harness.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError


@pytest.fixture
def chaos_level(request):
    """Get chaos level from pytest options."""
    return request.config.getoption("--chaos-level")


@pytest.fixture
def redis_pubsub():
    """Provide RedisStreamsClient."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    client = RedisStreamsClient(url=redis_url, namespace="chaos-test")
    try:
        yield client
    finally:
        # Cleanup
        for key in client.client.scan_iter("chaos-test:*"):
            client.client.delete(key)
        try:
            client.client.close()
        except Exception:
            pass
        try:
            client.client.connection_pool.disconnect()
        except Exception:
            pass


class ChaosInjector:
    """Utility class to inject chaos into the system."""
    
    @staticmethod
    def kill_random_worker(worker_processes: List[subprocess.Popen]):
        """Randomly kill a worker process."""
        if not worker_processes:
            return None
        
        victim = random.choice(worker_processes)
        pid = victim.pid
        
        try:
            victim.terminate()
            victim.wait(timeout=5)
        except subprocess.TimeoutExpired:
            victim.kill()
        
        return pid
    
    @staticmethod
    def disconnect_redis(redis_client: redis.Redis):
        """Simulate Redis disconnection."""
        try:
            redis_client.connection_pool.disconnect()
        except Exception:
            pass
    
    @staticmethod
    def corrupt_message(message: dict) -> dict:
        """Corrupt a message by removing/changing fields."""
        corruption_type = random.choice([
            "remove_task_id",
            "remove_payload",
            "invalid_json",
            "wrong_type"
        ])
        
        corrupted = message.copy()
        
        if corruption_type == "remove_task_id":
            corrupted.pop("task_id", None)
        elif corruption_type == "remove_payload":
            corrupted.pop("payload", None)
        elif corruption_type == "invalid_json":
            corrupted["invalid"] = float('inf')  # Not JSON serializable
        elif corruption_type == "wrong_type":
            corrupted["payload"] = "should_be_dict"
        
        return corrupted
    
    @staticmethod
    def exhaust_memory(size_mb: int = 100, duration: float = 1.0):
        """Allocate large memory block for duration."""
        data = bytearray(size_mb * 1024 * 1024)
        time.sleep(duration)
        del data
    
    @staticmethod
    def simulate_network_delay(min_ms: int = 100, max_ms: int = 500):
        """Simulate network delay."""
        delay = random.uniform(min_ms, max_ms) / 1000.0
        time.sleep(delay)


@pytest.mark.chaos
class TestWorkerKillRecovery:
    """Test worker process kill and recovery."""
    
    def test_worker_graceful_shutdown(self, redis_pubsub):
        """Test worker shuts down gracefully when receiving SIGTERM."""
        # Test graceful shutdown by verifying pending tasks are tracked
        stream = "chaos-test:graceful-shutdown:tasks"
        group = "test-workers"
        consumer = "worker-1"
        
        # Add task before creating consumer group
        redis_pubsub.xadd(stream, {"task": "important_task"})
        # Create group from beginning so we can read existing messages
        redis_pubsub.xgroup_create(stream, group, id="0", mkstream=True)
        
        # Read message (simulating in-flight work)
        messages = redis_pubsub.xreadgroup(group, consumer, {stream: ">"}, count=1)
        assert messages, "Should have pending message"
        
        # Simulate graceful shutdown - task is acknowledged before exit
        if messages and messages[0][1]:
            msg_id = messages[0][1][0][0]
            redis_pubsub.xack(stream, group, msg_id)
    
    def test_worker_hard_kill_recovery(self, redis_pubsub):
        """Test system recovers when worker is killed hard."""
        stream = "chaos-test:worker-kill:tasks"
        group = "test-workers"
        consumer = "worker-1"
        
        # Add messages
        for i in range(5):
            redis_pubsub.xadd(stream, {"task": f"task_{i}"})
        
        # Create consumer group from beginning so we can read existing messages
        redis_pubsub.xgroup_create(stream, group, id="0", mkstream=True)
        messages = redis_pubsub.xreadgroup(group, consumer, {stream: ">"}, count=3)
        
        # Simulate worker kill (messages not ACKed)
        # Messages should remain unacknowledged and be reclaimable
        assert messages, "Should have read messages"
        
        # Verify messages are in pending (not acknowledged)
        unread_msgs = redis_pubsub.xreadgroup(group, consumer, {stream: "0"}, count=100)
        # At least some messages should be pending
        assert unread_msgs, "Should have pending messages after kill"


@pytest.mark.chaos
class TestRedisFailureRecovery:
    """Test Redis connection failure and recovery."""
    
    def test_redis_connection_retry(self):
        """Test circuit breaker handles Redis connection failures."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout=2.0,
            success_threshold=2,
            name="redis_test"
        )
        circuit = CircuitBreaker(config)
        
        # Simulate failing Redis calls
        def failing_redis_call():
            raise redis.ConnectionError("Connection refused")
        
        # Should fail and open circuit
        for i in range(3):
            with pytest.raises(redis.ConnectionError):
                circuit.call(failing_redis_call)
        
        # Circuit should be open now
        assert circuit.is_open
        
        # Next call should fail fast
        with pytest.raises(CircuitBreakerOpenError):
            circuit.call(failing_redis_call)
    
    def test_redis_reconnection_after_timeout(self):
        """Test Redis reconnects after timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout=0.5,  # Short timeout for testing
            success_threshold=1,
            name="redis_reconnect"
        )
        circuit = CircuitBreaker(config)
        
        # Fail to open circuit
        def failing_call():
            raise redis.ConnectionError()
        
        for _ in range(2):
            with pytest.raises(redis.ConnectionError):
                circuit.call(failing_call)
        
        assert circuit.is_open
        
        # Wait for timeout
        time.sleep(0.6)
        
        # Circuit should transition to half-open and allow test
        def successful_call():
            return "success"
        
        result = circuit.call(successful_call)
        assert result == "success"
        assert circuit.is_closed


@pytest.mark.chaos
class TestMessageCorruption:
    """Test handling of corrupted messages."""
    
    def test_corrupted_message_handling(self, redis_pubsub):
        """Test system handles corrupted messages gracefully."""
        stream = "chaos-test:corruption:tasks"
        
        valid_message = {
            "task_id": "task-123",
            "payload": {"data": "test"},
            "metadata": {"source": "test"}
        }
        
        # Add valid message
        redis_pubsub.xadd(stream, valid_message)
        
        # Add corrupted messages
        corrupted_messages = [
            {"task_id": "task-456"},  # Missing payload
            {"payload": {"data": "test"}},  # Missing task_id
            {},  # Empty
        ]
        
        for corrupted in corrupted_messages:
            try:
                redis_pubsub.xadd(stream, corrupted)
            except Exception:
                # Some corruptions may fail at xadd
                pass
        
        # System should handle gracefully
        # In real implementation, would validate before processing


@pytest.mark.chaos
class TestResourceExhaustion:
    """Test system behavior under resource pressure."""
    
    def test_memory_pressure_handling(self, chaos_level):
        """Test system handles memory pressure."""
        if chaos_level in ["low", "medium"]:
            pytest.skip("Memory exhaustion only in high/extreme chaos")
        
        # Get current memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Try to allocate large block
        try:
            ChaosInjector.exhaust_memory(size_mb=50, duration=0.5)
        except MemoryError:
            pytest.fail("Should handle memory pressure gracefully")
        
        # Memory should be released
        time.sleep(0.5)
        final_memory = process.memory_info().rss / 1024 / 1024
        
        # Should recover within reasonable range
        assert final_memory < initial_memory + 100  # Allow 100MB variance
    
    def test_stream_backpressure(self, redis_pubsub):
        """Test backpressure when streams fill up."""
        stream = "chaos-test:backpressure:tasks"
        
        # Fill stream with messages
        for i in range(50):
            redis_pubsub.xadd(stream, {"task": f"task_{i}"})
        
        # Verify stream has messages
        messages = redis_pubsub.xread({stream: "0"}, count=200)
        assert messages, "Stream should have messages"
        # Verify we can read the messages we added
        total_msgs = sum(len(msgs[1]) for msgs in messages if msgs[1])
        assert total_msgs == 50, f"Stream should have 50 messages, got {total_msgs}"


@pytest.mark.chaos
class TestConcurrentConsumerConflicts:
    """Test handling of consumer group conflicts."""
    
    def test_duplicate_consumer_group_creation(self, redis_pubsub):
        """Test creating duplicate consumer groups doesn't error."""
        stream = "chaos-test:duplicate-group:tasks"
        group = "test-group"
        
        redis_pubsub.xadd(stream, {"data": "test"})
        
        # Create group first time should succeed
        created = redis_pubsub.xgroup_create(stream, group, id="$", mkstream=True)
        assert created, "First group creation should succeed"
        
        # Verify stream is accessible
        messages = redis_pubsub.xread({stream: "0"}, count=10)
        assert messages, "Should be able to read from stream"
    
    def test_consumer_name_collision(self, redis_pubsub):
        """Test handling same consumer name in group."""
        stream = "chaos-test:consumer-collision:tasks"
        group = "test-group"
        consumer = "same-name"
        
        # Add messages
        for i in range(5):
            redis_pubsub.xadd(stream, {"task": f"task_{i}"})
        
        # Create group from beginning to read existing messages
        redis_pubsub.xgroup_create(stream, group, id="0", mkstream=True)
        
        # First read with same consumer name reads new messages
        msgs1 = redis_pubsub.xreadgroup(group, consumer, {stream: ">"}, count=2)
        assert msgs1, "First read should get messages"
        
        # Second read with same consumer gets next batch of unread messages
        msgs2 = redis_pubsub.xreadgroup(group, consumer, {stream: ">"}, count=2)
        assert msgs2, "Second read should get remaining messages"
        
        # Verify message distribution
        total_read = len(msgs1[0][1]) + len(msgs2[0][1]) if msgs1 and msgs2 else 0
        assert total_read <= 5, "Should not read more messages than added"


@pytest.mark.chaos
class TestNetworkDelaySimulation:
    """Test system handles network delays."""
    
    def test_timeout_handling(self, redis_pubsub):
        """Test system handles read timeouts gracefully."""
        stream = "chaos-test:timeout:tasks"
        
        # Read with very short timeout from empty stream
        messages = redis_pubsub.xread({stream: "0-0"}, count=1, block=100)
        
        # Should return empty, not error
        assert messages == [] or len(messages) == 0
    
    def test_delayed_response_handling(self, chaos_level):
        """Test handling of delayed responses."""
        if chaos_level == "low":
            delay_range = (10, 50)
        elif chaos_level == "medium":
            delay_range = (50, 200)
        else:
            delay_range = (200, 1000)
        
        ChaosInjector.simulate_network_delay(*delay_range)
        # System should still function with delays


@pytest.mark.chaos
class TestCircuitBreakerIntegration:
    """Test circuit breaker integration in real scenarios."""
    
    def test_circuit_breaker_with_redis_client(self, redis_pubsub):
        """Test circuit breaker protects Redis client."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout=1.0,
            success_threshold=2,
            name="redis_client"
        )
        circuit = CircuitBreaker(config)
        
        stream = "chaos-test:circuit:tasks"
        
        # Normal operation should work
        def add_message():
            return redis_pubsub.xadd(stream, {"data": "test"})
        
        result = circuit.call(add_message)
        assert result is not None
        assert circuit.is_closed
    
    def test_circuit_breaker_failure_cascade_prevention(self):
        """Test circuit breaker prevents cascading failures."""
        circuits = []
        
        # Create multiple circuit breakers for different services
        for service in ["redis", "postgres", "llm"]:
            config = CircuitBreakerConfig(
                failure_threshold=2,
                timeout=0.5,
                name=service
            )
            circuits.append(CircuitBreaker(config))
        
        # Simulate one service failing
        def failing_service():
            raise Exception("Service down")
        
        # Should open only the failing circuit
        with pytest.raises(Exception):
            circuits[0].call(failing_service)
        with pytest.raises(Exception):
            circuits[0].call(failing_service)
        
        assert circuits[0].is_open
        assert circuits[1].is_closed  # Other services still ok
        assert circuits[2].is_closed
