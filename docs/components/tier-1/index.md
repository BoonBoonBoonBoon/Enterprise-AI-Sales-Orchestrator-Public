# Tier 1 - Manager

The strategic layer of the Agentic System. Tier 1 contains a single component — the **Manager Agent** — which serves as the unified entry point for all external goals and coordinates their execution across the system.

## Role in the Architecture

```
                    External Systems / API
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TIER 1 - MANAGER                            │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                   Manager Agent                          │  │
│   │                                                          │  │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │  │
│   │  │  Intake  │→ │  Intent  │→ │  Policy  │→ │  Tools  │ │  │
│   │  │          │  │ Classify │  │  Router  │  │Delegate │ │  │
│   │  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │  │
│   └─────────────────────────────────────────────────────────┘  │
│                            │                                    │
└────────────────────────────┼────────────────────────────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    ┌────────────┐    ┌────────────┐    ┌────────────┐
    │   Leads    │    │  Outreach  │    │  Inbound   │
    │Orchestrator│    │Orchestrator│    │Orchestrator│
    └────────────┘    └────────────┘    └────────────┘
         TIER 2            TIER 2            TIER 2
```

## Responsibilities

The Manager Agent has **four key responsibilities**:

### 1. Intent Classification

Determine what the incoming message/goal is asking for:

- New lead ingestion
- Campaign execution
- Reply handling
- Information retrieval
- System control

### 2. Policy-Based Routing

Apply business rules to decide which orchestrator(s) should handle the goal:

- Single orchestrator delegation
- Multi-orchestrator fan-out (sequential)
- Direct agent calls (shortcuts)

### 3. Delegation

Create properly formatted task envelopes and publish to the correct orchestrator streams.

### 4. Result Aggregation

Collect results from delegated tasks and compile final responses.

## Critical Rule

!!! danger "Manager Never Generates Content"
The Manager **decides** and **delegates** — it never generates email bodies, subject lines, or any user-facing content. All content generation is delegated to the Copywriter Agent via Tier 2 orchestrators.

## Components

| Component                      | Path                                    | Purpose                  |
| ------------------------------ | --------------------------------------- | ------------------------ |
| [Manager Agent](manager.md)    | `tiers/tier_1/manager/`                 | Main orchestration logic |
| [Policy Router](router.md)     | `tiers/tier_1/manager/policy/router.py` | Stream routing rules     |
| [Intent Classifier](intent.md) | `tiers/tier_1/manager/intent/`          | Goal classification      |

## Stream Interface

**Input:**

```
{tenant}:manager:tasks
```

**Output:**

```
{tenant}:manager:results
```

**Delegates to:**

```
{tenant}:orchestrators:{name}:tasks
```

## Quick Start

```powershell
# Start the Manager consumer
& ".venv/Scripts/python.exe" -m tiers.tier_1.manager.consumer
```

See [Running Consumers](../../guides/ops/consumers.md) for production deployment.
