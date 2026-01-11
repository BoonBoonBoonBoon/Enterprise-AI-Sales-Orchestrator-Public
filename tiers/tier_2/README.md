# Tier 2 - Business Logic Layer

**Role:** Workflow Orchestration & Task Decomposition

## Purpose

Tier 2 contains **orchestrators** that:

- Receive goals from Manager (Tier 1)
- Decompose complex workflows into atomic tasks
- Delegate specialized work to Tier 3 agents
- Coordinate multi-step operations
- Return aggregated results to Manager

## Components

| Orchestrator                                     | Responsibility                          | Status      |
| ------------------------------------------------ | --------------------------------------- | ----------- |
| [leads_orchestrator/](leads_orchestrator/)       | Lead CRUD, enrichment, deduplication    | ✅ Active   |
| [outreach_orchestrator/](outreach_orchestrator/) | Multi-channel campaign coordination     | ✅ Active   |
| [inbound_orchestrator/](inbound_orchestrator/)   | Inbound email/message processing        | 🚧 Skeleton |
| [audit_orchestrator/](audit_orchestrator/)       | System auditing, compliance             | 🚧 Skeleton |
| [control_orchestrator/](control_orchestrator/)   | Campaign control, multi-channel seeding | 🚧 Skeleton |

## Shared Components

| File                   | Purpose                                 |
| ---------------------- | --------------------------------------- |
| `base_orchestrator.py` | Base class for all orchestrators        |
| `registry.py`          | Orchestrator registration and discovery |

## Communication Rules (CRITICAL)

### ✅ Allowed

```
Manager (Tier 1)
    │
    ▼
Orchestrator (Tier 2)  ←── You are here
    │
    ▼
Agents (Tier 3)
```

### ❌ FORBIDDEN

```
Leads Orchestrator  ←✕→  Outreach Orchestrator
         │                      │
         └──────── ✕ ───────────┘

   NO HORIZONTAL COMMUNICATION
```

Orchestrators **CANNOT** communicate with each other directly. All cross-orchestrator coordination must go through Manager (Tier 1).

### Stream Naming

```
Input:  {tenant}:orchestrators:{name}:tasks
Output: {tenant}:orchestrators:{name}:results
```

## Quick Start

```bash
# Run individual orchestrators
python -m tiers.tier_2.leads_orchestrator.consumer
python -m tiers.tier_2.outreach_orchestrator.consumer
```

## Architecture Pattern

Each orchestrator follows this pattern:

```
tiers/tier_2/{name}_orchestrator/
├── README.md                    # Documentation
├── {name}_orchestrator.py       # Core Deep Agent logic
├── {name}_orchestrator_harness.py  # Redis wrapper
├── consumer.py                  # Entry point
├── schemas/                     # Pydantic models
└── tests/                       # Unit tests
```

## Deep Agent Integration

All orchestrators use Deep Agents with middleware:

- **TodoListMiddleware** — Break goals into step-by-step tasks
- **FilesystemMiddleware** — Store large datasets to avoid token limits
- **SubAgentMiddleware** — Spawn specialized subagents

## See Also

- [Tier Architecture Overview](../README.md)
- [Orchestrator Isolation Verification](../../docs/ORCHESTRATOR_ISOLATION_VERIFICATION.md)
- [Base Orchestrator](base_orchestrator.py)
