"""
Integration tests for Redis stream operations.

Tests XADD, XREADGROUP, XACK, XLEN and other Redis stream commands.
"""

import pytest
import redis
import os
import uuid
from datetime import datetime


@pytest.fixture
def redis_client():
    """Provide Redis client for testing."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    client = redis.from_url(redis_url, decode_responses=True)
    
    # Verify connection
    client.ping()
    try:
        yield client
    finally:
        # Cleanup test streams
        for key in client.scan_iter("test:*"):
            client.delete(key)
        try:
            client.close()
        except Exception:
            pass
        try:
            client.connection_pool.disconnect()
        except Exception:
            pass


@pytest.mark.integration
class TestRedisStreamOperations:
    """Test Redis stream operations used by the system."""
    
    def test_xadd_creates_message(self, redis_client):
        """Test XADD creates a message in a stream."""
        stream = f"test:stream:{uuid.uuid4()}"
        
        message_id = redis_client.xadd(stream, {"data": "test_value"})
        
        assert message_id is not None
        assert redis_client.xlen(stream) == 1
    
    def test_xreadgroup_reads_message(self, redis_client):
        """Test XREADGROUP can read messages from consumer group."""
        stream = f"test:stream:{uuid.uuid4()}"
        group = "test_group"
        consumer = "test_consumer"
        
        # Create stream and add message
        redis_client.xadd(stream, {"data": "test"})
        
        # Create consumer group
        try:
            redis_client.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError:
            pass  # Group already exists
        
        # Read message
        messages = redis_client.xreadgroup(
            group, consumer,
            {stream: ">"},
            count=1,
            block=1000
        )
        
        assert len(messages) > 0
        assert messages[0][0] == stream
        assert len(messages[0][1]) > 0
    
    def test_xack_acknowledges_message(self, redis_client):
        """Test XACK acknowledges processed messages."""
        stream = f"test:stream:{uuid.uuid4()}"
        group = "test_group"
        consumer = "test_consumer"
        
        # Create stream and message
        message_id = redis_client.xadd(stream, {"data": "test"})
        
        # Create consumer group
        try:
            redis_client.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError:
            pass
        
        # Read message
        messages = redis_client.xreadgroup(group, consumer, {stream: ">"}, count=1)
        
        # Acknowledge message
        ack_count = redis_client.xack(stream, group, message_id)
        
        assert ack_count == 1
    
    def test_xpending_shows_unacknowledged_messages(self, redis_client):
        """Test XPENDING shows pending (unacknowledged) messages."""
        stream = f"test:stream:{uuid.uuid4()}"
        group = "test_group"
        consumer = "test_consumer"
        
        # Create stream and message
        redis_client.xadd(stream, {"data": "test"})
        
        # Create consumer group
        try:
            redis_client.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError:
            pass
        
        # Read message without acknowledging
        redis_client.xreadgroup(group, consumer, {stream: ">"}, count=1)
        
        # Check pending
        pending = redis_client.xpending(stream, group)
        
        assert pending['pending'] == 1
    
    def test_xlen_returns_stream_length(self, redis_client):
        """Test XLEN returns correct stream length."""
        stream = f"test:stream:{uuid.uuid4()}"
        
        # Add multiple messages
        for i in range(5):
            redis_client.xadd(stream, {"index": str(i)})
        
        length = redis_client.xlen(stream)
        
        assert length == 5
    
    def test_stream_trimming(self, redis_client):
        """Test stream can be trimmed to limit size."""
        stream = f"test:stream:{uuid.uuid4()}"
        
        # Add 10 messages
        for i in range(10):
            redis_client.xadd(stream, {"index": str(i)})
        
        # Trim to keep only 5
        redis_client.xtrim(stream, maxlen=5, approximate=False)
        
        length = redis_client.xlen(stream)
        
        assert length == 5


@pytest.mark.integration
class TestRedisConsumerGroups:
    """Test Redis consumer group functionality."""
    
    def test_consumer_group_creation(self, redis_client):
        """Test creating a consumer group."""
        stream = f"test:stream:{uuid.uuid4()}"
        group = "test_group"
        
        # Create stream
        redis_client.xadd(stream, {"data": "test"})
        
        # Create group
        result = redis_client.xgroup_create(stream, group, id="0", mkstream=True)
        
        assert result is True
    
    def test_multiple_consumers_in_group(self, redis_client):
        """Test multiple consumers can read from same group."""
        stream = f"test:stream:{uuid.uuid4()}"
        group = "test_group"
        
        # Add messages
        for i in range(6):
            redis_client.xadd(stream, {"index": str(i)})
        
        # Create group
        try:
            redis_client.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError:
            pass
        
        # Read with consumer 1
        msgs1 = redis_client.xreadgroup(group, "consumer1", {stream: ">"}, count=3)
        
        # Read with consumer 2
        msgs2 = redis_client.xreadgroup(group, "consumer2", {stream: ">"}, count=3)
        
        # Each consumer should get different messages
        assert len(msgs1[0][1]) == 3
        assert len(msgs2[0][1]) == 3
    
    def test_consumer_lag_calculation(self, redis_client):
        """Test calculating consumer group lag."""
        stream = f"test:stream:{uuid.uuid4()}"
        group = "test_group"
		
        # Create group before adding messages so reads with ">" see new entries
        try:
            redis_client.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError:
            pass
		
        # Add 10 messages
        for i in range(10):
            redis_client.xadd(stream, {"index": str(i)})
        
        # Read only 5 messages
        redis_client.xreadgroup(group, "consumer", {stream: ">"}, count=5)
        
        # Calculate lag (total - read)
        stream_len = redis_client.xlen(stream)
        pending = redis_client.xpending(stream, group)
        
        # Pending should reflect the 5 unacked messages we read
        assert pending['pending'] == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
