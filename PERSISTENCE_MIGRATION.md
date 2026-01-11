# Persistence Layer Migration Guide

## Overview
This document outlines the migration from the legacy `DBWriteAgent` to the new, more feature-complete `PersistenceAgent`. This migration brings several benefits:

- **Unified API**: Access both read and write operations from a single agent
- **Better security**: Table allowlisting to restrict database access
- **Richer query capabilities**: Enhanced read methods for single records and filtered queries
- **Cleaner architecture**: Better separation of adapter, service, and agent layers

## Before vs After

### Before (DBWriteAgent):

```python
from agent.operational_agents.db_write_agent.db_write_agent import create_supabase_agent

# Creation requires explicit URL and key
db_agent = create_supabase_agent(
    url="https://example.supabase.co", 
    key="your-service-key"
)

# Only write operations
result = db_agent.write("leads", {"email": "test@example.com"})
```

### After (PersistenceAgent):

```python
from agent.operational_agents.persistence_agent.persistence_agent import create_persistence_agent

# Creation simplified, pulls from environment
persistence = create_persistence_agent(
    kind="supabase",
    allowed_tables=["leads", "conversations"]  # Security: restrict tables
)

# Write operations still available
result = persistence.write("leads", {"email": "test@example.com"})

# NEW: Read operations
lead = persistence.read("leads", "test@example.com", id_column="email")
leads = persistence.query("leads", {"status": "active"}, limit=10)
```

## Step-by-Step Migration Guide

### 1. Import Changes

Replace:
```python
from agent.operational_agents.db_write_agent.db_write_agent import (
    create_supabase_agent, create_in_memory_agent
)
```

With:
```python
from agent.operational_agents.persistence_agent.persistence_agent import create_persistence_agent
```

### 2. Agent Creation

Replace:
```python
db_agent = create_supabase_agent(url, key)
```

With:
```python
# Default gets URL/key from environment
persistence = create_persistence_agent(
    kind="supabase",
    allowed_tables=["table1", "table2"]  # Optional restriction
)
```

For in-memory testing:
```python
# Replace
test_agent = create_in_memory_agent()

# With 
test_agent = create_persistence_agent(kind="memory")
```

### 3. Method Calls

Most method calls should work without changes, as the parameter names match:
- `write(table, record)`
- `batch_write(table, records)`
- `upsert(table, record, on_conflict=None)`

### 4. Adding Read Operations

Take advantage of new capabilities:
```python
# Get by ID
record = persistence.read("leads", lead_id)

# Get by email (alternate ID)
record = persistence.read("leads", email_address, id_column="email")

# Query with filters
active_leads = persistence.query("leads", {"status": "active"})

# Query with limit
recent_leads = persistence.query("leads", limit=10)
```

### 5. Testing Your Migration

After migrating, ensure:
1. All write operations still succeed
2. Any new read operations return expected data
3. Table allowlisting properly restricts access where needed

## Timeline

The `DBWriteAgent` is now deprecated and will be removed in a future release. Please update your code as soon as possible.

## Need Help?

If you encounter issues during migration:
1. Run the `scripts/migrate_db_write.py` utility to find all DBWriteAgent usage
2. Check for edge cases in your usage patterns
3. Review the source code for both agents if needed

The PersistenceAgent is designed to be a drop-in replacement with additional capabilities, so migration should be straightforward.