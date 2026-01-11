# Tiers - Three-Tier Agent Architecture

This directory contains the three-tier agent orchestration system that powers the Agentic System.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        TIER 1 - STRATEGIC                        │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    Manager Agent                          │   │
│   │  • Receives high-level goals from users/APIs             │   │
│   │  • Routes to appropriate orchestrators                   │   │
│   │  • Decision-making ONLY (no execution)                   │   │
│   └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TIER 2 - BUSINESS LOGIC                      │
│                                                                   │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│   │   Leads     │  │  Outreach   │  │   Audit     │  ...        │
│   │Orchestrator │  │Orchestrator │  │Orchestrator │             │
│   └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                   │
│   • Decompose workflows into atomic tasks                        │
│   • Coordinate multi-step operations                             │
│   • Delegate to Tier 3 agents                                    │
│   • NO horizontal communication (vertical only)                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TIER 3 - EXECUTION                          │
│                                                                   │
│   ┌────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐        │
│   │  RAG   │  │Persistence │  │Copywriter│  │Scheduler │  ...   │
│   │ Agent  │  │   Agent    │  │  Agent   │  │  Agent   │        │
│   └────────┘  └────────────┘  └──────────┘  └──────────┘        │
│                                                                   │
│   • Perform atomic, specialized tasks                            │
│   • Wrapped in Agent Harness for reliability                     │
│   • Report results back to orchestrators                         │
└─────────────────────────────────────────────────────────────────┘
```

## Communication Rules (CRITICAL)

### Vertical Communication ONLY

```
Tier 1 ←→ Tier 2 ←→ Tier 3
   ↕           ↕           ↕
(results)  (results)  (results)
```

- **Tier 1 → Tier 2:** Manager routes goals to orchestrators
- **Tier 2 → Tier 3:** Orchestrators delegate tasks to agents
- **Tier 3 → Tier 2:** Agents return results to orchestrators
- **Tier 2 → Tier 1:** Orchestrators return results to Manager

### NO Horizontal Communication

```
❌ Tier 2 ←✕→ Tier 2    (Orchestrators cannot talk to each other)
❌ Tier 3 ←✕→ Tier 3    (Agents cannot talk to each other)
```

All cross-orchestrator coordination **MUST** go through Manager (Tier 1).

## Redis Stream Naming Convention

```
{tenant}:manager:tasks              → Manager input
{tenant}:manager:results            → Manager output

{tenant}:orchestrators:{name}:tasks → Orchestrator input
{tenant}:orchestrators:{name}:results → Orchestrator output

{tenant}:agents:{name}:tasks        → Agent input
{tenant}:agents:{name}:results      → Agent output
```

## Directory Structure

```
tiers/
├── README.md           ← You are here
├── __init__.py
│
├── tier_1/             ← Strategic Layer
│   └── manager/        ← Decision-making agent
│
├── tier_2/             ← Business Logic Layer
│   ├── leads_orchestrator/
│   ├── outreach_orchestrator/
│   ├── inbound_orchestrator/
│   ├── audit_orchestrator/
│   └── control_orchestrator/
│
└── tier_3/             ← Execution Layer
    ├── rag_agent/
    ├── persistence_agent/
    ├── copywriter_agent/
    ├── scheduler_agent/
    └── channel_sequencer_agent/
```

## Getting Started

### Run All Consumers

```bash
# Start Manager
python -m tiers.tier_1.manager.consumer

# Start Orchestrators
python -m tiers.tier_2.leads_orchestrator.consumer
python -m tiers.tier_2.outreach_orchestrator.consumer

# Start Agents
python -m tiers.tier_3.rag_agent.consumer
python -m tiers.tier_3.persistence_agent.consumer
python -m tiers.tier_3.copywriter_agent.consumer
```

### Quick Test

```bash
# Send a test goal to Manager
python scripts/testing/send_manager_test.py
```

## See Also

- [Architecture Reference](../docs/COMPLETE_ARCHITECTURE_REFERENCE.md)
- [Copilot Instructions](../.github/copilot-instructions.md) — Contains full communication rules
- [Harness Documentation](../core/harness/README.md)
