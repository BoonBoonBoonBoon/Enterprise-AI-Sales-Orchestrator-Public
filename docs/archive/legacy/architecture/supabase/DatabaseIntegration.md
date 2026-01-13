# Supabase Database Integration

## Overview

The Agentic System uses a **3-layer authentication stack** for secure database access through Supabase. This document covers the authentication architecture, agent permissions, and usage patterns.

---

## 🔐 The 3-Layer Authentication Stack

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: API Gateway                                       │
│  ✓ apikey header = Supabase anon key                       │
│  ✓ Authorization header = Custom JWT signed with JWT_SECRET │
│  ✓ JWT must have role: "anon" to pass gateway              │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: PostgreSQL GRANT Permissions                      │
│  ✓ Tables must have: GRANT ALL ON table TO anon            │
│  ✓ Without this, you get "permission denied for table"     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: Row Level Security (RLS) Policies                 │
│  ✓ Extracts user_role from JWT claims                      │
│  ✓ agent_reader → SELECT only                              │
│  ✓ agent_writer → SELECT, INSERT, UPDATE, DELETE           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Validated Tables

| Table | SELECT | INSERT | UPDATE | DELETE | RLS Enforced |
|-------|--------|--------|--------|--------|--------------|
| **clients** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **staging_leads** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **leads** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **conversations** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **messages** | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 🤖 Agent Permissions

### RAG Agent (`SUPABASE_RAG_JWT`)
- **Role:** `agent_reader`
- **Capabilities:**
  - ✅ SELECT from all tables (read-only access)
  - ❌ INSERT blocked by RLS
  - ❌ UPDATE blocked by RLS
  - ❌ DELETE blocked by RLS
- **Use Case:** Retrieval-Augmented Generation, querying context for LLMs

### Persistence Agent (`SUPABASE_PERSISTENCE_JWT`)
- **Role:** `agent_writer`
- **Capabilities:**
  - ✅ SELECT from all tables
  - ✅ INSERT new records
  - ✅ UPDATE existing records
  - ✅ DELETE records
- **Use Case:** Writing lead data, updating statuses, managing conversations

---

## 🛠️ SupabaseAdapter Usage

The `SupabaseAdapter` class provides a unified interface for database operations:

```python
from services.persistence.adapters.supabase_adapter import SupabaseAdapter

# Initialize with custom JWT + anon key pattern
adapter = SupabaseAdapter(
    url=os.getenv("SUPABASE_URL"),
    key=os.getenv("SUPABASE_PERSISTENCE_JWT"),
    anon_key=os.getenv("SUPABASE_KEY")  # The anon public key
)

# CRUD Operations
adapter.write("leads", {"email": "test@example.com", ...})      # CREATE
adapter.read("leads", "uuid-here")                               # READ by ID
adapter.query("leads", filters={"client_id": "..."}, limit=10)   # READ with filters
adapter.update("leads", "uuid-here", {"status": "contacted"})    # UPDATE
adapter.delete("leads", "uuid-here")                             # DELETE

# Batch operations
adapter.batch_write("staging_leads", [record1, record2, ...])

# Advanced queries
adapter.query(
    table="leads",
    filters={"client_id": "uuid"},
    limit=50,
    order_by="created_at",
    descending=True,
    select="id,email,current_status"
)
```

---

## 📋 Environment Variables

Required environment variables in `.env`:

```bash
# Supabase Connection
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbG...  # Anon public key (for apikey header)

# Agent-Specific JWTs (signed with JWT_SECRET, role: anon)
SUPABASE_RAG_JWT=eyJhbG...          # user_role: agent_reader
SUPABASE_PERSISTENCE_JWT=eyJhbG...   # user_role: agent_writer

# Service role (bypasses RLS - use sparingly)
SUPABASE_SERVICE_KEY=eyJhbG...
```

---

## 🔄 Integration with Tier 3 Agents

### RAG Agent Usage

```python
from services.persistence.adapters.supabase_adapter import SupabaseAdapter

class RAGAgent:
    def __init__(self):
        self.db = SupabaseAdapter(
            url=os.getenv("SUPABASE_URL"),
            key=os.getenv("SUPABASE_RAG_JWT"),
            anon_key=os.getenv("SUPABASE_KEY")
        )
    
    def get_lead_context(self, lead_id: str) -> dict:
        """Retrieve lead data for LLM context."""
        lead = self.db.read("leads", lead_id)
        conversations = self.db.query(
            "conversations",
            filters={"lead_id": lead_id},
            order_by="created_at",
            descending=True,
            limit=10
        )
        return {"lead": lead, "conversations": conversations}
```

### Persistence Agent Usage

```python
from services.persistence.adapters.supabase_adapter import SupabaseAdapter

class PersistenceAgent:
    def __init__(self):
        self.db = SupabaseAdapter(
            url=os.getenv("SUPABASE_URL"),
            key=os.getenv("SUPABASE_PERSISTENCE_JWT"),
            anon_key=os.getenv("SUPABASE_KEY")
        )
    
    def create_lead(self, lead_data: dict) -> dict:
        """Create a new lead record."""
        return self.db.write("leads", lead_data)
    
    def update_lead_status(self, lead_id: str, status: str) -> dict:
        """Update lead status after outreach."""
        return self.db.update("leads", lead_id, {"current_status": status})
    
    def log_message(self, conversation_id: str, content: str) -> dict:
        """Log a message in a conversation."""
        return self.db.write("messages", {
            "conversation_id": conversation_id,
            "sender_type": "agent",
            "text_content": content,
            "metadata": {}
        })
```

---

## 🧪 Running Tests

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run comprehensive database tests (52 tests)
python -m scripts.comprehensive_table_tests

# Run basic Supabase verification
python -m scripts.verify_supabase_setup
```

---

## 📝 Related Files

| File | Purpose |
|------|---------|
| `services/persistence/adapters/supabase_adapter.py` | Full CRUD + REST API support |
| `scripts/comprehensive_table_tests.py` | 52-test validation suite |
| `scripts/enable_rls_with_policies.sql` | RLS policies for all 5 tables |
| `scripts/supabase-edge-function-fixed.ts` | JWT token generator |

---

## ⚠️ Important Notes

### Required Fields by Table

Some tables have NOT NULL constraints that must be satisfied:

**staging_leads:**
- `campaign_id` (UUID)
- `source` (text)

**leads:**
- `campaign_id` (UUID) - use: `9646f98a-e987-4a8c-b786-9b82ea985d38`
- `current_status` (text)
- `sequence_step` (integer)
- `sequence_active` (boolean)
- `next_action_date` (timestamp)
- `last_contact_date` (timestamp)
- `booking_status` (text)
- `phone_number` (text, can be empty string)

**messages:**
- `metadata` (JSONB, use `{}`)

### Foreign Key Dependencies

Create parent records before child records:

```
clients
  ├── staging_leads (client_id → clients.id)
  ├── leads (client_id → clients.id)
  │     └── conversations (lead_id → leads.id)
  │           └── messages (conversation_id → conversations.id)
  └── conversations (client_id → clients.id)
```

### Token Expiry

- Current JWTs expire in 2030 (5 years from creation)
- Regenerate via Edge Function when needed
- Each token has identifiable `sub` claim for audit trail

---

## 🔒 Security Summary

1. **RAG Agent** can query any table for LLM context without risk of accidental writes
2. **Persistence Agent** can perform full CRUD on leads, conversations, messages
3. **Row-Level Security** enforces permission boundaries at the database level
4. **Always pass `anon_key`** when creating SupabaseAdapter for custom JWTs
