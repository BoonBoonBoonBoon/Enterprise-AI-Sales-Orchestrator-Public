"""
Comprehensive Redis CRUD Verification Test

Tests end-to-end Redis stream operations across all agent streams:
- XADD: Add messages to streams
- XREAD: Read messages without consumer groups
- XREADGROUP: Read messages with consumer groups
- XACK: Acknowledge processed messages
- XPENDING: Check pending messages
- XLEN: Get stream length
- Backpressure: Verify stream length limits
"""

import pytest
import os
import time
import uuid
from datetime import datetime
from typing import Dict, Any

from services.redis.client import RedisStreamsClient
from services.redis.stream_registry import StreamRegistry, Tier, StreamType


@pytest.fixture
def redis_pubsub():
    """Provide RedisStreamsClient for testing."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    client = RedisStreamsClient(url=redis_url, namespace="test")
    
    # Verify connection
    client.client.ping()
    
    yield client
    
    # Cleanup test streams
    for key in client.client.scan_iter("test:*"):
        client.client.delete(key)


@pytest.fixture
def stream_registry():
    """Provide stream registry."""
    return StreamRegistry()


def generate_test_message(message_type: str = "task") -> Dict[str, Any]:
    """Generate test message with envelope structure."""
    return {
        "task_id": str(uuid.uuid4()),
        "tenant_id": "test-tenant",
        "payload": {
            "test_data": f"test_{message_type}_{datetime.utcnow().isoformat()}",
            "type": message_type
        },
        "metadata": {
            "source": "test_suite",
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": str(uuid.uuid4())
        }
    }


@pytest.mark.integration
class TestRedisCRUDVerification:
    """Comprehensive CRUD verification across all agent streams."""
    
    def test_crud_rag_agent_stream(self, redis_pubsub):
        """Test CRUD operations on RAG agent task/result streams."""
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:rag:tasks"
        result_stream = f"{tenant_id}:agents:rag:results"
        consumer_group = "rag-workers"
        consumer_name = "test-rag-consumer"
        
        # CREATE (XADD): Add task to stream
        task_message = generate_test_message("rag_query")
        task_id = redis_pubsub.xadd(
            task_stream,
            task_message,
            maxlen=1000
        )
        assert task_id is not None
        assert redis_pubsub.xlen(task_stream) == 1
        
        # READ (XREADGROUP): Read task with consumer group
        redis_pubsub.create_consumer_group(task_stream, consumer_group, mkstream=True)
        messages = redis_pubsub.xreadgroup(
            consumer_group,
            consumer_name,
            {task_stream: ">"},
            count=1,
            block=100
        )
        assert len(messages) == 1
        assert messages[0][0] == task_stream
        message_id, message_data = messages[0][1][0]
        assert message_data["task_id"] == task_message["task_id"]
        
        # VERIFY PENDING: Check message is pending
        pending = redis_pubsub.xpending(task_stream, consumer_group)
        assert pending["pending"] == 1
        
        # UPDATE (XACK): Acknowledge processed message
        ack_count = redis_pubsub.xack(task_stream, consumer_group, message_id)
        assert ack_count == 1
        
        # VERIFY ACK: Pending should be 0
        pending_after = redis_pubsub.xpending(task_stream, consumer_group)
        assert pending_after["pending"] == 0
        
        # CREATE result message
        result_message = generate_test_message("rag_result")
        result_id = redis_pubsub.xadd(result_stream, result_message)
        assert result_id is not None
        
        # DELETE (stream cleanup): Verify XLEN
        assert redis_pubsub.xlen(result_stream) == 1
    
    def test_crud_persistence_agent_stream(self, redis_pubsub):
        """Test CRUD operations on Persistence agent streams."""
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:persistence:tasks"
        result_stream = f"{tenant_id}:agents:persistence:results"
        consumer_group = "persistence-workers"
        consumer_name = "test-persistence-consumer"
        
        # CREATE: Add write task
        write_task = generate_test_message("write")
        write_task["payload"]["operation"] = "write"
        write_task["payload"]["table"] = "leads"
        write_task["payload"]["data"] = {"name": "Test Lead", "email": "test@example.com"}
        
        task_id = redis_pubsub.xadd(task_stream, write_task, maxlen=1000)
        assert task_id is not None
        
        # READ with consumer group
        redis_pubsub.create_consumer_group(task_stream, consumer_group, mkstream=True)
        messages = redis_pubsub.xreadgroup(
            consumer_group,
            consumer_name,
            {task_stream: ">"},
            count=1,
            block=100
        )
        assert len(messages) == 1
        message_id, message_data = messages[0][1][0]
        
        # VERIFY operation
        assert message_data["payload"]["operation"] == "write"
        assert message_data["payload"]["table"] == "leads"
        
        # ACK
        ack_count = redis_pubsub.xack(task_stream, consumer_group, message_id)
        assert ack_count == 1
        
        # Verify result stream can be written
        result = generate_test_message("write_result")
        result["payload"]["status"] = "success"
        result_id = redis_pubsub.xadd(result_stream, result)
        assert result_id is not None
    
    def test_crud_copywriter_agent_stream(self, redis_pubsub):
        """Test CRUD operations on Copywriter agent streams."""
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:copywriter:tasks"
        result_stream = f"{tenant_id}:agents:copywriter:results"
        consumer_group = "copywriter-workers"
        consumer_name = "test-copywriter-consumer"
        
        # CREATE: Add generation task
        gen_task = generate_test_message("generate")
        gen_task["payload"]["template"] = "cold_email"
        gen_task["payload"]["context"] = {"lead_name": "John Doe", "company": "Acme Corp"}
        
        task_id = redis_pubsub.xadd(task_stream, gen_task, maxlen=1000)
        assert task_id is not None
        
        # READ
        redis_pubsub.create_consumer_group(task_stream, consumer_group, mkstream=True)
        messages = redis_pubsub.xreadgroup(
            consumer_group,
            consumer_name,
            {task_stream: ">"},
            count=1,
            block=100
        )
        assert len(messages) == 1
        message_id, message_data = messages[0][1][0]
        
        # ACK
        ack_count = redis_pubsub.xack(task_stream, consumer_group, message_id)
        assert ack_count == 1
    
    def test_multi_stream_xread(self, redis_pubsub):
        """Test XREAD across multiple streams simultaneously."""
        tenant_id = "test-tenant"
        rag_stream = f"{tenant_id}:agents:rag:results"
        persistence_stream = f"{tenant_id}:agents:persistence:results"
        
        # Add messages to both streams
        rag_msg = generate_test_message("rag_result")
        persist_msg = generate_test_message("persist_result")
        
        redis_pubsub.xadd(rag_stream, rag_msg)
        redis_pubsub.xadd(persistence_stream, persist_msg)
        
        # Read from both streams
        messages = redis_pubsub.xread(
            {rag_stream: "0-0", persistence_stream: "0-0"},
            count=2,
            block=100
        )
        
        assert len(messages) == 2
        stream_names = [msg[0] for msg in messages]
        assert rag_stream in stream_names
        assert persistence_stream in stream_names
    
    def test_stream_maxlen_trimming(self, redis_pubsub):
        """Test MAXLEN trimming keeps streams bounded."""
        tenant_id = "test-tenant"
        stream = f"{tenant_id}:agents:test:tasks"
        maxlen = 10
        
        # Add 15 messages with MAXLEN=10
        for i in range(15):
            msg = generate_test_message(f"msg_{i}")
            redis_pubsub.xadd(stream, msg, maxlen=maxlen)
        
        # Stream should have at most ~10 messages (Redis allows slight overage)
        length = redis_pubsub.xlen(stream)
        assert length <= maxlen + 1  # Redis MAXLEN ~ allows 1 extra
    
    def test_consumer_group_multiple_consumers(self, redis_pubsub):
        """Test multiple consumers in same group don't read duplicate messages."""
        tenant_id = "test-tenant"
        stream = f"{tenant_id}:agents:test:tasks"
        group = "test-group"
        consumer1 = "consumer-1"
        consumer2 = "consumer-2"
        
        # Add 10 messages
        for i in range(10):
            redis_pubsub.xadd(stream, generate_test_message(f"msg_{i}"))
        
        # Create consumer group
        redis_pubsub.create_consumer_group(stream, group, mkstream=True)
        
        # Consumer 1 reads 5 messages
        msgs1 = redis_pubsub.xreadgroup(group, consumer1, {stream: ">"}, count=5)
        consumer1_ids = [msg[0] for msg in msgs1[0][1]] if msgs1 else []
        
        # Consumer 2 reads remaining 5 messages
        msgs2 = redis_pubsub.xreadgroup(group, consumer2, {stream: ">"}, count=5)
        consumer2_ids = [msg[0] for msg in msgs2[0][1]] if msgs2 else []
        
        # No overlap
        assert len(set(consumer1_ids) & set(consumer2_ids)) == 0
        assert len(consumer1_ids) + len(consumer2_ids) == 10
    
    def test_xpending_detailed(self, redis_pubsub):
        """Test XPENDING returns detailed pending message info."""
        tenant_id = "test-tenant"
        stream = f"{tenant_id}:agents:test:tasks"
        group = "test-group"
        consumer = "test-consumer"
        
        # Add message
        redis_pubsub.xadd(stream, generate_test_message("test"))
        redis_pubsub.create_consumer_group(stream, group, mkstream=True)
        
        # Read but don't ACK
        msgs = redis_pubsub.xreadgroup(group, consumer, {stream: ">"}, count=1)
        message_id = msgs[0][1][0][0]
        
        # Check pending summary
        pending = redis_pubsub.xpending(stream, group)
        assert pending["pending"] == 1
        assert pending["min"] == message_id
        assert pending["max"] == message_id
        
        # ACK and verify
        redis_pubsub.xack(stream, group, message_id)
        pending_after = redis_pubsub.xpending(stream, group)
        assert pending_after["pending"] == 0
    
    def test_stream_registry_all_agents(self, stream_registry):
        """Verify stream registry has definitions for all Tier 3 agents."""
        tenant_id = "test-tenant"
        
        # RAG Agent
        rag_tasks = stream_registry.get_stream("rag", StreamType.TASKS)
        assert rag_tasks is not None
        assert rag_tasks.tier == Tier.AGENT
        assert "rag" in rag_tasks.get_key(tenant_id)
        
        # Persistence Agent
        persist_tasks = stream_registry.get_stream("persistence", StreamType.TASKS)
        assert persist_tasks is not None
        assert persist_tasks.tier == Tier.AGENT
        
        # Copywriter Agent
        copy_tasks = stream_registry.get_stream("copywriter", StreamType.TASKS)
        assert copy_tasks is not None
        assert copy_tasks.tier == Tier.AGENT
    
    def test_backpressure_detection(self, redis_pubsub):
        """Test ability to detect when streams are full (backpressure)."""
        tenant_id = "test-tenant"
        stream = f"{tenant_id}:agents:test:tasks"
        threshold = 100
        
        # Fill stream
        for i in range(150):
            redis_pubsub.xadd(stream, generate_test_message(f"msg_{i}"))
        
        # Check if over threshold
        length = redis_pubsub.xlen(stream)
        assert length > threshold
        
        # This would trigger backpressure mechanism
        # (to be implemented in next step)


