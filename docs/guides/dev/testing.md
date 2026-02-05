# Writing Tests

This guide covers testing patterns for the Agentic System.

## Test Structure

```
tests/
├── unit/                    # Isolated component tests
│   ├── test_rag_agent.py
│   ├── test_persistence.py
│   └── test_envelope.py
├── integration/             # Service integration tests
│   ├── test_redis_streams.py
│   ├── test_supabase.py
│   └── test_e2e_flow.py
└── conftest.py              # Shared fixtures
```

## Running Tests

### All Tests

```powershell
& ".venv/Scripts/python.exe" -m pytest -v
```

### Specific Category

```powershell
# Unit tests only
& ".venv/Scripts/python.exe" -m pytest tests/unit/ -v

# Integration tests
& ".venv/Scripts/python.exe" -m pytest tests/integration/ -v
```

### Single Test

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/unit/test_rag_agent.py::test_get_lead_context -v
```

## Unit Testing Agents

### Testing Process Task

```python
import pytest
from tiers.tier_3.rag_agent.rag_agent_harness import RAGAgentHarness

def test_process_task_success():
    harness = RAGAgentHarness(tenant_id="test")

    task = {
        "task_id": "test-001",
        "tenant_id": "test",
        "payload": {
            "action": "get_lead_context",
            "lead_id": "lead-123"
        },
        "metadata": {}
    }

    # Mock the database
    harness.db = MockSupabaseAdapter()
    harness.db.read.return_value = {"id": "lead-123", "name": "Test"}

    result = harness.process_task(task)

    assert result["status"] == "success"
    assert "lead" in result["result"]
```

### Testing Error Handling

```python
def test_process_task_not_found():
    harness = RAGAgentHarness(tenant_id="test")
    harness.db = MockSupabaseAdapter()
    harness.db.read.return_value = None

    result = harness.process_task({
        "task_id": "test-001",
        "tenant_id": "test",
        "payload": {"action": "get_lead_context", "lead_id": "bad-id"},
        "metadata": {}
    })

    assert result["status"] == "error"
    assert result["error"]["code"] == "LEAD_NOT_FOUND"
```

## Mocking

### Mock Supabase Adapter

```python
from unittest.mock import MagicMock

def create_mock_adapter():
    mock = MagicMock()
    mock.read.return_value = {"id": "123", "name": "Test Lead"}
    mock.query.return_value = [{"id": "1"}, {"id": "2"}]
    mock.write.return_value = {"id": "new-123"}
    return mock
```

### Mock Redis Client

```python
from unittest.mock import MagicMock

def create_mock_redis():
    mock = MagicMock()
    mock.xadd.return_value = "1234567890-0"
    mock.xread.return_value = [
        ("stream", [("msg-id", {"data": '{"status": "success"}'})])
    ]
    return mock
```

## Integration Tests

### Redis Stream Test

```python
import pytest
from services.redis.client import get_redis_client

@pytest.fixture
def redis():
    client = get_redis_client()
    yield client
    # Cleanup
    client.delete("test:agents:test:tasks")
    client.delete("test:agents:test:results")

def test_publish_and_read(redis):
    # Publish
    msg_id = redis.xadd("test:agents:test:tasks", {"data": "test"})
    assert msg_id is not None

    # Read
    result = redis.xread({"test:agents:test:tasks": "0"}, count=1)
    assert len(result) == 1
```

### Supabase Test

```python
import pytest
from services.persistence.supabase_adapter import SupabaseAdapter

@pytest.fixture
def adapter():
    return SupabaseAdapter(role="agent_writer")

def test_crud_operations(adapter):
    # Create
    lead = adapter.write("staging_leads", {
        "email": "test@example.com",
        "name": "Test Lead"
    })
    assert "id" in lead

    # Read
    fetched = adapter.read("staging_leads", lead["id"])
    assert fetched["email"] == "test@example.com"

    # Update
    updated = adapter.update("staging_leads", lead["id"], {"name": "Updated"})
    assert updated is not None

    # Delete
    adapter.delete("staging_leads", lead["id"])
```

## E2E Flow Test

```python
def test_full_rag_flow(redis, adapter):
    """End-to-end RAG agent flow."""
    import json
    import uuid
    import time

    # Create test data
    lead = adapter.write("leads", {...})

    # Publish task
    task = {
        "task_id": str(uuid.uuid4()),
        "tenant_id": "test",
        "payload": {"action": "get_lead_context", "lead_id": lead["id"]},
        "metadata": {}
    }
    redis.xadd("test:agents:rag:tasks", {"data": json.dumps(task)})

    # Wait for result (with running consumer)
    time.sleep(2)

    # Check result
    results = redis.xread({"test:agents:rag:results": "0"}, count=10)
    assert len(results) > 0

    result = json.loads(results[0][1][0][1]["data"])
    assert result["task_id"] == task["task_id"]
    assert result["status"] == "success"
```

## Qualification & Promotion E2E

To validate the staging → qualification → promotion pipeline end-to-end:

```powershell
& ".venv/Scripts/python.exe" scripts/testing/test_qualify_lead_promotion_e2e.py
```

## Fixtures

### conftest.py

```python
import pytest
import os

@pytest.fixture(scope="session")
def test_tenant():
    return "test-tenant"

@pytest.fixture
def mock_envelope():
    return {
        "task_id": "test-001",
        "tenant_id": "test",
        "payload": {},
        "metadata": {"source": "test"}
    }

@pytest.fixture(autouse=True)
def set_test_env():
    os.environ["TENANT_ID"] = "test"
    os.environ["LOG_LEVEL"] = "WARNING"
    yield
    # Cleanup if needed
```

## Best Practices

1. **Isolate tests** — Each test should be independent
2. **Mock external services** — Don't hit real APIs in unit tests
3. **Use fixtures** — Share setup code via pytest fixtures
4. **Clean up** — Remove test data after integration tests
5. **Test error paths** — Not just happy paths
6. **Run CI** — Tests should pass in CI before merge

## Related

- [Troubleshooting](../ops/troubleshooting.md)
- [CI/CD Guide](../deploy/ci-cd.md)
