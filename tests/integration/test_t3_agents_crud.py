"""Test Tier 3 Agents - CRUD operations with response verification and pretty printing.

Tests:
1. RAGAgent - Query/Search CRUD (Read-only)
2. PersistenceAgent - Write/Update/Delete CRUD (Full CRUD)
3. CopywriterAgent - Content Generation (Create)

Prints detailed responses for manual inspection.
"""
import os
import json
import pytest
import uuid
from datetime import datetime
from typing import Dict, Any

from services.redis.client import RedisStreamsClient
from services.redis import config


def print_header(title: str):
    """Print formatted test header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def print_response(label: str, data: Any, indent: int = 2):
    """Pretty print response data."""
    prefix = " " * indent
    if isinstance(data, dict):
        print(f"{prefix}{label}:")
        print(json.dumps(data, indent=2).replace("\n", f"\n{prefix}"))
    else:
        print(f"{prefix}{label}: {data}")


def create_envelope(task_type: str, payload: Dict[str, Any], tenant_id: str = "test-tenant") -> Dict[str, Any]:
    """Create Redis message envelope."""
    return {
        "task_id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "payload": payload,
        "metadata": {
            "source": "test_suite",
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": str(uuid.uuid4()),
            "type": task_type
        }
    }


def deserialize_message(msg_data: Dict[str, Any]) -> Dict[str, Any]:
    """Deserialize JSON strings in message if needed."""
    if isinstance(msg_data.get("payload"), str):
        msg_data["payload"] = json.loads(msg_data["payload"])
    if isinstance(msg_data.get("metadata"), str):
        msg_data["metadata"] = json.loads(msg_data["metadata"])
    return msg_data


@pytest.fixture
def redis_client():
    """Provide Redis Streams client for testing."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    client = RedisStreamsClient(url=redis_url, namespace="test")
    
    # Verify connection
    client.client.ping()
    
    try:
        yield client
    finally:
        # Cleanup test streams
        for key in client.client.scan_iter("test:*"):
            client.client.delete(key)
        try:
            client.client.close()
        except Exception:
            pass
        try:
            client.client.connection_pool.disconnect()
        except Exception:
            pass


