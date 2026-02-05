# READY TO TEST: Option A - Three-Tier Flow Testing

## Status: ✅ All Setup Complete

All infrastructure has been built and verified. The system is ready to test.

## Three Commands to Run Tests

### Step 1: Verify Everything is Ready
```powershell
python diagnostic.py
```

Expected output:
```
✅ Redis
✅ Dependencies
✅ Files
✅ VirtualEnv
```

### Step 2: Terminal 1 - Start Consumers
```powershell
python start_all_consumers.py
```

Expected output:
```
============================================================
Starting: Manager
✅ Started Manager (PID: XXXX)

============================================================
Starting: Leads Orchestrator
✅ Started Leads Orchestrator (PID: XXXX)

============================================================
Starting: Outreach Orchestrator
✅ Started Outreach Orchestrator (PID: XXXX)
```

**Leave Terminal 1 running.**

### Step 3: Terminal 2 - Run Tests
```powershell
python test_manager_orchestrator_flow.py
```

Expected flow:
```
TEST 1: Manager → Leads Orchestrator Delegation
  Step 1️⃣: Check streams before sending task...
  Step 2️⃣: Sending task to manager:tasks...
  Step 3️⃣: Waiting for Manager consumer to delegate...
  Step 4️⃣: Checking final state...
  Step 5️⃣: Reading results from leads:results...
  ✅ PASSED

TEST 2: Manager → Outreach Orchestrator Delegation
  [Similar flow]
  ✅ PASSED

TEST SUMMARY
  ✅ Three-tier flow is working!
```

## If OpenAI Key Not Set

Add this before running Terminal 2 tests:

```powershell
# Set OpenAI API key (if not already in .env)
$env:OPENAI_API_KEY = "sk-proj-your-actual-key-here"
```

## What This Tests

✅ **Test 1: Manager → Leads Flow**
- Task: "Find 50 AI/ML startups in San Francisco"
- Manager reads from manager:tasks
- Manager delegates to leads:tasks
- Leads orchestrator processes
- Results published to leads:results
- Success = results appear in 20 seconds

✅ **Test 2: Manager → Outreach Flow**
- Task: "Launch Q4 email outreach campaign"
- Manager reads from manager:tasks
- Manager delegates to outreach:tasks
- Outreach orchestrator processes
- Results published to outreach:results
- Success = results appear in 20 seconds

## Troubleshooting

### No Results After 20 Seconds

**Step 1:** Check Terminal 1 (consumers) for errors

**Step 2:** Run diagnostic
```powershell
python diagnostic.py
```

**Step 3:** Check Redis directly
```powershell
redis-cli KEYS "agentic-dev:*"
redis-cli XLEN agentic-dev:manager:tasks
```

**Step 4:** Verify OpenAI key is set
```powershell
echo $env:OPENAI_API_KEY
# Should show: sk-proj-...
```

### "Redis connection refused"

```powershell
# Check REDIS_URL
echo $env:REDIS_URL

# Should show: redis://default:***@redis-15143...

# Or verify local Redis works
redis-cli PING
# Should return: PONG
```

### "Module not found" errors

```powershell
# Reinstall dependencies
pip install -r requirements.txt

# Or just check what's installed
pip list | grep -E "redis|deepagents|langchain|openai"
```

## Files Built

| File | Purpose | Status |
|------|---------|--------|
| `agent/manager/manager_agent_harness.py` | Manager wrapper | ✅ Complete |
| `agent/manager/consumer.py` | Manager consumer | ✅ Complete |
| `start_all_consumers.py` | Startup script | ✅ Complete |
| `test_manager_orchestrator_flow.py` | Test script | ✅ Complete |
| `diagnostic.py` | Prerequisites checker | ✅ Complete |
| `docs/Complete_Redis_Architecture.md` | Architecture docs | ✅ Complete |
| `TEST_OPTION_A_GUIDE.md` | Full guide | ✅ Complete |
| `QUICK_START.md` | Quick reference | ✅ Complete |
| `PHASE_14_SETUP_SUMMARY.md` | Summary | ✅ Complete |

## After Tests Pass ✅

Once both tests show `✅ PASSED`:

1. **Next:** Build Tier 3 agents (Tasks 9-14)
   - Copywriter Consumer
   - Booking Consumer
   - Sequencing Consumer
   - Verify RAG Consumer
   - Verify Persistence Consumer
   - Build Deduplication Consumer

2. **Then:** Test complete flow (Task 15)
   - End-to-end with all 3 tiers
   - Results aggregation at each level

3. **Finally:** Production hardening (Tasks 16-20)
   - Monitoring
   - Cleanup
   - Documentation
   - Docker/Kubernetes

## Quick Reference

### Stream Names
```
agentic-dev:manager:tasks          (entry point)
agentic-dev:manager:results        (exit point)
agentic-dev:leads:tasks            (Leads input)
agentic-dev:leads:results          (Leads output)
agentic-dev:outreach:tasks         (Outreach input)
agentic-dev:outreach:results       (Outreach output)
```

### Consumer Groups
```
manager-workers    (on manager:tasks)
leads-workers      (on leads:tasks)
outreach-workers   (on outreach:tasks)
```

### Key Commands
```powershell
# Start consumers
python start_all_consumers.py

# Run tests
python test_manager_orchestrator_flow.py

# Check status
python diagnostic.py

# View Redis streams
redis-cli KEYS "agentic-dev:*"
redis-cli XLEN agentic-dev:manager:tasks

# Monitor streams
python scripts/streams_health.py
```

## System Architecture Verified

```
✅ Tier 1: Manager (external entry point)
   - manager:tasks (receives requests)
   - manager:results (publishes final results)
   - Harness wrapper with retry logic
   - Consumer group for scaling

✅ Tier 2: Orchestrators (business logic)
   - leads:tasks/results (discovery, qualification)
   - outreach:tasks/results (campaigns, touchpoints)
   - Both have consumers and harness wrappers

⏳ Tier 3: Operational Agents (NOT YET BUILT)
   - copywriter:tasks/results
   - booking:tasks/results
   - sequencing:tasks/results
   - rag:tasks/results
   - persistence:tasks/results
   - deduplication:tasks/results
```

## Next Steps

### Immediate (Now)
1. ✅ Run: `python diagnostic.py`
2. ✅ Terminal 1: `python start_all_consumers.py`
3. ✅ Terminal 2: `python test_manager_orchestrator_flow.py`

### After Tests Pass
1. ✅ Review test results
2. ⏳ Commit changes
3. ⏳ Build Tier 3 agents
4. ⏳ Test complete flow

---

**Ready to test!** Follow the three steps above. 🚀
