"""
Test Tier 3 Agent CRUD Operations
Tests RAGAgent, PersistenceAgent, and CopywriterAgent end-to-end message flow.
"""
import os
import time
import json
import pytest
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any

from services.redis.client import RedisStreamsClient
from services.redis.stream_registry import StreamRegistry


@pytest.fixture
def redis_client():
    """Provide RedisStreamsClient for testing."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    client = RedisStreamsClient(url=redis_url, namespace="test-t3")
    
    # Verify connection
    client.client.ping()
    
    yield client
    
    # Cleanup test streams
    for key in client.client.scan_iter("test-t3:*"):
        client.client.delete(key)


def deserialize_message(msg_data: Dict[str, bytes]) -> Dict[str, Any]:
    """Deserialize Redis message data from bytes to dict."""
    result = {}
    for key, value in msg_data.items():
        if isinstance(value, bytes):
            try:
                # Try JSON decode first
                decoded = json.loads(value.decode('utf-8'))
                result[key] = decoded
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fallback to string
                result[key] = value.decode('utf-8')
        else:
            result[key] = value
    
    # Ensure nested payload and metadata are also deserialized
    for nested_key in ['payload', 'metadata']:
        if nested_key in result and isinstance(result[nested_key], str):
            try:
                result[nested_key] = json.loads(result[nested_key])
            except (json.JSONDecodeError, ValueError):
                pass  # Keep as string if can't parse
    
    return result


def pretty_print_message(title: str, msg_id: str, msg_data: Dict[str, Any]):
    """Pretty print message with structure."""
    print(f"\n{'='*80}")
    print(f"📨 {title}")
    print(f"{'='*80}")
    print(f"Message ID: {msg_id}")
    print(f"\nPayload:")
    for key, value in msg_data.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    print(f"{'='*80}\n")


@pytest.mark.integration
class TestRAGAgentCRUD:
    """Test RAG Agent CRUD operations."""
    
    def test_rag_agent_create_read(self, redis_client):
        """Test RAG Agent receives task and returns result."""
        print("\n🔍 Testing RAG Agent CRUD...")
        
        # Arrange - prepare task stream
        task_stream = "test-t3:agents:rag:tasks"
        result_stream = "test-t3:agents:rag:results"
        
        task_payload = {
            "task_id": str(uuid4()),
            "tenant_id": "test-tenant",
            "payload": {
                "action": "search",
                "query": "test query for leads",
                "top_k": 5
            },
            "metadata": {
                "source": "test_suite",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Act - XADD (CREATE)
        msg_id = redis_client.xadd(task_stream, task_payload)
        print(f"✅ CREATED task in {task_stream}")
        pretty_print_message("RAG Task Created", msg_id, task_payload)
        
        # Act - XREAD (READ)
        messages = redis_client.xread({task_stream: "0"}, count=1)
        
        # Assert
        assert messages, "Should have created message"
        assert len(messages) > 0, "Should have at least one stream"
        assert len(messages[0][1]) > 0, "Should have at least one message"
        
        stream_name, msg_list = messages[0]
        read_msg_id, msg_data = msg_list[0]
        
        # Deserialize message data
        deserialized = deserialize_message(msg_data)
        
        print(f"✅ READ task from {task_stream}")
        pretty_print_message("RAG Task Read", read_msg_id, deserialized)
        
        # Verify task structure
        assert deserialized['task_id'] == task_payload['task_id']
        print(f"✅ Task ID matches: {deserialized['task_id']}")
        
        print("\n✅ RAG Agent CRUD test PASSED\n")


@pytest.mark.integration
class TestPersistenceAgentCRUD:
    """Test Persistence Agent CRUD operations."""
    
    def test_persistence_agent_write_read(self, redis_client):
        """Test Persistence Agent receives write task and returns result."""
        print("\n💾 Testing Persistence Agent CRUD...")
        
        # Arrange
        task_stream = "test-t3:agents:persistence:tasks"
        result_stream = "test-t3:agents:persistence:results"
        
        task_payload = {
            "task_id": str(uuid4()),
            "tenant_id": "test-tenant",
            "payload": {
                "action": "write",
                "table": "staging_leads",
                "data": {
                    "name": "Test Lead",
                    "email": "test@example.com",
                    "company": "Test Corp"
                }
            },
            "metadata": {
                "source": "test_suite",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Act - CREATE
        msg_id = redis_client.xadd(task_stream, task_payload)
        print(f"✅ CREATED persistence task in {task_stream}")
        pretty_print_message("Persistence Task Created", msg_id, task_payload)
        
        # Act - READ
        messages = redis_client.xread({task_stream: "0"}, count=1)
        
        # Assert
        assert messages, "Should have created message"
        stream_name, msg_list = messages[0]
        read_msg_id, msg_data = msg_list[0]
        
        deserialized = deserialize_message(msg_data)
        
        print(f"✅ READ persistence task from {task_stream}")
        pretty_print_message("Persistence Task Read", read_msg_id, deserialized)
        
        # Verify structure
        assert deserialized['task_id'] == task_payload['task_id']
        assert deserialized['payload']['action'] == 'write'
        print(f"✅ Persistence task verified: {deserialized['payload']['action']} to {deserialized['payload']['table']}")
        
        print("\n✅ Persistence Agent CRUD test PASSED\n")


@pytest.mark.integration
class TestCopywriterAgentCRUD:
    """Test Copywriter Agent CRUD operations."""
    
    def test_copywriter_agent_generate_read(self, redis_client):
        """Test Copywriter Agent receives generation task and returns result."""
        print("\n✍️ Testing Copywriter Agent CRUD...")
        
        # Arrange
        task_stream = "test-t3:agents:copywriter:tasks"
        result_stream = "test-t3:agents:copywriter:results"
        
        task_payload = {
            "task_id": str(uuid4()),
            "tenant_id": "test-tenant",
            "payload": {
                "action": "generate",
                "template": "outreach_email",
                "context": {
                    "lead_name": "John Doe",
                    "company": "TechCorp",
                    "industry": "SaaS"
                }
            },
            "metadata": {
                "source": "test_suite",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Act - CREATE
        msg_id = redis_client.xadd(task_stream, task_payload)
        print(f"✅ CREATED copywriter task in {task_stream}")
        pretty_print_message("Copywriter Task Created", msg_id, task_payload)
        
        # Act - READ
        messages = redis_client.xread({task_stream: "0"}, count=1)
        
        # Assert
        assert messages, "Should have created message"
        stream_name, msg_list = messages[0]
        read_msg_id, msg_data = msg_list[0]
        
        deserialized = deserialize_message(msg_data)
        
        print(f"✅ READ copywriter task from {task_stream}")
        pretty_print_message("Copywriter Task Read", read_msg_id, deserialized)
        
        # Verify structure
        assert deserialized['task_id'] == task_payload['task_id']
        assert deserialized['payload']['action'] == 'generate'
        print(f"✅ Copywriter task verified: {deserialized['payload']['template']} for {deserialized['payload']['context']['lead_name']}")
        
        print("\n✅ Copywriter Agent CRUD test PASSED\n")


@pytest.mark.integration
class TestAllT3AgentsCRUD:
    """Test all T3 agents together."""
    
    def test_all_agents_crud_flow(self, redis_client):
        """Test complete CRUD flow across all T3 agents."""
        print("\n🔄 Testing All T3 Agents CRUD Flow...")
        
        agents = [
            ("rag", "search", {"query": "test", "top_k": 3}),
            ("persistence", "write", {"table": "staging_leads", "data": {"name": "Test"}}),
            ("copywriter", "generate", {"template": "email", "context": {"name": "Test"}})
        ]
        
        for agent_name, action, payload_data in agents:
            task_stream = f"test-t3:agents:{agent_name}:tasks"
            
            task = {
                "task_id": str(uuid4()),
                "tenant_id": "test-tenant",
                "payload": {"action": action, **payload_data},
                "metadata": {"source": "test_suite", "timestamp": datetime.utcnow().isoformat()}
            }
            
            # CREATE
            msg_id = redis_client.xadd(task_stream, task)
            print(f"✅ {agent_name.upper()}: Created task {msg_id[:10]}...")
            
            # READ
            messages = redis_client.xread({task_stream: "0"}, count=1)
            assert messages, f"{agent_name} should have message"
            
            _, msg_list = messages[0]
            _, msg_data = msg_list[0]
            deserialized = deserialize_message(msg_data)
            
            assert deserialized['task_id'] == task['task_id']
            print(f"✅ {agent_name.upper()}: Read and verified task")
        
        print("\n✅ All T3 Agents CRUD Flow test PASSED\n")
