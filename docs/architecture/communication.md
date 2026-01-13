# Communication Rules

This document defines the strict communication rules governing inter-component messaging.

## Core Rule: Vertical Only

**Orchestrators (Tier 2) can ONLY communicate:**

- **UPWARD:** To Manager (Tier 1) via result streams
- **DOWNWARD:** To Agents (Tier 3) via task streams

**FORBIDDEN:** Direct orchestrator-to-orchestrator communication.

## Visual Diagram

```
                    ┌─────────────────┐
                    │     Manager     │
                    │    (Tier 1)     │
                    └────────┬────────┘
                             │
               ┌─────────────┴─────────────┐
               │                           │
               ▼                           ▼
     ┌─────────────────┐         ┌─────────────────┐
     │     Leads       │         │    Outreach     │
     │   (Tier 2)      │    ✗    │    (Tier 2)     │
     └────────┬────────┘◄───────►└────────┬────────┘
              │          BLOCKED          │
    ┌─────────┼─────────┐       ┌─────────┼─────────┐
    ▼         ▼         ▼       ▼         ▼         ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│ RAG  │ │Persis│ │ Copy │ │ RAG  │ │Persis│ │ Copy │
│(T3)  │ │(T3)  │ │(T3)  │ │(T3)  │ │(T3)  │ │(T3)  │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

---

## Allowed Communication Paths

### Manager → Orchestrator

```python
# ✅ ALLOWED
stream = f"{tenant}:orchestrators:leads:tasks"
redis.xadd(stream, task_envelope)
```

### Orchestrator → Agent

```python
# ✅ ALLOWED
stream = f"{tenant}:agents:rag:tasks"
redis.xadd(stream, task_envelope)
```

### Agent → Orchestrator (Results)

```python
# ✅ ALLOWED
result_stream = f"{tenant}:agents:rag:results"
redis.xadd(result_stream, result_envelope)
```

### Orchestrator → Manager (Results)

```python
# ✅ ALLOWED
result_stream = f"{tenant}:orchestrators:leads:results"
redis.xadd(result_stream, result_envelope)
```

---

## Forbidden Communication Paths

### Orchestrator → Orchestrator

```python
# ❌ FORBIDDEN
# LeadsOrchestrator CANNOT do this:
stream = f"{tenant}:orchestrators:outreach:tasks"
redis.xadd(stream, task)  # VIOLATION!
```

### Agent → Agent

```python
# ❌ FORBIDDEN
# RAGAgent CANNOT do this:
stream = f"{tenant}:agents:persistence:tasks"
redis.xadd(stream, task)  # VIOLATION!
```

### Agent → Orchestrator (Tasks)

```python
# ❌ FORBIDDEN
# Agent CANNOT send tasks to orchestrator:
stream = f"{tenant}:orchestrators:leads:tasks"
redis.xadd(stream, task)  # VIOLATION!
```

---

## Enforcement Mechanisms

### Code Guardrails

```python
# In orchestrator base class
def assert_agents_stream(self, stream: str) -> None:
    """Ensure stream is an agent stream, not orchestrator."""
    if ":orchestrators:" in stream:
        raise ValueError(
            f"Orchestrators cannot publish to orchestrator streams: {stream}"
        )
```

### Usage

```python
class LeadsOrchestrator(DeepAgentHarness):
    def delegate_to_agent(self, agent_name: str, payload: dict):
        stream = f"{self.tenant_id}:agents:{agent_name}:tasks"
        self.assert_agents_stream(stream)  # Guard check
        self.redis.xadd(stream, payload)
```

---

## Cross-Orchestrator Coordination

When Leads needs Outreach to handle a reply:

### Incorrect (Forbidden)

```python
# ❌ LeadsOrchestrator directly calling Outreach
class LeadsOrchestrator:
    def process_inbound(self, email):
        context = self.get_lead_context(email)
        reply_packet = self.build_reply_packet(email, context)

        # WRONG! Cannot call outreach directly
        self.redis.xadd(
            f"{tenant}:orchestrators:outreach:tasks",
            {"action": "handle_reply", "reply_packet": reply_packet}
        )
```

### Correct (Via Manager)

```python
# ✅ LeadsOrchestrator returns result to Manager
class LeadsOrchestrator:
    def process_inbound(self, email):
        context = self.get_lead_context(email)
        reply_packet = self.build_reply_packet(email, context)

        # Return to Manager with reply_packet
        return {
            "status": "success",
            "reply_packet": reply_packet  # Manager handles chaining
        }

# Manager receives and chains
class Manager:
    def handle_leads_result(self, result):
        if "reply_packet" in result:
            # Manager routes to Outreach
            self.redis.xadd(
                f"{tenant}:orchestrators:outreach:tasks",
                {"action": "handle_reply", "reply_packet": result["reply_packet"]}
            )
```

---

## Stream Naming Convention

| Component              | Stream Pattern                          |
| ---------------------- | --------------------------------------- |
| Manager (tasks)        | `{tenant}:manager:tasks`                |
| Manager (results)      | `{tenant}:manager:results`              |
| Orchestrator (tasks)   | `{tenant}:orchestrators:{name}:tasks`   |
| Orchestrator (results) | `{tenant}:orchestrators:{name}:results` |
| Agent (tasks)          | `{tenant}:agents:{name}:tasks`          |
| Agent (results)        | `{tenant}:agents:{name}:results`        |

---

## Why These Rules?

### 1. Single Point of Coordination

Manager has complete visibility into system state. No hidden orchestrator-to-orchestrator dependencies.

### 2. Simplified Debugging

When investigating issues, you only need to check:

- Manager decisions
- Single orchestrator workflow
- Agent executions

### 3. Easier Testing

Mock Manager to test orchestrator in isolation. No need to spin up other orchestrators.

### 4. Clear Audit Trail

```
Manager → Leads → RAG → Leads → Manager → Outreach → Copywriter → Outreach → Manager
```

Every hop is logged. Full traceability.

---

## Verification

Run isolation check:

```powershell
.\.venv\Scripts\python.exe -c "
import ast
import os

violations = []
for root, dirs, files in os.walk('tiers/tier_2'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            content = open(path).read()
            if ':orchestrators:' in content and 'xadd' in content:
                violations.append(path)

if violations:
    print('VIOLATIONS FOUND:')
    for v in violations:
        print(f'  - {v}')
else:
    print('No violations found')
"
```

## Related

- [System Design](design.md)
- [Data Flow](data-flow.md)
- [Three-Tier Architecture](../concepts/three-tier-architecture.md)
