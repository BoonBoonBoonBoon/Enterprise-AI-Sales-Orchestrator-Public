# ADR-002: Vertical-Only Communication

**Status:** ✅ Accepted  
**Date:** October 2025

## Context

In a multi-tier system with multiple orchestrators, we needed to decide how components communicate:

1. **Horizontal:** Orchestrators can call each other directly
2. **Vertical:** Orchestrators only communicate up/down the hierarchy

Horizontal communication creates hidden dependencies, makes tracing difficult, and can lead to circular dependencies and deadlocks.

## Decision

We enforce **vertical-only communication** between tiers:

```
                    ┌─────────────┐
                    │   Manager   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │    Leads    │ │  Outreach   │ │   Inbound   │
    │Orchestrator │ │ Orchestrator│ │ Orchestrator│
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           ▼               ▼               ▼
    ┌─────────────────────────────────────────────┐
    │              Tier 3 Agents                  │
    └─────────────────────────────────────────────┘
```

### Rules

1. **Tier 2 → Tier 2:** ❌ FORBIDDEN
2. **Tier 2 → Tier 1:** ✅ Results only (upward)
3. **Tier 2 → Tier 3:** ✅ Tasks (downward)
4. **Tier 3 → Tier 3:** ❌ FORBIDDEN
5. **All cross-domain coordination:** Through Manager only

### Enforcement

```python
# Code guardrail in orchestrators
def assert_agents_stream(stream_key: str):
    """Raises error if publishing to non-agent stream."""
    if ":orchestrators:" in stream_key:
        raise ForbiddenStreamError(
            f"Horizontal communication forbidden: {stream_key}"
        )
```

## Consequences

### Positive

- **Traceable flows** — Every workflow has a single path through the system
- **No circular dependencies** — Impossible by design
- **Clear ownership** — Manager owns all cross-domain coordination
- **Simpler debugging** — Follow the vertical path
- **Easier testing** — Mock only up/down, never sideways

### Negative

- **Manager bottleneck** — All cross-orchestrator work flows through Manager
- **More messages** — Leads→Outreach requires: Leads→Manager→Outreach
- **Manager complexity** — Manager must understand all handoff patterns

### Neutral

- **Deep reply chaining** — Manager waits on Leads results, then enqueues to Outreach
- **Reply packets** — Orchestrators include `reply_packet` for Manager to forward

## Alternatives Considered

### Option A: Allow Horizontal Communication

Orchestrators can publish to each other's task streams.

- **Pros:** Lower latency, fewer hops
- **Cons:** Spaghetti dependencies, circular risks, hard to trace
- **Why rejected:** Debugging and maintenance nightmare at scale

### Option B: Event Bus with Subscriptions

Orchestrators subscribe to events they care about.

- **Pros:** Highly decoupled
- **Cons:** Implicit dependencies, hard to understand flow
- **Why rejected:** Too implicit, debugging requires event correlation

### Option C: Shared State Instead of Messages

Orchestrators read/write to shared database for coordination.

- **Pros:** Simple for small systems
- **Cons:** Race conditions, polling overhead, no clear workflow
- **Why rejected:** Doesn't scale, violates message-passing architecture

## Example: Lead Qualification → Outreach

**Correct flow:**

```
1. Manager receives "process new lead"
2. Manager → Leads Orchestrator: qualify lead
3. Leads Orchestrator → RAG Agent: get context
4. Leads Orchestrator → Persistence Agent: enrich
5. Leads Orchestrator → Manager: result with reply_packet
6. Manager → Outreach Orchestrator: execute campaign (with reply_packet)
7. Outreach Orchestrator → Copywriter Agent: generate email
8. Outreach Orchestrator → Manager: result
```

**Forbidden flow:**

```
❌ Leads Orchestrator → Outreach Orchestrator: execute campaign
```

## References

- [ADR-001: Three-Tier Architecture](001-three-tier-architecture.md)
- [Communication Rules](../communication.md)
