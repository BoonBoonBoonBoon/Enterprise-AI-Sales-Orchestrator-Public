# End-to-End Orchestration Testing

Complete guide for testing the LeadsOrchestrator with T3 agents via Redis Streams.

## 📋 What Gets Tested

### Full Orchestration Flow
```
Test Message → LeadsOrchestrator → Decision Engine → T3 Agent → Result
     ↓              ↓                    ↓              ↓         ↓
  Redis          Consumes            Delegates       Executes  Returns
  Stream         Task                 to RAG/        Task      Result
                                     Persistence
```

### Test Coverage

1. **Task Reception** - Orchestrator receives and parses task envelopes
2. **RAG Delegation** - Enrichment tasks routed to RAG agent
3. **Persistence Delegation** - Bulk operations routed to Persistence agent
4. **Result Flow** - Complete request → response cycle
5. **System Health** - All components running and healthy

## 🚀 Quick Start

### Step 1: Start Docker Services
```powershell
docker compose up -d
```

### Step 2: Start All Consumers
```powershell
# Option A: Start all at once (recommended)
python scripts/start_all_consumers.py

# Option B: Start individually in separate terminals
python -m tiers.tier_2.leads_orchestrator.consumer
python -m tiers.tier_3.rag_agent.consumer
python -m tiers.tier_3.persistence_agent.consumer
```

### Step 3: Verify System Health
```powershell
python scripts/verify_production_ready.py
```

Expected output:
```
✅ [PASS] Docker Compose
✅ [PASS] Redis Connection
✅ [PASS] Stream: leads:tasks
✅ [PASS] Stream: rag:tasks
✅ [PASS] Stream: persistence:tasks
✅ [PASS] Consumer: leads_orchestrator.consumer
✅ [PASS] Consumer: rag_agent.consumer
✅ [PASS] Consumer: persistence_agent.consumer

🎉 ALL CRITICAL SYSTEMS ARE READY!
```

### Step 4: Run E2E Tests
```powershell
# Run all E2E tests with output
pytest tests/integration/test_leads_orchestrator_e2e.py -v -s --no-cov

# Run specific test
pytest tests/integration/test_leads_orchestrator_e2e.py::TestLeadsOrchestratorE2E::test_full_orchestration_flow_with_results -v -s --no-cov

# Run health checks only
pytest tests/integration/test_leads_orchestrator_e2e.py::TestSystemHealthCheck -v -s --no-cov
```

## 📊 Test Scenarios

### Test 1: Basic Task Reception
**Purpose:** Verify orchestrator can receive tasks  
**Stream:** `agentic-dev:orchestrators:leads:tasks`  
**Expected:** Task appears in stream and orchestrator logs show processing

### Test 2: RAG Agent Delegation
**Purpose:** Verify orchestrator delegates enrichment to RAG  
**Trigger:** Send task with `action: "enrich_lead"`  
**Expected:**
- Task appears in `agentic-dev:agents:rag:tasks`
- Correlation ID preserved
- RAG agent processes task

### Test 3: Persistence Agent Delegation
**Purpose:** Verify orchestrator delegates bulk operations  
**Trigger:** Send task with 150+ leads  
**Expected:**
- Task appears in `agentic-dev:agents:persistence:tasks`
- Bulk operation delegated instead of direct execution

### Test 4: Full Orchestration Flow
**Purpose:** End-to-end request → response  
**Flow:**
```
1️⃣ Send search task to orchestrator
2️⃣ Orchestrator delegates to RAG
3️⃣ RAG processes and returns result
4️⃣ Orchestrator compiles final result
5️⃣ Result appears in orchestrator results stream
```

## 📈 Output Examples

