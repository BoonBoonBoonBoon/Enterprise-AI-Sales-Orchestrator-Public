"""Tests for envelope parsing in workers.

Validates that workers correctly parse various payload structures from
Redis messages using from_redis_message() and to_redis_fields().
"""
import pytest
from core.envelope.typed_envelope import (
    task, result, error, to_redis_fields, from_redis_message, Priority, Status
)


class TestEnvelopeRoundtrip:
    """Test envelope serialization/deserialization roundtrip."""
    
    def test_task_envelope_roundtrip(self):
        """Test task envelope survives Redis serialization roundtrip."""
        original = task(
            task_id="test_123",
            payload={"query": {"table": "leads", "filters": {"email": "test@example.com"}}},
            source="test",
            destination="rag:tasks",
            priority=Priority.HIGH
        )
        
        fields = to_redis_fields(original)
        restored = from_redis_message(fields)
        
        assert restored.metadata.task_id == original.metadata.task_id
        assert restored.metadata.correlation_id == original.metadata.correlation_id
        assert restored.payload == original.payload
        assert restored.status == original.status
        assert restored.metadata.priority == original.metadata.priority
    
    def test_result_envelope_roundtrip(self):
        """Test result envelope survives Redis serialization roundtrip."""
        original_task = task(
            task_id="task_456",
            payload={"data": "test"},
            source="worker",
            destination="test:stream"
        )
        
        original_result = result(
            original=original_task,
            payload={"records": [{"id": "1", "email": "test@example.com"}], "count": 1},
            source="rag_worker"
        )
        
        fields = to_redis_fields(original_result)
        restored = from_redis_message(fields)
        
        assert restored.metadata.task_id == original_result.metadata.task_id
        assert restored.metadata.correlation_id == original_result.metadata.correlation_id
        assert restored.payload == original_result.payload
        assert restored.status == Status.SUCCESS
    
    def test_error_envelope_roundtrip(self):
        """Test error envelope survives Redis serialization roundtrip."""
        original_task = task(
            task_id="task_789",
            payload={"op": "insert"},
            source="orchestrator",
            destination="persist:tasks"
        )
        
        original_error = error(
            original=original_task,
            error_msg="Duplicate key violation",
            source="persist_worker",
            code="23505"
        )
        
        fields = to_redis_fields(original_error)
        restored = from_redis_message(fields)
        
        assert restored.metadata.task_id == original_error.metadata.task_id
        assert restored.metadata.correlation_id == original_error.metadata.correlation_id
        assert restored.error == "Duplicate key violation"
        assert restored.error_code == "23505"
        assert restored.status == Status.ERROR


