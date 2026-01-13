# Persistence Service

The Persistence Service provides database access via Supabase with role-based authentication.

## Overview

| Component    | Description                                  |
| ------------ | -------------------------------------------- |
| **Location** | `services/persistence/`                      |
| **Purpose**  | Supabase client wrapper with role management |
| **Used By**  | RAGAgent (reader), PersistenceAgent (writer) |

## SupabaseAdapter

Primary interface for database operations:

```python
from services.persistence.supabase_adapter import SupabaseAdapter

# Reader role (RAGAgent)
reader = SupabaseAdapter(role="agent_reader")

# Writer role (PersistenceAgent)
writer = SupabaseAdapter(role="agent_writer")
```

## Operations

### Read

```python
# Get by ID
lead = adapter.read("leads", "uuid-here")
# Returns: {"id": "...", "name": "...", ...}
```

### Query

```python
# Filter query
leads = adapter.query("leads", {"status": "qualified"}, limit=10)
# Returns: [{"id": "...", ...}, ...]

# Multiple filters
leads = adapter.query("leads", {
    "status": "qualified",
    "score": {"gte": 80}
})
```

### Write

```python
# Insert new record
result = adapter.write("leads", {
    "name": "John Doe",
    "email": "john@example.com",
    "client_id": "uuid-client",
    "campaign_id": "uuid-campaign"
})
# Returns: {"id": "uuid-new", "created_at": "..."}
```

### Update

```python
# Update by ID
result = adapter.update("leads", "uuid-lead", {
    "status": "contacted",
    "score": 85
})
# Returns: {"id": "...", "updated_at": "..."}
```

### Delete

```python
# Delete by ID
result = adapter.delete("leads", "uuid-lead")
# Returns: {"deleted": True}
```

### Batch Write

```python
# Insert multiple records
results = adapter.batch_write("messages", [
    {"conversation_id": "uuid", "content": "Hello", "metadata": {}},
    {"conversation_id": "uuid", "content": "World", "metadata": {}}
])
# Returns: {"created_count": 2, "ids": ["uuid-1", "uuid-2"]}
```

## API Reference

### Constructor

```python
class SupabaseAdapter:
    def __init__(
        self,
        role: str = "agent_reader",  # "agent_reader" or "agent_writer"
        url: str = None,             # From SUPABASE_URL if None
        anon_key: str = None,        # From SUPABASE_ANON_KEY if None
        jwt_secret: str = None       # From SUPABASE_JWT_SECRET if None
    ):
```

### Methods

| Method        | Signature                                | Description        |
| ------------- | ---------------------------------------- | ------------------ |
| `read`        | `(table, id) → dict`                     | Get single record  |
| `query`       | `(table, filters, limit, offset) → list` | Query with filters |
| `write`       | `(table, data) → dict`                   | Insert record      |
| `update`      | `(table, id, data) → dict`               | Update record      |
| `delete`      | `(table, id) → dict`                     | Delete record      |
| `batch_write` | `(table, records) → dict`                | Insert multiple    |

## Role Management

### agent_reader

- SELECT only
- Used by RAGAgent
- Cannot modify data

### agent_writer

- Full CRUD
- Used by PersistenceAgent
- Can INSERT, UPDATE, DELETE

### Role Enforcement

```python
class SupabaseAdapter:
    def _create_role_jwt(self) -> str:
        """Create JWT with role claim."""
        payload = {
            "role": self.role,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    @property
    def client(self):
        if self._client is None:
            self._client = create_client(self.url, self.anon_key)
            self._client.postgrest.auth(self._create_role_jwt())
        return self._client
```

## Error Handling

```python
from services.persistence.exceptions import (
    RecordNotFoundError,
    ForeignKeyError,
    DuplicateKeyError,
    RLSError
)

try:
    adapter.write("leads", data)
except ForeignKeyError as e:
    # Invalid client_id or campaign_id
    logger.error(f"FK violation: {e}")
except DuplicateKeyError as e:
    # Unique constraint (e.g., duplicate email)
    logger.warning(f"Duplicate: {e}")
except RLSError as e:
    # Row-level security denied
    logger.error(f"RLS denied: {e}")
```

## File Structure

```
services/persistence/
├── __init__.py
├── supabase_adapter.py   # Main adapter
├── exceptions.py         # Custom exceptions
└── README.md
```

## Configuration

| Variable              | Required | Description        |
| --------------------- | -------- | ------------------ |
| `SUPABASE_URL`        | ✅       | Project URL        |
| `SUPABASE_ANON_KEY`   | ✅       | Public API key     |
| `SUPABASE_JWT_SECRET` | ✅       | JWT signing secret |

## Usage in Agents

### RAGAgent (Reader)

```python
class RAGAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(tenant_id, "rag")
        self.db = SupabaseAdapter(role="agent_reader")

    def get_lead_context(self, lead_id: str) -> dict:
        lead = self.db.read("leads", lead_id)
        conversations = self.db.query("conversations", {"lead_id": lead_id})
        return {"lead": lead, "conversations": conversations}
```

### PersistenceAgent (Writer)

```python
class PersistenceAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(tenant_id, "persistence")
        self.db = SupabaseAdapter(role="agent_writer")

    def create_lead(self, data: dict) -> dict:
        return self.db.write("leads", data)
```

## Testing

### Mock Adapter

```python
from unittest.mock import MagicMock

mock_db = MagicMock(spec=SupabaseAdapter)
mock_db.read.return_value = {"id": "test", "name": "Test Lead"}

agent.db = mock_db
```

## Related

- [Database Schema](../../reference/database/schema.md)
- [RLS Policies](../../reference/database/rls.md)
- [RAG Agent](../tier-3/rag.md)
- [Persistence Agent](../tier-3/persistence.md)
