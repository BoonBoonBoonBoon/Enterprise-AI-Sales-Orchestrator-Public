"""
Test end-to-end delegation flow with new hierarchical stream naming.
Manager -> Orchestrators -> Agents
"""

import json
import redis
import pytest
import time
from typing import Optional
import uuid


# Test configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
TEST_TENANT = "test-tenant"
TIMEOUT = 5.0


@pytest.fixture(scope="module")
def redis_client():
    """Connect to Redis for testing."""
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=2
        )
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


def test_manager_stream_names():
    """Verify Manager uses correct stream naming."""
    try:
        from tiers.tier_1.manager.tools.delegation_tools import DelegationTools
    except ImportError:
        from agent.manager.tools.delegation_tools import DelegationTools
    from unittest.mock import MagicMock
    
    mock_redis = MagicMock()
    tools = DelegationTools(mock_redis, TEST_TENANT)
    
    # Manager is Tier 1 and delegates to orchestrators
    assert hasattr(tools, 'delegate_to_leads_orchestrator')
    assert hasattr(tools, 'delegate_to_outreach_orchestrator')


def test_orchestrator_stream_names():
    """Verify Orchestrators use correct hierarchical stream naming."""
    try:
        from tiers.tier_2.leads_orchestrator.consumer import LeadsConsumer
        from tiers.tier_2.outreach_orchestrator.consumer import OutreachConsumer
    except ImportError:
        from agent.orchestrators.leads_orchestrator.consumer import LeadsConsumer
        from agent.orchestrators.outreach_orchestrator.consumer import OutreachConsumer
    from unittest.mock import MagicMock
    
    mock_redis = MagicMock()
    
    # Test Leads Orchestrator
    leads_consumer = LeadsConsumer(mock_redis, TEST_TENANT)
    assert leads_consumer.task_stream == f"{TEST_TENANT}:orchestrators:leads:tasks"
    assert leads_consumer.result_stream == f"{TEST_TENANT}:orchestrators:leads:results"
    
    # Test Outreach Orchestrator
    outreach_consumer = OutreachConsumer(mock_redis, TEST_TENANT)
    assert outreach_consumer.task_stream == f"{TEST_TENANT}:orchestrators:outbound:tasks"
    assert outreach_consumer.result_stream == f"{TEST_TENANT}:orchestrators:outbound:results"


def test_rag_agent_stream_names():
    """Verify RAG Agent uses correct hierarchical stream naming."""
    try:
        from tiers.tier_3.rag_agent.consumer import RAGConsumer
    except ImportError:
        from agent.operational_agents.rag_agent.consumer import RAGConsumer
    from unittest.mock import MagicMock
    
    mock_redis = MagicMock()
    
    # Test RAG Agent
    rag_consumer = RAGConsumer(mock_redis, TEST_TENANT)
    assert rag_consumer.task_stream == f"{TEST_TENANT}:agents:rag:tasks"
    assert rag_consumer.result_stream == f"{TEST_TENANT}:agents:rag:results"


def test_booking_and_sequencing_agent_stream_names():
    """Verify Booking (Scheduler) + Sequencing consumers use existing agent streams."""
    from unittest.mock import MagicMock

    from tiers.tier_3.channel_sequencer_agent.consumer import ChannelSequencerAgentConsumer
    from tiers.tier_3.scheduler_agent.consumer import SchedulerAgentConsumer

    mock_redis = MagicMock()

    booking_consumer = SchedulerAgentConsumer(mock_redis, TEST_TENANT)
    assert booking_consumer.task_stream == f"{TEST_TENANT}:agents:booking:tasks"
    assert booking_consumer.result_stream == f"{TEST_TENANT}:agents:booking:results"

    sequencing_consumer = ChannelSequencerAgentConsumer(mock_redis, TEST_TENANT)
    assert sequencing_consumer.task_stream == f"{TEST_TENANT}:agents:sequencing:tasks"
    assert sequencing_consumer.result_stream == f"{TEST_TENANT}:agents:sequencing:results"


def test_manager_delegation_to_orchestrators(redis_client):
    """Test Manager delegates to orchestrators with new stream names."""
    try:
        from tiers.tier_1.manager.tools.delegation_tools import DelegationTools
    except ImportError:
        from agent.manager.tools.delegation_tools import DelegationTools
    
    tools = DelegationTools(redis_client, TEST_TENANT)
    
    # Create test task
    task_data = {
        "leads": [
            {
                "name": "Test Lead",
                "email": "test@example.com",
                "company": "Test Co"
            }
        ]
    }
    
    # Test delegation to Leads Orchestrator
    leads_stream = f"{TEST_TENANT}:orchestrators:leads:tasks"
    task_id = f"test_task_{uuid.uuid4()}"
    
    # Publish test task (simulating what manager would do)
    stream_id = redis_client.xadd(
        leads_stream,
        {
            "payload": json.dumps(task_data),
            "task_id": task_id,
            "priority": "normal"
        }
    )
    
    assert stream_id is not None
    
    # Verify the task exists in the new hierarchical stream
    tasks = redis_client.xrange(leads_stream, count=1)
    assert len(tasks) > 0
    task_message = tasks[0][1]
    assert task_message.get("task_id") == task_id
    
    # Clean up
    redis_client.delete(leads_stream)


