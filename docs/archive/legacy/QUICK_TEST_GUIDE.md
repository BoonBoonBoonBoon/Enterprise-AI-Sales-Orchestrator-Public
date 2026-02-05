# Quick Test Guide

## Before Running Tests

1. **Ensure Redis is accessible**:
   ```bash
   # Connection details in .env or hardcoded in test files
   REDIS_URL=redis://default:***@redis-15143.c335.europe-west2-1.gce.redns.redis-cloud.com:15143/0
   TENANT_ID=agentic-dev
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Test Sequence

### Test 1: Verify Stream Naming
```bash
python test_stream_naming.py
```

**Expected Output**:
- All Tier 1, 2, and 3 streams listed with message counts
- No old incorrect streams found
- Confirmation that naming is consistent

---

### Test 2: End-to-End Delegation Test
```bash
python test_e2e_flow.py
```

**What It Tests**:
1. **Manager → Leads**: Sends task to manager, verifies delegation to leads
2. **Leads → RAG**: Sends task to leads, verifies delegation to RAG

**Expected Output**:
```
======================================================================
  AGENTIC SYSTEM - END-TO-END FLOW TEST
======================================================================

Tenant: agentic-dev
Redis: redis-15143.c335.europe-west2-1.gce.redns.redis-cloud.com:15143/0

======================================================================
  Starting All Consumers
======================================================================
[OK] Consumers started

======================================================================
  TEST 1: Manager -> Leads Delegation
======================================================================
Baseline:
  leads:tasks: X
  manager:tasks: Y

Sending test task: test-leads-TIMESTAMP
  Goal: Find 50 AI startups in San Francisco

Task added to manager:tasks: MESSAGE_ID

Waiting 5 seconds for delegation...

After processing:
  leads:tasks: X -> X+1
  manager:tasks: Y -> Y+1

[OK] MANAGER->LEADS DELEGATION SUCCESSFUL!
     Delegated 1 task(s) to Leads Orchestrator

======================================================================
  TEST 2: Leads -> RAG Delegation
======================================================================
[Similar output for RAG delegation test]

======================================================================
  TEST SUMMARY
======================================================================
Test 1 (Manager -> Leads): [OK] PASSED
Test 2 (Leads -> RAG):     [OK] PASSED

[OK] END-TO-END FLOW VERIFIED!
    Two-tier delegation pipeline is working correctly.
```

---

### Test 3: Check Consumer Logs

If delegation is working, you should see logs like:

**Leads Consumer**:
```
[CONSUMER] Processing task test-rag-TIMESTAMP from message 1234567890-0
[CONSUMER] Task data: {'task_id': 'test-rag-...', 'goal': 'Enrich lead data...', 'data': {...}}
```

**Leads Orchestrator**:
```
LeadsOrchestrator executing: {'task_id': '...', 'goal': 'Enrich lead data...', ...} (id=exec_...)
Extracted goal: Enrich lead data for Acme Corp
Context: {'lead_id': 'lead_123', 'company': 'Acme Corp'}
Invoking Deep Agent with messages: [...]
```

**RAG Delegation Tool** (if working):
```
[TOOL CALL] delegate_to_rag_agent_tool invoked with lead_id=lead_123, query=...
[TOOL CALL] Enqueuing to stream: agentic-dev:agents:rag:tasks
[TOOL CALL] Delegated enrichment to RAG Agent: rag_task_...
```

---

## Troubleshooting

### Issue: "No delegation detected" for Test 1

**Check**:
1. Are consumers running?
   ```bash
   ps aux | grep python | grep consumer
   ```

2. Is Manager consumer listening to correct stream?
   ```bash
   python test_stream_naming.py
   # Should show: agentic-dev:leads:tasks
   ```

3. Check Manager logs for intent classification
   - Should classify "Find 50 AI startups" as `lead_enrichment`
   - Should delegate to `["leads"]` orchestrator

**Fix**:
- Ensure `start_all_consumers.py` is running all consumers
- Verify no exceptions in consumer startup logs

---

### Issue: "No delegation detected" for Test 2

**Check**:
1. Is Leads consumer receiving the task?
   - Look for `[CONSUMER] Processing task` logs

2. Is Leads orchestrator executing?
   - Look for `LeadsOrchestrator executing` logs

3. Is RAG delegation tool being called?
   - Look for `[TOOL CALL]` logs
   - If missing, Deep Agent is not invoking the tool

**Fix Options**:

**Option A - More Explicit Goal**:
Change test task goal to be more explicit:
```python
"goal": "Use delegate_to_rag_agent_tool to enrich lead_123 with data for Acme Corp"
```

**Option B - Direct Tool Call**:
Bypass Deep Agent and call tool directly for testing:
```python
# In leads_orchestrator.py execute() method
if "enrich" in goal.lower():
    # Direct tool invocation
    lead_id = context.get("lead_id", "unknown")
    return self._create_delegate_to_rag_agent_tool()(lead_id, goal)
```

**Option C - Adjust System Prompt**:
Make system prompt more directive:
```python
"If the goal contains 'enrich', 'enhance', or 'augment', ALWAYS use delegate_to_rag_agent_tool."
```

---

## Debug Mode

For detailed debugging, set logging to DEBUG:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or run with environment variable:
```bash
export LOG_LEVEL=DEBUG
python test_e2e_flow.py
```

---

## Success Indicators

✅ **Full Success**:
- Test 1 PASSED: Manager → Leads delegation working
- Test 2 PASSED: Leads → RAG delegation working
- Both tests show message count increases
- Logs show tool invocations

⚠️ **Partial Success**:
- Test 1 PASSED: Tier 1 delegation working
- Test 2 INCOMPLETE: Tier 2 delegation needs debugging
- This is the current expected state

❌ **Failure**:
- Test 1 INCOMPLETE: Basic delegation broken
- Check stream naming and consumer startup

---

## Quick Commands

```bash
# Verify stream naming
python test_stream_naming.py

# Run full E2E test
python test_e2e_flow.py

# Check running consumers
ps aux | grep consumer

# Start consumers manually
python start_all_consumers.py

# Test just Manager delegation
python test_manager_direct.py

# Check Redis streams directly
redis-cli -h redis-15143.c335.europe-west2-1.gce.redns.redis-cloud.com -p 15143 -a PASSWORD
> XLEN agentic-dev:leads:tasks
> XLEN agentic-dev:agents:rag:tasks
```

---

**Last Updated**: November 22, 2025  
**Status**: Ready for testing with enhanced logging