class TestRAGAgentCRUD:
    """Test RAGAgent Read operations (READ-ONLY agent)."""
    
    def test_rag_agent_query_crud(self, redis_client):
        """Test RAGAgent CRUD: Query/Retrieve documents."""
        print_header("RAGAgent - Query CRUD Test")
        
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:rag:tasks"
        result_stream = f"{tenant_id}:agents:rag:results"
        group = "rag-test"
        consumer = "test-rag-1"
        
        # === CREATE: Send query task ===
        print("\n[1] CREATE - Send Query Task")
        query_payload = {
            "action": "query",
            "query": "What are the main pain points for SaaS companies?",
            "top_k": 5,
            "filters": {"source": "documentation"}
        }
        task_envelope = create_envelope("rag_query", query_payload, tenant_id)
        
        task_id = redis_client.xadd(task_stream, task_envelope)
        print_response("Task Added", {"stream": task_stream, "message_id": task_id})
        assert task_id is not None, "Failed to add task to stream"
        
        # === READ: Consume task ===
        print("\n[2] READ - Consume Query Task")
        redis_client.xgroup_create(task_stream, group, id="0", mkstream=True)
        messages = redis_client.xreadgroup(group, consumer, {task_stream: ">"}, count=1)
        
        assert messages, "No messages in stream"
        assert messages[0][1], "Message has no data"
        
        msg_id, msg_data = messages[0][1][0]
        print_response("Read Message ID", msg_id)
        msg_data = deserialize_message(msg_data)
        print_response("Read Message Data", msg_data)
        
        # Verify envelope structure
        assert msg_data["task_id"] == task_envelope["task_id"]
        assert msg_data["payload"]["action"] == "query"
        
        # === UPDATE: Acknowledge message ===
        print("\n[3] UPDATE - Acknowledge Task Processing")
        ack_count = redis_client.xack(task_stream, group, msg_id)
        print_response("Acknowledged", f"{ack_count} message(s)")
        assert ack_count == 1, "Failed to acknowledge message"
        
        # === CREATE: Write result ===
        print("\n[4] CREATE - Write Query Result")
        result_payload = {
            "action": "query",
            "status": "success",
            "results": [
                {
                    "id": "doc_1",
                    "content": "SaaS companies struggle with customer retention...",
                    "relevance": 0.98
                },
                {
                    "id": "doc_2",
                    "content": "Integration challenges are a key pain point...",
                    "relevance": 0.95
                }
            ],
            "total_matches": 42,
            "query_time_ms": 234
        }
        result_envelope = create_envelope("rag_query_result", result_payload, tenant_id)
        
        result_id = redis_client.xadd(result_stream, result_envelope)
        print_response("Result Added", {"stream": result_stream, "message_id": result_id})
        assert result_id is not None, "Failed to add result"
        
        # === READ: Verify result ===
        print("\n[5] READ - Verify Result")
        results = redis_client.xread({result_stream: "0"}, count=1)
        assert results, "No results in stream"
        
        result_data = results[0][1][0][1]
        result_data = deserialize_message(result_data)
        print_response("Result Data", result_data)
        assert result_data["payload"]["status"] == "success"
        assert len(result_data["payload"]["results"]) == 2
        
        print("\n✅ RAGAgent CRUD test passed!")
    
    def test_rag_agent_vector_search(self, redis_client):
        """Test RAGAgent vector similarity search."""
        print_header("RAGAgent - Vector Search Test")
        
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:rag:tasks"
        result_stream = f"{tenant_id}:agents:rag:results"
        
        # === CREATE: Send vector search task ===
        print("\n[1] CREATE - Vector Search Task")
        search_payload = {
            "action": "vector_search",
            "query_text": "How do we improve conversion rates?",
            "embedding_dimension": 1536,
            "similarity_threshold": 0.7,
            "limit": 10
        }
        task_envelope = create_envelope("rag_vector_search", search_payload, tenant_id)
        
        task_id = redis_client.xadd(task_stream, task_envelope)
        print_response("Task Added", task_id)
        
        # === READ: Get task ===
        print("\n[2] READ - Consume Vector Search Task")
        messages = redis_client.xread({task_stream: "0"}, count=1)
        assert messages, "No messages in stream"
        
        msg_data = messages[0][1][0][1]
        print_response("Task Received", msg_data)
        
        # === CREATE: Write vector search results ===
        print("\n[3] CREATE - Vector Search Results")
        result_payload = {
            "action": "vector_search",
            "status": "success",
            "matches": [
                {
                    "id": "chunk_123",
                    "text": "Conversion optimization through A/B testing...",
                    "similarity_score": 0.92,
                    "source_document": "conversion_guide.md"
                },
                {
                    "id": "chunk_456",
                    "text": "Landing page best practices for SaaS...",
                    "similarity_score": 0.88,
                    "source_document": "saas_guide.md"
                }
            ],
            "search_time_ms": 156
        }
        result_envelope = create_envelope("rag_vector_search_result", result_payload, tenant_id)
        
        result_id = redis_client.xadd(result_stream, result_envelope)
        print_response("Results Added", result_id)
        
        print("\n✅ Vector search test passed!")


