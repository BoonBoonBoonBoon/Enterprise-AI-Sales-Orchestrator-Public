# Persistence Agent Write Test - Implementation Complete ✅

## What Was Created

### 1. **Test File** (`test_write_all_tables.py`)
- **Location:** `tiers/tier_3/persistence_agent/tests/test_write_all_tables.py`
- **Size:** ~650 lines
- **Features:**
  - 4 individual test methods (one per table)
  - 1 master test (full workflow)
  - Mock data with FK relationships
  - Async Redis Streams communication
  - Cleanup instructions

### 2. **Pre-Flight Check** (`run_write_test.py`)
- **Location:** `tiers/tier_3/persistence_agent/tests/run_write_test.py`
- **Features:**
  - Environment variable validation
  - Redis connectivity check
  - Supabase connectivity check
  - Consumer status prompts
  - Auto-runs test if checks pass

---

## Test Data Summary

| Table | Records | Relationships |
|-------|---------|---------------|
| **staging_leads** | 4 | Standalone (no FK dependencies) |
| **leads** | 4 | Standalone (client_id generated) |
| **conversations** | 4 | FK → leads (linked to all 4 leads) |
| **messages** | 6 | FK → conversations (distributed across convos) |
| **TOTAL** | **18** | **3 FK relationships** |

---

## Mock Data Details

### Staging Leads (4)
```
test_staging_1_{timestamp}@example.com - John Doe, Acme Corp, CEO (pending)
test_staging_2_{timestamp}@example.com - Jane Smith, Beta Inc, CTO (complete, promotion_ready)
test_staging_3_{timestamp}@example.com - Mike Johnson, Gamma LLC, VP Sales (failed)
test_staging_4_{timestamp}@example.com - Lisa Chen, Delta Systems, Head of Marketing (complete, promotion_ready)
```

### Leads (4)
```
test_lead_john_{timestamp}@acme.com - John Parker, VP Engineering (score: 85, qualified)
test_lead_jane_{timestamp}@beta.com - Jane Williams, Director Product (score: 70, contacted)
test_lead_mike_{timestamp}@gamma.com - Mike Anderson, Sales Manager (score: 60, pending)
test_lead_lisa_{timestamp}@delta.com - Lisa Taylor, CMO (score: 90, qualified)
```

### Conversations (4)
```
Conv 1 → Lead 1: "Partnership Inquiry - Acme Corp" (active)
Conv 2 → Lead 2: "Product Demo Request - Beta Technologies" (active)
Conv 3 → Lead 3: "Pricing Questions - Gamma Solutions" (closed)
Conv 4 → Lead 4: "Enterprise Pilot Program - Delta" (active)
```

### Messages (6)
```
Msg 1 → Conv 1: Outbound - Partnership intro (sentiment: 0.0)
Msg 2 → Conv 1: Inbound - Positive response (sentiment: 0.8)
Msg 3 → Conv 2: Outbound - Demo request (sentiment: 0.0)
Msg 4 → Conv 2: Inbound - Acceptance (sentiment: 0.5)
Msg 5 → Conv 3: Outbound - Pricing info (sentiment: 0.0)
Msg 6 → Conv 4: Inbound - Not interested (sentiment: -0.7)
```

---

## How to Run

### Step 1: Start Persistence Agent Consumer

**Terminal 1** (Keep running):
```powershell
.\.venv\Scripts\Activate.ps1
python -m tiers.tier_3.persistence_agent.consumer
```

### Step 2: Run the Test

**Terminal 2**:
```powershell
.\.venv\Scripts\Activate.ps1
python tiers/tier_3/persistence_agent/tests/run_write_test.py
```

**Or directly with pytest:**
```powershell
python -m pytest tiers/tier_3/persistence_agent/tests/test_write_all_tables.py::TestWriteAllTables::test_full_workflow -v -s
```

---

## Expected Output

```
================================================================================
MASTER TEST: Full Write Workflow (All 4 Tables)
================================================================================

TEST 1: Writing 4 staging_leads (batch)
📤 Published task to agentic-dev:agents:persistence:tasks
✅ Received result
✅ Created 4 staging leads

TEST 2: Writing 4 leads (individual creates)
📝 Creating lead 1/4: test_lead_john_{timestamp}@acme.com
✅ Created lead with ID: {uuid}
...
✅ Created all 4 leads

TEST 3: Writing 4 conversations (linked to leads)
📝 Creating conversation 1/4: Partnership Inquiry - Acme Corp
✅ Created conversation with ID: {uuid}
...
✅ Created all 4 conversations

TEST 4: Writing 6 messages (linked to conversations)
📝 Creating message 1/6 (outbound): Partnership intro...
✅ Created message with ID: {uuid}
...
✅ Created all 6 messages

================================================================================
✅ FULL WORKFLOW COMPLETE
================================================================================
📊 Summary:
  - Staging Leads: 4 created
  - Leads: 4 created
  - Conversations: 4 created
  - Messages: 6 created
  - Test Timestamp: {timestamp}
================================================================================
```

---

## Cleanup

After testing, run this SQL in Supabase SQL Editor:

```sql
-- Get your test timestamp from the output
-- Replace {timestamp} with actual value (e.g., 20251130_153045)

-- Delete messages
DELETE FROM messages
WHERE conversation_id IN (
  SELECT id FROM conversations WHERE lead_id IN (
    SELECT id FROM leads WHERE email LIKE '%{timestamp}%'
  )
);

-- Delete conversations
DELETE FROM conversations
WHERE lead_id IN (
  SELECT id FROM leads WHERE email LIKE '%{timestamp}%'
);

-- Delete leads
DELETE FROM leads WHERE email LIKE '%{timestamp}%';

-- Delete staging_leads
DELETE FROM staging_leads WHERE email LIKE '%{timestamp}%';
```

---

## Current Status

✅ **Test file created** - `test_write_all_tables.py`  
✅ **Pre-flight check created** - `run_write_test.py`  
✅ **Environment validated** - Redis, Supabase, OpenAI API keys set  
✅ **Mock data designed** - 18 records with FK relationships  
⏳ **Consumer status** - Needs to be started  
⏳ **Test execution** - Ready to run

---

## Next Steps

1. **Start consumer** in Terminal 1
2. **Run test** in Terminal 2 using `run_write_test.py`
3. **Verify in Supabase** - Check tables for test records
4. **Cleanup** - Run SQL cleanup script
5. **Optional:** Add to CI/CD pipeline for automated testing

---

**Files Created:**
- `tiers/tier_3/persistence_agent/tests/test_write_all_tables.py` (650 lines)
- `tiers/tier_3/persistence_agent/tests/run_write_test.py` (150 lines)

**Total Implementation:** ~800 lines of production-ready test code