@pytest.mark.integration
class TestRedisFailureScenarios:
    """Test Redis failure scenarios and recovery."""
    
    def test_consumer_group_already_exists(self, redis_pubsub):
        """Test creating consumer group that already exists doesn't error."""
        stream = "test:stream:duplicate-group"
        group = "test-group"
        
        # Create group first time
        redis_pubsub.xadd(stream, {"data": "test"})
        redis_pubsub.create_consumer_group(stream, group, mkstream=True)
        
        # Create again - should not raise error
        redis_pubsub.create_consumer_group(stream, group, mkstream=True)
    
    def test_read_empty_stream(self, redis_pubsub):
        """Test reading from empty stream returns empty list."""
        stream = "test:stream:empty"
        
        messages = redis_pubsub.xread({stream: "0-0"}, count=1, block=100)
        assert messages == [] or len(messages[0][1]) == 0
    
    def test_ack_nonexistent_message(self, redis_pubsub):
        """Test ACKing non-existent message returns 0."""
        stream = "test:stream:noack"
        group = "test-group"
        
        redis_pubsub.xadd(stream, {"data": "test"})
        redis_pubsub.create_consumer_group(stream, group, mkstream=True)
        
        # ACK fake message
        ack_count = redis_pubsub.xack(stream, group, "99999999-0")
        assert ack_count == 0
