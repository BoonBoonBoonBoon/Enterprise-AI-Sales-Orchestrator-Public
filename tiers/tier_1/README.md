# Tier 1 - Strategic Layer

**Role:** Decision-Making & Routing

## Purpose

Tier 1 is the strategic brain of the system. It contains the **Manager Agent** which:

- Receives high-level goals from users, APIs, or external systems
- Analyzes intent and determines the appropriate course of action
- Routes work to Tier 2 orchestrators
- **Never performs execution work** — only decides _what_ to do and _when_

## Components

| Component            | Description                                      |
| -------------------- | ------------------------------------------------ |
| [manager/](manager/) | The Manager Agent: routes goals to orchestrators |

## Communication

```
External (APIs, Users, Events)
           │
           ▼
    ┌──────────────┐
    │   MANAGER    │  ← Tier 1
    └──────┬───────┘
           │
           ▼
    Tier 2 Orchestrators
```

### Streams

- **Input:** `{tenant}:manager:tasks`
- **Output:** `{tenant}:orchestrators:{name}:tasks` (delegation)
- **Results:** `{tenant}:manager:results`

## Key Principles

1. **Decision ONLY** — Manager never generates content, emails, or performs database writes
2. **Delegation** — All work is delegated to Tier 2 orchestrators
3. **Fast Path** — Simple operations use shortcuts (<50ms) without delegation
4. **Stateless** — No instance-specific state; scales horizontally

## Quick Start

```bash
python -m tiers.tier_1.manager.consumer
```

## See Also

- [Manager Agent README](manager/README.md)
- [Three-Tier Architecture](../../docs/architecture/three-tier-system.md)