class TestRAGWorkerPayloads:
    """Test RAG worker payload parsing."""
    
    def test_rag_query_payload(self):
        """Test RAG worker can parse query payload."""
        envelope = task(
            task_id="rag_test",
            payload={
                "query": {
                    "table": "leads",
                    "filters": {"email": "lead@company.com"},
                    "limit": 10,
                    "order_by": "created_at",
                    "descending": True
                }
            },
            source="orchestrator",
            destination="rag:tasks"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        query_spec = parsed.payload.get("query", {})
        assert query_spec["table"] == "leads"
        assert query_spec["filters"]["email"] == "lead@company.com"
        assert query_spec["limit"] == 10
        assert query_spec["order_by"] == "created_at"
        assert query_spec["descending"] is True
    
    def test_rag_result_with_records(self):
        """Test RAG worker result with records."""
        original_task = task(
            task_id="rag_query",
            payload={"query": {"table": "leads"}},
            source="orchestrator",
            destination="rag:tasks"
        )
        
        rag_result = result(
            original=original_task,
            payload={
                "records": [
                    {"id": "1", "email": "test1@example.com", "company_name": "Acme Corp"},
                    {"id": "2", "email": "test2@example.com", "company_name": "Tech Inc"}
                ],
                "count": 2,
                "table": "leads"
            },
            source="rag_worker"
        )
        
        fields = to_redis_fields(rag_result)
        parsed = from_redis_message(fields)
        
        assert parsed.payload["count"] == 2
        assert len(parsed.payload["records"]) == 2
        assert parsed.payload["records"][0]["email"] == "test1@example.com"


class TestPersistenceWorkerPayloads:
    """Test persistence worker payload parsing."""
    
    def test_insert_task_payload(self):
        """Test persistence worker can parse insert payload."""
        envelope = task(
            task_id="persist_insert",
            payload={
                "table": "leads",
                "op": "insert",
                "values": {
                    "email": "new@company.com",
                    "first_name": "John",
                    "company_name": "NewCo"
                },
                "returning": True
            },
            source="orchestrator",
            destination="persist:tasks"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.payload["table"] == "leads"
        assert parsed.payload["op"] == "insert"
        assert parsed.payload["values"]["email"] == "new@company.com"
        assert parsed.payload["returning"] is True
    
    def test_upsert_task_payload(self):
        """Test persistence worker can parse upsert payload."""
        envelope = task(
            task_id="persist_upsert",
            payload={
                "table": "leads",
                "op": "upsert",
                "values": {
                    "email": "existing@company.com",
                    "first_name": "Jane",
                    "company_name": "UpdatedCo"
                },
                "on_conflict": ["email"],
                "returning": True
            },
            source="orchestrator",
            destination="persist:tasks"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.payload["op"] == "upsert"
        assert parsed.payload["on_conflict"] == ["email"]
    
    def test_batch_insert_payload(self):
        """Test persistence worker can parse batch insert payload."""
        envelope = task(
            task_id="persist_batch",
            payload={
                "table": "leads",
                "op": "batch_insert",
                "rows": [
                    {"email": "lead1@example.com", "first_name": "Alice"},
                    {"email": "lead2@example.com", "first_name": "Bob"}
                ],
                "returning": False
            },
            source="bulk_importer",
            destination="persist:tasks"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.payload["op"] == "batch_insert"
        assert len(parsed.payload["rows"]) == 2


class TestCopywriterWorkerPayloads:
    """Test copywriter worker payload parsing."""
    
    def test_copywriter_full_context_payload(self):
        """Test copywriter worker can parse full context payload."""
        envelope = task(
            task_id="copy_gen",
            payload={
                "lead_data": {
                    "id": "lead_123",
                    "email": "prospect@company.com",
                    "first_name": "Sarah",
                    "company_name": "TechCorp",
                    "title": "VP Engineering"
                },
                "campaign_context": {
                    "campaign_name": "Q1 Outreach",
                    "step": 2,
                    "previous_subject": "Introduction to our platform",
                    "days_since_last_contact": 5
                },
                "instructions": {
                    "tone": "professional",
                    "language": "en-US",
                    "max_length": 200,
                    "include_cta": True,
                    "cta": "schedule a demo"
                }
            },
            source="rag_worker",
            destination="copy:tasks",
            campaign_id="campaign_q1_2025"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.payload["lead_data"]["first_name"] == "Sarah"
        assert parsed.payload["campaign_context"]["step"] == 2
        assert parsed.payload["instructions"]["tone"] == "professional"
        assert parsed.metadata.campaign_id == "campaign_q1_2025"
    
    def test_copywriter_minimal_payload(self):
        """Test copywriter worker handles minimal payload."""
        envelope = task(
            task_id="copy_minimal",
            payload={
                "lead_data": {"first_name": "Alex"},
                "campaign_context": {},
                "instructions": {}
            },
            source="test",
            destination="copy:tasks"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        # Should parse without errors
        assert "lead_data" in parsed.payload
        assert "campaign_context" in parsed.payload
        assert "instructions" in parsed.payload


class TestComplexPayloadTypes:
    """Test complex nested payloads."""
    
    def test_nested_dict_payload(self):
        """Test deeply nested dictionary payloads."""
        envelope = task(
            task_id="nested_test",
            payload={
                "level1": {
                    "level2": {
                        "level3": {
                            "data": ["item1", "item2"],
                            "metadata": {"key": "value"}
                        }
                    }
                }
            },
            source="test",
            destination="test:stream"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.payload["level1"]["level2"]["level3"]["data"] == ["item1", "item2"]
        assert parsed.payload["level1"]["level2"]["level3"]["metadata"]["key"] == "value"
    
    def test_list_payload(self):
        """Test payload with lists."""
        envelope = task(
            task_id="list_test",
            payload={
                "items": [1, 2, 3, 4, 5],
                "strings": ["a", "b", "c"],
                "mixed": [1, "two", 3.0, True, None]
            },
            source="test",
            destination="test:stream"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.payload["items"] == [1, 2, 3, 4, 5]
        assert parsed.payload["strings"] == ["a", "b", "c"]
        assert parsed.payload["mixed"] == [1, "two", 3.0, True, None]
    
    def test_empty_payload(self):
        """Test envelope with empty payload."""
        envelope = task(
            task_id="empty_test",
            payload={},
            source="test",
            destination="test:stream"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.payload == {}


class TestMetadataPreservation:
    """Test metadata fields are preserved through serialization."""
    
    def test_correlation_id_preserved(self):
        """Test correlation_id is preserved."""
        envelope = task(
            task_id="meta_test",
            payload={"data": "test"},
            source="test",
            destination="test:stream"
        )
        
        original_corr_id = envelope.metadata.correlation_id
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.metadata.correlation_id == original_corr_id
    
    def test_tenant_and_user_preserved(self):
        """Test tenant_id and user_id are preserved."""
        envelope = task(
            task_id="tenant_test",
            payload={"data": "test"},
            source="test",
            destination="test:stream",
            tenant_id="tenant_abc",
            user_id="user_123"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.metadata.tenant_id == "tenant_abc"
        assert parsed.metadata.user_id == "user_123"
    
    def test_campaign_id_preserved(self):
        """Test campaign_id is preserved."""
        envelope = task(
            task_id="campaign_test",
            payload={"data": "test"},
            source="test",
            destination="test:stream",
            campaign_id="campaign_xyz"
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.metadata.campaign_id == "campaign_xyz"
    
    def test_priority_preserved(self):
        """Test priority is preserved."""
        envelope = task(
            task_id="priority_test",
            payload={"data": "test"},
            source="test",
            destination="test:stream",
            priority=Priority.CRITICAL
        )
        
        fields = to_redis_fields(envelope)
        parsed = from_redis_message(fields)
        
        assert parsed.metadata.priority == Priority.CRITICAL
