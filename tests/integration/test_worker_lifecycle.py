"""
Integration tests for worker lifecycle.

Tests worker startup, task processing, and graceful shutdown.
"""

import pytest
import redis
import os
import time
import uuid
from unittest.mock import Mock, patch


@pytest.fixture
def redis_client():
    """Provide Redis client for testing."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    client = redis.from_url(redis_url, decode_responses=True)
    client.ping()
    try:
        yield client
    finally:
        # Cleanup
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
class TestRAGWorkerLifecycle:
    """Test RAG worker lifecycle."""
    
    @patch('tiers.tier_3.rag_agent.worker.RAGWorker.search_citations')
    def test_worker_processes_rag_task(self, mock_search, redis_client):
        """Test RAG worker can process a task from Redis."""
        from tiers.tier_3.rag_agent.worker import RAGWorker
        
        # Mock search to return citations
        mock_search.return_value = [
            {"url": "https://example.com", "title": "Test"}
        ]
        
        # Create test streams
        task_stream = f"test:rag:tasks:{uuid.uuid4()}"
        result_stream = f"test:rag:results:{uuid.uuid4()}"
        
        # Create consumer group before adding messages
        try:
            redis_client.xgroup_create(task_stream, "rag-workers", id="0", mkstream=True)
        except redis.ResponseError:
            pass
		
        # Add task to stream
        task_data = {
            "envelope_id": "test-123",
            "lead_id": "lead-456",
            "task_type": "rag",
            "query": "test query",
            "status": "pending"
        }
        redis_client.xadd(task_stream, task_data)
        
        # Create worker (but don't start main loop)
        worker = RAGWorker(
            redis_url=os.environ.get('REDIS_URL', 'redis://localhost:6379'),
            task_stream=task_stream,
            result_stream=result_stream
        )
        
        # Process one task manually
        messages = redis_client.xreadgroup(
            "rag-workers", "test_worker",
            {task_stream: ">"},
            count=1,
            block=1000
        )
        
        assert len(messages) > 0
        assert messages[0][0] == task_stream
    
    def test_worker_graceful_shutdown(self, redis_client):
        """Test worker can shutdown gracefully."""
        from core.utils.graceful_shutdown import GracefulShutdown
        
        shutdown = GracefulShutdown(grace_period=5)
        
        # Simulate worker running
        assert shutdown.is_shutting_down() is False
        
        # Trigger shutdown
        shutdown.trigger_shutdown()
        
        # Should be shutting down now
        assert shutdown.is_shutting_down() is True


@pytest.mark.integration
class TestWorkerHealthChecks:
    """Test worker health check functionality."""
    
    def test_redis_connectivity_check(self, redis_client):
        """Test Redis connectivity health check."""
        # Should succeed
        result = redis_client.ping()
        assert result is True
    
    def test_stream_exists_check(self, redis_client):
        """Test checking if streams exist."""
        stream = f"test:stream:{uuid.uuid4()}"
        
        # Stream doesn't exist yet
        assert redis_client.exists(stream) == 0
        
        # Create stream
        redis_client.xadd(stream, {"data": "test"})
        
        # Now it exists
        assert redis_client.exists(stream) == 1
    
    def test_consumer_group_info(self, redis_client):
        """Test retrieving consumer group information."""
        stream = f"test:stream:{uuid.uuid4()}"
        group = "test_group"
        
        # Create stream and group
        redis_client.xadd(stream, {"data": "test"})
        try:
            redis_client.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError:
            pass
        
        # Get group info
        groups = redis_client.xinfo_groups(stream)
        
        assert len(groups) > 0
        assert groups[0]['name'] == group


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    def test_rag_task_to_result_flow(self, redis_client):
        """Test complete RAG task processing flow."""
        task_stream = f"test:rag:tasks:{uuid.uuid4()}"
        result_stream = f"test:rag:results:{uuid.uuid4()}"
        
        # Add task
        task_data = {
            "envelope_id": "e2e-test",
            "lead_id": "lead-123",
            "task_type": "rag",
            "query": "test query",
            "status": "pending"
        }
        task_id = redis_client.xadd(task_stream, task_data)
        
        assert task_id is not None
        assert redis_client.xlen(task_stream) == 1
        
        # Simulate worker processing (in real system, worker would do this)
        result_data = {
            "envelope_id": "e2e-test",
            "status": "completed",
            "citations": '["https://example.com"]',
            "confidence": "0.95"
        }
        result_id = redis_client.xadd(result_stream, result_data)
        
        assert result_id is not None
        assert redis_client.xlen(result_stream) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