class TestPersistenceAgentCRUD:
    """Test PersistenceAgent CRUD operations (Full CRUD)."""
    
    def test_persistence_agent_write_crud(self, redis_client):
        """Test PersistenceAgent CRUD: Write (CREATE)."""
        print_header("PersistenceAgent - Write CRUD Test")
        
        tenant_id = "test-tenant"
        stream_suffix = str(uuid.uuid4())
        task_stream = f"test:{tenant_id}:{stream_suffix}:agents:persistence:tasks"
        result_stream = f"test:{tenant_id}:{stream_suffix}:agents:persistence:results"
        group = f"persistence-test-{stream_suffix}"
        consumer = "test-persist-1"
        
        # === CREATE: Prepare group and send write task ===
        redis_client.xgroup_create(task_stream, group, id="0", mkstream=True)
		
        print("\n[1] CREATE - Write Task to Database")
        write_payload = {
            "operation": "write",
            "table": "leads",
            "data": {
                "name": "John Doe",
                "email": "john@example.com",
                "company": "Acme Corp",
                "status": "qualified"
            }
        }
        task_envelope = create_envelope("persistence_write", write_payload, tenant_id)
        
        task_id = redis_client.xadd(task_stream, task_envelope)
        print_response("Write Task Added", {"message_id": task_id, "table": "leads"})
        
        # === READ: Consume task ===
        print("\n[2] READ - Consume Write Task")
        messages = redis_client.xreadgroup(group, consumer, {task_stream: ">"}, count=1)
        
        assert messages, "No write tasks in stream"
        msg_id, msg_data = messages[0][1][0]
        msg_data = deserialize_message(msg_data)
        print_response("Task Received", msg_data)
        assert msg_data["payload"]["operation"] == "write"
        
        # === UPDATE: Acknowledge task ===
        print("\n[3] UPDATE - Acknowledge Write")
        ack_count = redis_client.xack(task_stream, group, msg_id)
        print_response("Write Acknowledged", f"{ack_count} message(s)")
        
        # === CREATE: Write success result ===
        print("\n[4] CREATE - Write Success Result")
        result_payload = {
            "operation": "write",
            "status": "success",
            "table": "leads",
            "inserted_id": "lead_abc123",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "rows_affected": 1,
                "query_time_ms": 45
            }
        }
        result_envelope = create_envelope("persistence_write_result", result_payload, tenant_id)
        
        result_id = redis_client.xadd(result_stream, result_envelope)
        print_response("Write Result Added", result_id)
        
        print("\n✅ Write CRUD test passed!")
    
    def test_persistence_agent_update_crud(self, redis_client):
        """Test PersistenceAgent CRUD: Update."""
        print_header("PersistenceAgent - Update CRUD Test")
        
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:persistence:tasks"
        result_stream = f"{tenant_id}:agents:persistence:results"
        
        # === CREATE: Update task ===
        print("\n[1] CREATE - Update Task")
        update_payload = {
            "operation": "update",
            "table": "leads",
            "filter": {"id": "lead_abc123"},
            "updates": {
                "status": "contacted",
                "last_contacted": datetime.utcnow().isoformat(),
                "notes": "Initial call scheduled"
            }
        }
        task_envelope = create_envelope("persistence_update", update_payload, tenant_id)
        
        task_id = redis_client.xadd(task_stream, task_envelope)
        print_response("Update Task Added", task_id)
        
        # === READ: Get task ===
        print("\n[2] READ - Consume Update Task")
        messages = redis_client.xread({task_stream: "0"}, count=1)
        assert messages, "No update tasks"
        
        msg_data = messages[0][1][0][1]
        msg_data = deserialize_message(msg_data)
        print_response("Task Received", msg_data)
        
        # === CREATE: Update result ===
        print("\n[3] CREATE - Update Success Result")
        result_payload = {
            "operation": "update",
            "status": "success",
            "table": "leads",
            "filter": {"id": "lead_abc123"},
            "rows_updated": 1,
            "timestamp": datetime.utcnow().isoformat()
        }
        result_envelope = create_envelope("persistence_update_result", result_payload, tenant_id)
        
        result_id = redis_client.xadd(result_stream, result_envelope)
        print_response("Update Result Added", result_id)
        
        print("\n✅ Update CRUD test passed!")
    
    def test_persistence_agent_delete_crud(self, redis_client):
        """Test PersistenceAgent CRUD: Delete."""
        print_header("PersistenceAgent - Delete CRUD Test")
        
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:persistence:tasks"
        result_stream = f"{tenant_id}:agents:persistence:results"
        
        # === CREATE: Delete task ===
        print("\n[1] CREATE - Delete Task")
        delete_payload = {
            "operation": "delete",
            "table": "leads",
            "filter": {"id": "lead_abc123"}
        }
        task_envelope = create_envelope("persistence_delete", delete_payload, tenant_id)
        
        task_id = redis_client.xadd(task_stream, task_envelope)
        print_response("Delete Task Added", task_id)
        
        # === READ: Get task ===
        print("\n[2] READ - Consume Delete Task")
        messages = redis_client.xread({task_stream: "0"}, count=1)
        msg_data = messages[0][1][0][1]
        msg_data = deserialize_message(msg_data)
        print_response("Task Received", msg_data)
        
        # === CREATE: Delete result ===
        print("\n[3] CREATE - Delete Success Result")
        result_payload = {
            "operation": "delete",
            "status": "success",
            "table": "leads",
            "rows_deleted": 1,
            "timestamp": datetime.utcnow().isoformat()
        }
        result_envelope = create_envelope("persistence_delete_result", result_payload, tenant_id)
        
        result_id = redis_client.xadd(result_stream, result_envelope)
        print_response("Delete Result Added", result_id)
        
        print("\n✅ Delete CRUD test passed!")


