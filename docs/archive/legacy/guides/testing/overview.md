# READY TO TEST: Option A - Three-Tier Flow Testing

## Status: âœ… All Setup Complete

All infrastructure has been built and verified. The system is ready to test.

## Three Commands to Run Tests

### Step 1: Verify Everything is Ready
```powershell
python diagnostic.py
```

Expected output:
```
âœ… Redis
âœ… Dependencies
âœ… Files
âœ… VirtualEnv
```

### Step 2: Terminal 1 - Start Consumers
```powershell
python start_all_consumers.py
```

Expected output:
```
============================================================
Starting: Manager
âœ… Started Manager (PID: XXXX)

============================================================
Starting: Leads Orchestrator
âœ… Started Leads Orchestrator (PID: XXXX)

============================================================
Starting: Outreach Orchestrator
âœ… Started Outreach Orchestrator (PID: XXXX)
```

**Leave Terminal 1 running.**

### Step 3: Terminal 2 - Run Tests
```powershell
python test_manager_orchestrator_flow.py
```

Expected flow:
```
TEST 1: Manager â†’ Leads Orchestrator Delegation
  Step 1ï¸âƒ£: Check streams before sending task...
  Step 2ï¸âƒ£: Sending task to manager:tasks...
  Step 3ï¸âƒ£: Waiting for Manager consumer to delegate...
  Step 4ï¸âƒ£: Checking final state...
  Step 5ï¸âƒ£: Reading results from leads:results...
  âœ… PASSED

TEST 2: Manager â†’ Outreach Orchestrator Delegation
  [Similar flow]
  âœ… PASSED

TEST SUMMARY
  âœ… Three-tier flow is working!
```

## If OpenAI Key Not Set

Add this before running Terminal 2 tests:

```powershell
# Set OpenAI API key (if not already in .env)
$env:OPENAI_API_KEY = "sk-proj-your-actual-key-here"
```

## What This Tests

âœ… **Test 1: Manager â†’ Leads Flow**
- Task: "Find 50 AI/ML startups in San Francisco"
- Manager reads from manager:tasks
- Manager delegates to leads:tasks
- Leads orchestrator processes
- Results published to leads:results
- Success = results appear in 20 seconds

âœ… **Test 2: Manager â†’ Outreach Flow**
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

# Should show: redis://<REDACTED_REDIS_URL>

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
| `agent/manager/manager_agent_harness.py` | Manager wrapper | âœ… Complete |
| `agent/manager/consumer.py` | Manager consumer | âœ… Complete |
| `start_all_consumers.py` | Startup script | âœ… Complete |
| `test_manager_orchestrator_flow.py` | Test script | âœ… Complete |
| `diagnostic.py` | Prerequisites checker | âœ… Complete |
| `docs/Complete_Redis_Architecture.md` | Architecture docs | âœ… Complete |
| `TEST_OPTION_A_GUIDE.md` | Full guide | âœ… Complete |
| `QUICK_START.md` | Quick reference | âœ… Complete |
| `PHASE_14_SETUP_SUMMARY.md` | Summary | âœ… Complete |

## After Tests Pass âœ…

Once both tests show `âœ… PASSED`:

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
âœ… Tier 1: Manager (external entry point)
   - manager:tasks (receives requests)
   - manager:results (publishes final results)
   - Harness wrapper with retry logic
   - Consumer group for scaling

âœ… Tier 2: Orchestrators (business logic)
   - leads:tasks/results (discovery, qualification)
   - outreach:tasks/results (campaigns, touchpoints)
   - Both have consumers and harness wrappers

â³ Tier 3: Operational Agents (NOT YET BUILT)
   - copywriter:tasks/results
   - booking:tasks/results
   - sequencing:tasks/results
   - rag:tasks/results
   - persistence:tasks/results
   - deduplication:tasks/results
```

## Next Steps

### Immediate (Now)
1. âœ… Run: `python diagnostic.py`
2. âœ… Terminal 1: `python start_all_consumers.py`
3. âœ… Terminal 2: `python test_manager_orchestrator_flow.py`

### After Tests Pass
1. âœ… Review test results
2. â³ Commit changes
3. â³ Build Tier 3 agents
4. â³ Test complete flow

---

**Ready to test!** Follow the three steps above. ðŸš€

