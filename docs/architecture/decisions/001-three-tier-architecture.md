# ADR-001: Three-Tier Architecture

**Status:** ✅ Accepted  
**Date:** October 2025

## Context

We needed to design an AI agent orchestration system that could:

1. Handle complex multi-step workflows
2. Scale individual components independently
3. Maintain clear separation of concerns
4. Support multiple tenants with isolation
5. Allow easy addition of new agents and workflows

Flat architectures with peer-to-peer agent communication create complexity as the number of agents grows (O(n²) connections). Monolithic designs limit scalability and deployability.

## Decision

We adopt a **three-tier hierarchical architecture**:

```
┌─────────────────────────────────────────────┐
│  TIER 1: Strategic Layer (Manager)          │
│  - Single entry point                       │
│  - Intent classification                    │
│  - Policy-based routing                     │
└─────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  TIER 2: Business Logic Layer (Orchestrators)│
│  - Domain-specific workflow decomposition   │
│  - State management for complex flows       │
│  - Coordinates multiple agent calls         │
└─────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  TIER 3: Execution Layer (Agents)           │
│  - Atomic, stateless tasks                  │
│  - Single responsibility                    │
│  - Fast, focused execution                  │
└─────────────────────────────────────────────┘
```

### Tier Responsibilities

| Tier | Role           | Components    | Communication                             |
| ---- | -------------- | ------------- | ----------------------------------------- |
| 1    | Strategic      | Manager Agent | Receives goals, delegates to Tier 2       |
| 2    | Business Logic | Orchestrators | Decomposes workflows, delegates to Tier 3 |
| 3    | Execution      | Agents        | Performs atomic tasks, returns results    |

## Consequences

### Positive

- **Clear separation of concerns** — Each tier has distinct responsibilities
- **Scalability** — Scale Tier 3 agents independently based on load
- **Maintainability** — Changes to business logic don't affect execution layer
- **Testability** — Each tier can be tested in isolation
- **Debuggability** — Clear flow makes tracing easier
- **Onboarding** — New developers understand the system quickly

### Negative

- **Latency** — Multiple hops add latency vs. direct execution
- **Complexity** — More moving parts than a flat architecture
- **Overhead** — Message passing between tiers has cost

### Neutral

- **Deployment** — Each tier can be deployed independently (micro-service pattern)
- **Monitoring** — Need observability at each tier boundary

## Alternatives Considered

### Option A: Flat Peer-to-Peer Architecture

All agents communicate directly with each other.

- **Pros:** Lower latency, simpler for small systems
- **Cons:** O(n²) complexity, hard to reason about, no clear entry point
- **Why rejected:** Doesn't scale, violates separation of concerns

### Option B: Two-Tier (Manager + Agents)

No orchestrator layer; Manager calls agents directly.

- **Pros:** Fewer hops, simpler
- **Cons:** Manager becomes a god object, complex workflow logic in one place
- **Why rejected:** Manager would be too complex, hard to maintain

### Option C: Event-Driven Saga Pattern

Agents react to events without central coordination.

- **Pros:** Highly decoupled, resilient
- **Cons:** Hard to trace flows, compensating transactions complex
- **Why rejected:** Too complex for our use case, debugging nightmare

## References

- [Martin Fowler: Presentation Domain Data Layering](https://martinfowler.com/bliki/PresentationDomainDataLayering.html)
- [Microsoft: N-tier architecture style](https://docs.microsoft.com/en-us/azure/architecture/guide/architecture-styles/n-tier)
