# Core Concepts

Understanding the foundational concepts of the Agentic System is essential before diving into implementation details. This section covers the key architectural patterns, communication mechanisms, and design principles that power the platform.

## Overview

The Agentic System is an enterprise-grade AI agent orchestration platform built on three core principles:

1. **Hierarchical Control** — A 3-tier architecture separating strategic decisions from business logic and task execution
2. **Vertical Communication** — Strict parent-child messaging patterns preventing horizontal coupling
3. **Tenant Isolation** — Complete separation of data and workflows per customer

## Concepts

<div class="grid cards" markdown>

- :material-layers-triple:{ .lg .middle } **Three-Tier Architecture**

  ***

  Understand the Manager → Orchestrator → Agent hierarchy that structures all workflows.

  [:octicons-arrow-right-24: Learn more](three-tier-architecture.md)

- :material-email-fast:{ .lg .middle } **Message Envelope**

  ***

  The standardized JSON structure for all inter-agent communication.

  [:octicons-arrow-right-24: Learn more](envelope.md)

- :material-database-arrow-right:{ .lg .middle } **Redis Streams**

  ***

  How Redis Streams enable reliable, ordered, multi-consumer message delivery.

  [:octicons-arrow-right-24: Learn more](redis-streams.md)

- :material-shield-half-full:{ .lg .middle } **Agent Harness**

  ***

  The wrapper pattern providing retries, circuit breakers, and observability to all agents.

  [:octicons-arrow-right-24: Learn more](agent-harness.md)

- :material-account-group:{ .lg .middle } **Multi-Tenancy**

  ***

  How tenant isolation is enforced at the stream, database, and application layers.

  [:octicons-arrow-right-24: Learn more](multi-tenancy.md)

</div>

## Reading Order

If you're new to the system, we recommend reading these concepts in order:

1. [Three-Tier Architecture](three-tier-architecture.md) — Start here
2. [Message Envelope](envelope.md) — How agents communicate
3. [Redis Streams](redis-streams.md) — The transport layer
4. [Agent Harness](agent-harness.md) — Reliability patterns
5. [Multi-Tenancy](multi-tenancy.md) — Isolation guarantees

## Quick Reference

| Concept        | One-Liner                                          |
| -------------- | -------------------------------------------------- |
| **Tier 1**     | Strategic layer — Manager Agent routes goals       |
| **Tier 2**     | Business logic — Orchestrators decompose workflows |
| **Tier 3**     | Execution — Agents perform atomic tasks            |
| **Envelope**   | `{task_id, tenant_id, payload, metadata}`          |
| **Stream Key** | `{tenant}:{tier}:{component}:tasks\|results`       |
| **Harness**    | Wraps agents with retries + circuit breaker        |
