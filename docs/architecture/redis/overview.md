# Redis Architecture Overview

**Status:** Active  
**Last Updated:** January 2026

This document provides a comprehensive overview of Redis usage in the Agentic System.

## Table of Contents

1. [Purpose](#purpose)
2. [Stream Naming Convention](#stream-naming-convention)
3. [Three-Tier Data Flow](#three-tier-data-flow)
4. [Stream Inventory](#stream-inventory)
5. [Consumer Groups](#consumer-groups)

---

## Purpose

Redis Streams serve as the primary communication backbone for the three-tier agent architecture:

- **Asynchronous task delegation** between tiers
- **Result propagation** back to callers
- **Multi-tenant isolation** via tenant-prefixed streams
- **Reliable delivery** via consumer groups with acknowledgment

---

## Stream Naming Convention

### Pattern

```
{tenant_id}:{tier}:{component}:{stream_type}
```

### Components

| Component     | Description                 | Examples                             |
| ------------- | --------------------------- | ------------------------------------ |
| `tenant_id`   | Tenant identifier           | `agentic-dev`, `acme`, `prod`        |
| `tier`        | Architecture tier           | `manager`, `orchestrators`, `agents` |
| `component`   | Specific agent/orchestrator | `leads`, `rag`, `copywriter`         |
| `stream_type` | Stream purpose              | `tasks`, `results`                   |

### By Tier

| Tier              | Pattern                                | Example                                 |
| ----------------- | -------------------------------------- | --------------------------------------- |
| **Manager**       | `{tenant}:manager:{type}`              | `agentic-dev:manager:tasks`             |
| **Orchestrators** | `{tenant}:orchestrators:{name}:{type}` | `agentic-dev:orchestrators:leads:tasks` |
| **Agents**        | `{tenant}:agents:{name}:{type}`        | `agentic-dev:agents:rag:tasks`          |

---

## Three-Tier Data Flow

### Downstream (Delegation)

```
User/API Request
       │
       ▼
┌─────────────────────────────────────────┐
│ {tenant}:manager:tasks                  │
│                                         │
│            MANAGER (Tier 1)             │
│  Analyzes → Routes → Delegates          │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
┌───────────────────┐ ┌───────────────────┐
│orchestrators:leads│ │orchestrators:out- │
│:tasks             │ │reach:tasks        │
│                   │ │                   │
│ ORCHESTRATOR T2   │ │ ORCHESTRATOR T2   │
└────────┬──────────┘ └────────┬──────────┘
         │                     │
    ┌────┴────┐           ┌────┴────┐
    ▼         ▼           ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│agents: │ │agents: │ │agents: │ │agents: │
│rag:   │ │persist-│ │copy-   │ │booking:│
│tasks  │ │ence:   │ │writer: │ │tasks   │
│       │ │tasks   │ │tasks   │ │        │
│ T3    │ │ T3     │ │ T3     │ │ T3     │
└────────┘ └────────┘ └────────┘ └────────┘
```

### Upstream (Results)

```
Agent completes task
       │
       ▼
{tenant}:agents:{name}:results
       │
       ▼
Orchestrator reads result
       │
       ▼
{tenant}:orchestrators:{name}:results
       │
       ▼
Manager reads result (if needed)
       │
       ▼
{tenant}:manager:results
       │
       ▼
User/API Response
```

---

## Stream Inventory

### Tier 1 - Manager

| Stream                     | Purpose                        |
| -------------------------- | ------------------------------ |
| `{tenant}:manager:tasks`   | Incoming goals from users/APIs |
| `{tenant}:manager:results` | Final aggregated results       |

### Tier 2 - Orchestrators

| Stream                                    | Purpose                        |
| ----------------------------------------- | ------------------------------ |
| `{tenant}:orchestrators:leads:tasks`      | Lead operations requests       |
| `{tenant}:orchestrators:leads:results`    | Lead operation results         |
| `{tenant}:orchestrators:outreach:tasks`   | Campaign coordination requests |
| `{tenant}:orchestrators:outreach:results` | Campaign coordination results  |
| `{tenant}:orchestrators:inbound:tasks`    | Inbound message processing     |
| `{tenant}:orchestrators:inbound:results`  | Inbound processing results     |
| `{tenant}:orchestrators:audit:tasks`      | Audit requests                 |
| `{tenant}:orchestrators:audit:results`    | Audit results                  |

### Tier 3 - Agents

| Stream                                | Purpose                  |
| ------------------------------------- | ------------------------ |
| `{tenant}:agents:rag:tasks`           | RAG/enrichment requests  |
| `{tenant}:agents:rag:results`         | Enriched data            |
| `{tenant}:agents:persistence:tasks`   | Database operations      |
| `{tenant}:agents:persistence:results` | Operation confirmations  |
| `{tenant}:agents:copywriter:tasks`    | Copy generation requests |
| `{tenant}:agents:copywriter:results`  | Generated copy           |
| `{tenant}:agents:booking:tasks`       | Meeting scheduling       |
| `{tenant}:agents:booking:results`     | Booking confirmations    |
| `{tenant}:agents:sequencing:tasks`    | Sequence optimization    |
| `{tenant}:agents:sequencing:results`  | Optimized sequences      |

---

## Consumer Groups

Each consumer uses a consumer group for reliable delivery:

```python
# Consumer reads with group
redis.xreadgroup(
    groupname="rag-agent-group",
    consumername="rag-consumer-1",
    streams={"agentic-dev:agents:rag:tasks": ">"},
    count=10,
    block=5000
)

# Acknowledge after processing
redis.xack(
    "agentic-dev:agents:rag:tasks",
    "rag-agent-group",
    message_id
)
```

### Group Naming

```
{component}-group      # e.g., rag-agent-group, leads-orchestrator-group
```

---

## See Also

- [Implementation Guide](implementation.md)
- [Operations & Monitoring](operations.md)
- [Core Streams Module](https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/core/streams.py)
