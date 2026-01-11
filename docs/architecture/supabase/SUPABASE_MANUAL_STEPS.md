# Supabase Manual Steps - Final Setup

## Status
- ✅ JWT tokens generated and saved to `.env`
- ✅ RAG agent updated to use `SUPABASE_RAG_JWT`
- ✅ Persistence agent updated to use `SUPABASE_PERSISTENCE_JWT`
- ⏳ **NEXT:** Run SQL scripts in Supabase Dashboard (migration + RLS)

---

## Step 1: Create Test Client Record

**Location:** Supabase Dashboard → SQL Editor → New Query

**Run this:**
```sql
-- File: scripts/create_test_client.sql
INSERT INTO clients (id, name)
VALUES ('93d28de3-2835-52f3-b2ef-c2eb8a2ac09b', 'Agentic Dev Test Client')
ON CONFLICT (id) DO NOTHING;
```

**Verify:**
```sql
SELECT * FROM clients WHERE id = '93d28de3-2835-52f3-b2ef-c2eb8a2ac09b';
```

---

## Step 2: Apply Staging Conversation Migration

**Location:** Supabase Dashboard → SQL Editor → New Query

**Run entire file:** `docs/architecture/supabase/migrations/20260102_staging_conversations.sql`

This will:
1. Add `archived_at` to `staging_leads`
2. Create `staging_conversations` (FK → `staging_leads`)
3. Create `staging_messages` (FK → `staging_conversations`)
4. Add indexes for email + FK lookups

**Verify:**
```sql
-- Confirm tables exist
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
   AND tablename IN ('staging_conversations', 'staging_messages')
ORDER BY tablename;

-- Confirm archived_at added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
   AND table_name = 'staging_leads'
   AND column_name = 'archived_at';
```

---

## Step 3: Enable RLS and Create Policies

**Location:** Supabase Dashboard → SQL Editor → New Query

**Run entire file:** `scripts/setup_rls_policies.sql`

This will:
1. Enable Row Level Security on the core agent tables
2. Create helper function to extract `user_role` from JWT
3. Create policies so:
   - `agent_reader` can SELECT (for RAG agent)
   - `agent_writer` can perform ALL operations (for Persistence agent)

**Verify:**
```sql
-- Check RLS enabled
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE tablename IN (
   'clients',
   'staging_leads',
   'staging_conversations',
   'staging_messages',
   'lead_outreach',
   'leads',
   'conversations',
   'messages'
);

-- Check policies exist
SELECT schemaname, tablename, policyname, cmd 
FROM pg_policies
WHERE tablename IN (
   'clients',
   'staging_leads',
   'staging_conversations',
   'staging_messages',
   'lead_outreach',
   'leads',
   'conversations',
   'messages'
)
ORDER BY tablename, policyname;
```

Expected: 
- All tables have `rowsecurity = TRUE`
- Policies exist for each table (service_role bypass + agent reader/writer policies)

---

## Step 4: Test JWT Authentication

After running both SQL scripts, test from your terminal:

```powershell
# Test that agents can authenticate
python -m tiers.tier_3.persistence_agent.tests.direct_test
```

Expected output:
- ✅ Client lookup succeeds
- ✅ All 4 table writes succeed
- ✅ No permission errors

---

## Troubleshooting

### If you see "permission denied" errors:
1. Check JWT tokens are in `.env` (run: `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('RAG:', os.getenv('SUPABASE_RAG_JWT')[:50]); print('Persistence:', os.getenv('SUPABASE_PERSISTENCE_JWT')[:50])"`)
2. Verify RLS policies exist (run verification queries above)
3. Check `user_role` claim in JWT (decode token at jwt.io)

### If RLS policies fail to create:
- Ensure you're using Supabase SQL Editor (not psql)
- Run each policy individually to find which one fails
- Check if policies already exist: `SELECT * FROM pg_policies WHERE tablename = 'clients';`

---

## JWT Token Details

**RAG Agent Token (READ ONLY)**
- Subject: `rag-agent-service`
- Role: `agent_reader`
- Permissions: SELECT on all 4 tables

**Persistence Agent Token (WRITE)**
- Subject: `persistence-agent-service`
- Role: `agent_writer`
- Permissions: ALL operations on all 4 tables

These tokens are long-lived (no expiry) and stored in `.env`:
- `SUPABASE_RAG_JWT`
- `SUPABASE_PERSISTENCE_JWT`
