"""Unit tests for `core.envelope.typed_envelope`.

This repo uses the Pydantic-based `Envelope` + `Metadata` models.
"""

import pytest

from core.envelope.typed_envelope import Envelope, Metadata, Priority, Status, from_redis_message, task, to_redis_fields


@pytest.mark.unit
class TestTypedEnvelope:
    """Test Envelope schema."""
    
    def test_creation_with_minimal_fields(self):
        envelope = Envelope(
            metadata=Metadata(task_id="test-123", source="unit-test"),
            payload={"query": "test"},
            status=Status.PENDING,
        )

        assert envelope.metadata.task_id == "test-123"
        assert envelope.metadata.source == "unit-test"
        assert envelope.status == Status.PENDING
    
    def test_creation_with_all_fields(self):
        envelope = task(
            source="unit-test",
            task_id="test-123",
            payload={"template": "test"},
            destination="copywriter:tasks",
            priority=Priority.HIGH,
            tenant_id="tenant-1",
            user_id="user-1",
            tags={"variant": "A"},
        )

        assert envelope.metadata.task_id == "test-123"
        assert envelope.metadata.priority == Priority.HIGH
        assert envelope.metadata.tenant_id == "tenant-1"
        assert envelope.metadata.tags["variant"] == "A"
    
    def test_to_dict_serialization(self):
        envelope = task(source="unit-test", task_id="test-123", payload={"query": "test"})
        fields = to_redis_fields(envelope)
        assert isinstance(fields, dict)
        assert "data" in fields
    
    def test_from_dict_deserialization(self):
        original = task(source="unit-test", task_id="test-123", payload={"action": "write"})
        restored = from_redis_message(to_redis_fields(original))
        assert restored.metadata.task_id == "test-123"
        assert restored.payload["action"] == "write"
    
    def test_status_enum_values(self):
        statuses = [Status.PENDING, Status.SUCCESS, Status.ERROR, Status.RETRY, Status.DLQ]
        for status in statuses:
            env = Envelope(metadata=Metadata(task_id="t", source="unit-test"), payload={}, status=status)
            assert env.status == status


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