### Successful Delegation to RAG
```
================================================================================
🔄 STAGE: RAG AGENT RECEIVED DELEGATION
================================================================================
📡 Stream: agentic-dev:agents:rag:tasks
🧠 Decision: Orchestrator delegated to RAG for search

📦 Envelope:
  Task ID: test-task-abc123
  Correlation ID: corr-xyz789
  Source: leads_orchestrator
  Destination: rag_agent
  Priority: HIGH

  Payload:
    action: search_leads
    query: companies in SaaS industry with 50-200 employees
    filters:
      industry: SaaS
      employee_range: [50, 200]

  Status: PENDING
================================================================================

✅ DELEGATION SUCCESSFUL!
✅ Task found in RAG stream
✅ Correlation preserved: corr-xyz789
```

### Full Flow Complete
```
================================================================================
🎉 END-TO-END FLOW SUCCESSFUL!
================================================================================
✅ Task sent to orchestrator
✅ Orchestrator delegated to RAG
✅ RAG agent processed and returned result
✅ Orchestrator compiled final result

📊 Correlation ID preserved throughout: corr-xyz789
```

## 🔍 Monitoring & Debugging

### Check Stream Contents
```powershell
# Connect to Redis
docker compose exec redis redis-cli

# View stream length
XLEN agentic-dev:orchestrators:leads:tasks

# Read last 10 messages
XREVRANGE agentic-dev:orchestrators:leads:tasks + - COUNT 10

# View consumer groups
XINFO GROUPS agentic-dev:orchestrators:leads:tasks
```

### Check Consumer Logs
Each consumer window will show:
- Task received
- Processing status
- Delegation decisions
- Errors (if any)

### Common Issues

#### No messages in downstream streams
- **Cause:** Orchestrator not making delegation decision
- **Fix:** Check orchestrator logs for decision reasoning
- **Verify:** Task payload matches expected format

#### Timeout waiting for result
- **Cause:** T3 agent not processing or slow response
- **Fix:** Check T3 agent logs, verify agent is running
- **Increase:** Timeout in test (default 30s)

#### Consumer group errors
- **Cause:** Stream or group not initialized
- **Fix:** Restart consumers, they auto-create groups

## 🧹 Cleanup

### Stop Consumers
```powershell
# If using start_all_consumers.py
Press Ctrl+C in the script window

# If running individually
Press Ctrl+C in each terminal
```

### Clean Redis Streams
```powershell
docker compose exec redis redis-cli

# Delete specific stream
DEL agentic-dev:orchestrators:leads:tasks

# Delete all test streams
KEYS agentic-dev:*test* | xargs DEL

# Flush entire Redis (⚠️ use with caution)
FLUSHDB
```

### Stop Docker
```powershell
docker compose down
```

## 📝 Adding New Tests

### Template for New E2E Test
```python
def test_my_new_scenario(self, redis_client):
    """Test description."""
    print("\n🔍 Testing my scenario...")
    
    tenant_id = "agentic-dev"
    task_stream = f"{tenant_id}:orchestrators:leads:tasks"
    
    # Create task envelope
    task_id = f"test-{uuid4()}"
    envelope = task(
        source="e2e_test",
        task_id=task_id,
        payload={"goal": "My test goal", "action": "my_action"},
        destination="leads_orchestrator",
        tenant_id=tenant_id
    )
    
    # Send to orchestrator
    redis_fields = to_redis_fields(envelope)
    msg_id = redis_client.xadd(task_stream, redis_fields)
    
    # Wait for expected behavior
    # ... add assertions ...
    
    print("✅ Test passed!")
```

## 🎯 Success Criteria

System is production-ready when:
- ✅ All health checks pass
- ✅ Messages flow from orchestrator to T3 agents
- ✅ Correlation IDs preserved throughout flow
- ✅ Results return to orchestrator
- ✅ No errors in consumer logs
- ✅ Stream lengths increasing (messages being processed)

## 📚 Related Files

- **Tests:** `tests/integration/test_leads_orchestrator_e2e.py`
- **Health Check:** `scripts/verify_production_ready.py`
- **Startup:** `scripts/start_all_consumers.py`
- **Orchestrator:** `tiers/tier_2/leads_orchestrator/`
- **T3 Agents:** `tiers/tier_3/{rag_agent,persistence_agent,copywriter_agent}/`
- **Envelopes:** `core/envelope/`
- **Redis Client:** `services/redis/client.py`