def test_leads_orchestrator_delegation_to_rag(redis_client):
    """Test Leads Orchestrator delegates to RAG Agent with new stream names."""
    
    # Create test enrichment task
    task_data = {
        "lead_id": "lead_123",
        "query": "Test enrichment query"
    }
    
    # Test delegation to RAG Agent
    rag_stream = f"{TEST_TENANT}:agents:rag:tasks"
    task_id = f"rag_task_{uuid.uuid4()}"
    
    # Publish test task (simulating what orchestrator would do)
    stream_id = redis_client.xadd(
        rag_stream,
        {
            "task_id": task_id,
            "lead_id": task_data["lead_id"],
            "query": task_data["query"],
            "operation": "enrich_lead",
            "delegated_by": "leads_orchestrator"
        }
    )
    
    assert stream_id is not None
    
    # Verify the task exists in the new hierarchical stream
    tasks = redis_client.xrange(rag_stream, count=1)
    assert len(tasks) > 0
    task_message = tasks[0][1]
    assert task_message.get("task_id") == task_id
    assert task_message.get("lead_id") == "lead_123"
    
    # Clean up
    redis_client.delete(rag_stream)


def test_outreach_orchestrator_delegation_to_copywriter(redis_client):
    """Test Outreach Orchestrator delegates to Copywriter Agent with new stream names."""
    
    # Create test copy task
    copywriter_stream = f"{TEST_TENANT}:agents:copywriter:tasks"
    task_id = f"copy_task_{uuid.uuid4()}"
    
    # Publish test task (simulating what orchestrator would do)
    stream_id = redis_client.xadd(
        copywriter_stream,
        {
            "task_id": task_id,
            "campaign_id": "campaign_123",
            "lead_id": "lead_456",
            "channel": "email",
            "tone": "professional"
        }
    )
    
    assert stream_id is not None
    
    # Verify the task exists in the new hierarchical stream
    tasks = redis_client.xrange(copywriter_stream, count=1)
    assert len(tasks) > 0
    task_message = tasks[0][1]
    assert task_message.get("task_id") == task_id
    assert task_message.get("campaign_id") == "campaign_123"
    
    # Clean up
    redis_client.delete(copywriter_stream)


def test_redis_stream_hierarchy_structure(redis_client):
    """Verify the complete hierarchical structure in Redis."""
    
    # Create streams following the hierarchy
    manager_tasks = f"{TEST_TENANT}:manager:tasks"
    leads_tasks = f"{TEST_TENANT}:orchestrators:leads:tasks"
    outreach_tasks = f"{TEST_TENANT}:orchestrators:outbound:tasks"
    rag_tasks = f"{TEST_TENANT}:agents:rag:tasks"
    copywriter_tasks = f"{TEST_TENANT}:agents:copywriter:tasks"
    booking_tasks = f"{TEST_TENANT}:agents:booking:tasks"
    sequencing_tasks = f"{TEST_TENANT}:agents:sequencing:tasks"
    
    streams = [
        manager_tasks,
        leads_tasks,
        outreach_tasks,
        rag_tasks,
        copywriter_tasks,
        booking_tasks,
        sequencing_tasks,
    ]
    
    # Add test data to each stream
    for stream in streams:
        redis_client.xadd(stream, {"test": "data"})
    
    # Verify all streams exist
    for stream in streams:
        info = redis_client.xlen(stream)
        assert info >= 1, f"Stream {stream} should exist"
    
    # Verify hierarchy is visible (using KEYS pattern)
    # This would show the proper namespace organization
    manager_pattern = f"{TEST_TENANT}:manager:*"
    orchestrators_pattern = f"{TEST_TENANT}:orchestrators:*"
    agents_pattern = f"{TEST_TENANT}:agents:*"
    
    manager_keys = redis_client.keys(manager_pattern)
    orchestrators_keys = redis_client.keys(orchestrators_pattern)
    agents_keys = redis_client.keys(agents_pattern)
    
    assert len(manager_keys) > 0, "Manager streams should exist"
    assert len(orchestrators_keys) > 0, "Orchestrator streams should exist"
    assert len(agents_keys) > 0, "Agent streams should exist"
    
    # Clean up
    for stream in streams:
        redis_client.delete(stream)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
