# QUICK START: Testing Three-Tier Redis Streams (Option A)

## What We Built ✅

1. **Manager Agent Harness** (`agent/manager/manager_agent_harness.py`)
   - Wrapper for Manager Agent with retry logic, timeouts, checkpointing
   
2. **Manager Consumer** (`agent/manager/consumer.py`)
   - Reads from `{tenant}:manager:tasks`
   - Delegates to Leads/Outreach orchestrators
   - Publishes to `{tenant}:manager:results`

3. **Startup Script** (`start_all_consumers.py`)
   - Starts Manager + Leads + Outreach consumers in one command

4. **Test Script** (`test_manager_orchestrator_flow.py`)
   - Tests Manager → Leads delegation
   - Tests Manager → Outreach delegation
   - Monitors stream message counts

5. **Diagnostic Tool** (`diagnostic.py`)
   - Checks prerequisites (Redis, environment, files)

## Quick Start (3 Steps)

### Step 1: Set API Key (if not already set)
```powershell
$env:OPENAI_API_KEY = "sk-proj-..."  # Your actual key
```

### Step 2: Terminal 1 - Start Consumers
```powershell
python start_all_consumers.py
```

Wait for all three to start. Leave this running.

### Step 3: Terminal 2 - Run Test
```powershell
python test_manager_orchestrator_flow.py
```

Press Enter and watch the magic happen! ✨

## What Happens in the Test

```
STEP 1: Check streams before task
  manager:tasks: 0 messages
  leads:tasks: 0 messages
  outreach:tasks: 0 messages

STEP 2: Send task to manager:tasks
  ✅ Task sent

STEP 3: Wait for delegation and processing
  Monitoring for 20 seconds...
  [Consumers process the task]

STEP 4: Check streams after processing
  manager:tasks: 0 → 1
  leads:tasks: 0 → 1  (Manager delegated!)
  leads:results: 0 → 1 (Leads consumer completed!)

STEP 5: Read results from leads:results
  ✅ Result received
```

## Successful Test Output

```
✅ TEST 1 (Manager → Leads):     PASSED
✅ TEST 2 (Manager → Outreach):  PASSED

✅ Three-tier flow is working!
```

## If Tests Fail

### Issue 1: "OpenAI API key required"
```powershell
# Set the key
$env:OPENAI_API_KEY = "sk-proj-your-key"
# Restart consumers
```

### Issue 2: "No results appear"
```powershell
# Terminal 2: Check what's happening
python diagnostic.py

# Check if consumers are running (look at Terminal 1)
# Check for errors in Terminal 1 output
```

### Issue 3: "Redis connection refused"
```powershell
# Verify Redis URL
echo $env:REDIS_URL
# Should show: redis://default:***@redis-15143...

# Or use local Redis
python verify_redis_streams.py
```

## Architecture Verified

If tests pass, you've confirmed:

```
✅ Tier 1: Manager (external entry point)
  - manager:tasks (receives requests)
  - manager:results (publishes final results)

✅ Tier 2: Orchestrators (business logic)
  - leads:tasks/results (working)
  - outreach:tasks/results (working)

⏳ Tier 3: Agents (capabilities)
  - NOT TESTED YET (need to build 6 consumers)
```

## Files Created

| File | Purpose |
|------|---------|
| `agent/manager/manager_agent_harness.py` | Manager production wrapper |
| `agent/manager/consumer.py` | Manager Redis consumer |
| `start_all_consumers.py` | Start all 3 consumers |
| `test_manager_orchestrator_flow.py` | Test delegation flow |
| `diagnostic.py` | Check prerequisites |
| `TEST_OPTION_A_GUIDE.md` | Full testing guide |
| `QUICK_START.md` | This file |

## Stream Names

```
agentic-dev:manager:tasks       (entry point)
agentic-dev:manager:results     (exit point)

agentic-dev:leads:tasks         (from Manager delegation)
agentic-dev:leads:results       (Leads consumer response)

agentic-dev:outreach:tasks      (from Manager delegation)
agentic-dev:outreach:results    (Outreach consumer response)
```

## Consumer Groups

- `manager-workers` (on manager:tasks)
- `leads-workers` (on leads:tasks)
- `outreach-workers` (on outreach:tasks)

## Next After Tests Pass

Option A is just testing tiers 1 and 2.

To complete the system (Task 9-14):
- Build Copywriter Consumer
- Build Booking Consumer
- Build Sequencing Consumer
- Verify/Update RAG Consumer
- Verify/Update Persistence Consumer
- Build Deduplication Consumer

Then run full end-to-end test (Task 15).

## Useful Commands

```powershell
# Check Redis streams
redis-cli KEYS "agentic-dev:*"

# View a stream
redis-cli XLEN agentic-dev:leads:tasks

# Read messages
redis-cli XREAD COUNT 10 STREAMS agentic-dev:leads:results 0

# Monitor all streams in real-time
python scripts/streams_health.py

# Check consumer groups
redis-cli XINFO GROUPS agentic-dev:manager:tasks
```

## Detailed Guide

For more details, see: `TEST_OPTION_A_GUIDE.md`

---

**Status:** Ready to test! All prerequisites met ✅