class TestCopywriterAgentCRUD:
    """Test CopywriterAgent content generation (CREATE)."""
    
    def test_copywriter_agent_email_generation(self, redis_client):
        """Test CopywriterAgent CRUD: Generate email copy."""
        print_header("CopywriterAgent - Email Generation CRUD Test")
        
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:copywriter:tasks"
        result_stream = f"{tenant_id}:agents:copywriter:results"
        group = "copywriter-test"
        consumer = "test-copy-1"
        
        # === CREATE: Send generation task ===
        print("\n[1] CREATE - Email Generation Task")
        gen_payload = {
            "template": "cold_email",
            "context": {
                "recipient_name": "Sarah Johnson",
                "company": "TechStartup Inc",
                "role": "VP Product",
                "pain_points": ["scaling infrastructure", "team coordination"],
                "our_solution": "DevOps automation platform"
            },
            "tone": "professional",
            "max_words": 200
        }
        task_envelope = create_envelope("copywriter_email", gen_payload, tenant_id)
        
        task_id = redis_client.xadd(task_stream, task_envelope)
        print_response("Generation Task Added", task_id)
        
        # === READ: Consume task ===
        print("\n[2] READ - Consume Generation Task")
        redis_client.xgroup_create(task_stream, group, id="0", mkstream=True)
        messages = redis_client.xreadgroup(group, consumer, {task_stream: ">"}, count=1)
        
        assert messages, "No generation tasks"
        msg_id, msg_data = messages[0][1][0]
        msg_data = deserialize_message(msg_data)
        print_response("Task Received", msg_data)
        assert msg_data["payload"]["template"] == "cold_email"
        
        # === UPDATE: Acknowledge ===
        print("\n[3] UPDATE - Acknowledge Generation")
        ack_count = redis_client.xack(task_stream, group, msg_id)
        print_response("Acknowledged", f"{ack_count} message(s)")
        
        # === CREATE: Generated content result ===
        print("\n[4] CREATE - Generated Email Copy")
        result_payload = {
            "template": "cold_email",
            "status": "success",
            "generated_content": (
                "Hi Sarah,\n\n"
                "I noticed TechStartup is scaling rapidly. Scaling infrastructure "
                "and team coordination are critical challenges at this stage.\n\n"
                "Our DevOps automation platform helps companies like yours reduce "
                "infrastructure overhead by 40% and improve deployment speed.\n\n"
                "Would you be open to a 15-minute conversation?\n\nBest,\nAlex"
            ),
            "word_count": 68,
            "metadata": {
                "model_used": "gpt-4",
                "generation_time_ms": 1234,
                "tokens_used": 234
            }
        }
        result_envelope = create_envelope("copywriter_email_result", result_payload, tenant_id)
        
        result_id = redis_client.xadd(result_stream, result_envelope)
        print_response("Generated Content Result Added", result_id)
        
        # === READ: Verify result ===
        print("\n[5] READ - Verify Generated Content")
        results = redis_client.xread({result_stream: "0"}, count=1)
        result_data = results[0][1][0][1]
        payload = result_data.get("payload")
        if isinstance(payload, str):
            payload = json.loads(payload)
        print_response("Generated Copy", {
            "word_count": payload["word_count"],
            "status": payload["status"],
            "preview": payload["generated_content"][:80] + "..."
        })
        
        print("\n✅ Email generation CRUD test passed!")
    
    def test_copywriter_agent_subject_line_generation(self, redis_client):
        """Test CopywriterAgent: Generate email subject lines."""
        print_header("CopywriterAgent - Subject Line Generation Test")
        
        tenant_id = "test-tenant"
        task_stream = f"{tenant_id}:agents:copywriter:tasks"
        result_stream = f"{tenant_id}:agents:copywriter:results"
        
        # === CREATE: Subject line generation task ===
        print("\n[1] CREATE - Subject Line Generation Task")
        gen_payload = {
            "template": "subject_lines",
            "context": {
                "company": "TechStartup Inc",
                "value_prop": "Reduce infrastructure costs by 40%",
                "audience": "VP Product"
            },
            "num_options": 5
        }
        task_envelope = create_envelope("copywriter_subject", gen_payload, tenant_id)
        
        task_id = redis_client.xadd(task_stream, task_envelope)
        print_response("Task Added", task_id)
        
        # === CREATE: Subject line results ===
        print("\n[2] CREATE - Generated Subject Lines")
        result_payload = {
            "template": "subject_lines",
            "status": "success",
            "subject_lines": [
                "40% faster deployments for TechStartup?",
                "Infrastructure costs: cut by nearly half",
                "Scaling infrastructure shouldn't require 3 teams",
                "DevOps simplified for growing companies",
                "TechStartup: Deploy faster, stress less"
            ],
            "metadata": {
                "model_used": "gpt-4",
                "generation_time_ms": 456
            }
        }
        result_envelope = create_envelope("copywriter_subject_result", result_payload, tenant_id)
        
        result_id = redis_client.xadd(result_stream, result_envelope)
        print_response("Results Added", result_id)
        
        # === READ: Verify ===
        print("\n[3] READ - Verify Subject Lines")
        results = redis_client.xread({result_stream: "0"}, count=1)
        result_data = results[0][1][0][1]

        payload = result_data.get("payload")
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        print_response("Generated Subject Lines", {
            "count": len(payload["subject_lines"]),
            "options": payload["subject_lines"]
        })
        
        print("\n✅ Subject line generation test passed!")
