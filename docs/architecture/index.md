# Architecture

In-depth documentation of the Agentic System's architecture, design principles, and key decisions.

## Overview

The Agentic System is an enterprise-grade AI agent orchestration platform designed for reliability, scalability, and maintainability. It employs a strict three-tier hierarchy with vertical-only communication patterns.

## Core Documents

<div class="grid cards" markdown>

- :material-sitemap:{ .lg .middle } **System Design**

  ***

  High-level architecture, component relationships, and design philosophy.

  [:octicons-arrow-right-24: System Design](design.md)

- :material-swap-horizontal:{ .lg .middle } **Data Flow**

  ***

  How data moves through the system from input to output.

  [:octicons-arrow-right-24: Data Flow](data-flow.md)

- :material-arrow-up-down:{ .lg .middle } **Communication Rules**

  ***

  The vertical-only communication pattern and its enforcement.

  [:octicons-arrow-right-24: Communication Rules](communication.md)

- :material-shield-lock:{ .lg .middle } **Security Model**

  ***

  Authentication, authorization, and data protection mechanisms.

  [:octicons-arrow-right-24: Security Model](security.md)

</div>

## Architecture Decision Records (ADRs)

We document significant architectural decisions using ADRs. Each record captures the context, decision, and consequences.

| ADR                                                     | Title                             | Status      |
| ------------------------------------------------------- | --------------------------------- | ----------- |
| [ADR-001](decisions/001-three-tier-architecture.md)     | Three-Tier Architecture           | ✅ Accepted |
| [ADR-002](decisions/002-vertical-only-communication.md) | Vertical-Only Communication       | ✅ Accepted |
| [ADR-003](decisions/003-redis-streams-over-queues.md)   | Redis Streams over Message Queues | ✅ Accepted |
| [ADR-004](decisions/004-supabase-rls-3-layer-auth.md)   | Supabase RLS 3-Layer Auth         | ✅ Accepted |
| [ADR-005](decisions/005-agent-harness-pattern.md)       | Agent Harness Pattern             | ✅ Accepted |
| [ADR-006](decisions/006-langgraph-deep-agents.md)       | LangGraph for Deep Agents         | ✅ Accepted |

See [ADR Index](decisions/index.md) for the complete list and ADR template.

## Key Principles

### 1. Hierarchical Control

```
Tier 1 (Strategic)     → Manager routes goals
Tier 2 (Business Logic) → Orchestrators decompose workflows
Tier 3 (Execution)      → Agents perform atomic tasks
```

### 2. Vertical Communication Only

Orchestrators never communicate horizontally. All cross-domain coordination flows through the Manager.

### 3. Single Responsibility

Each component has one job. Agents don't orchestrate. Orchestrators don't execute. Manager doesn't generate content.

### 4. Tenant Isolation

Every stream, database query, and workflow is scoped to a tenant via `{tenant_id}` prefix.

### 5. Resilience by Default

The Agent Harness provides retries, circuit breakers, and checkpointing out of the box.

## Visual Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL INTERFACE                          │
│                  (API Gateway / Webhooks)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 1                 MANAGER                                 │
│              ┌──────────────────────────────┐                   │
│              │     Intent → Policy → Route   │                   │
│              └──────────────────────────────┘                   │
└─────────────────────────┬───────────────────────────────────────┘
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 2           ORCHESTRATORS                                 │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐                    │
│   │  Leads  │    │Outreach │    │ Inbound │                    │
│   └────┬────┘    └────┬────┘    └────┬────┘                    │
└────────┼──────────────┼──────────────┼──────────────────────────┘
         └──────────────┴──────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 3              AGENTS                                     │
│   ┌─────┐    ┌───────────┐    ┌──────────┐                     │
│   │ RAG │    │Persistence│    │Copywriter│                     │
│   └─────┘    └───────────┘    └──────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────────────┐
│  SERVICES    Redis │ Supabase │ Vector DB │ Email              │
└─────────────────────────────────────────────────────────────────┘
```

## Related Documentation

- [Concepts](../concepts/index.md) — Core concepts explained
- [Components](../components/index.md) — Component documentation
- [Reference](../reference/index.md) — API and configuration reference
