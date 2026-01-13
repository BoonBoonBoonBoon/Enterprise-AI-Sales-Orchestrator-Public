# Architecture Decision Records

We document significant architectural decisions using ADRs (Architecture Decision Records). Each record captures the context, decision, and consequences of important technical choices.

## What is an ADR?

An Architecture Decision Record is a short document that describes:

1. **Context** — The situation and forces at play
2. **Decision** — What we decided to do
3. **Consequences** — The results of the decision (good and bad)

## ADR Index

| ID                                            | Title                             | Status      | Date     |
| --------------------------------------------- | --------------------------------- | ----------- | -------- |
| [ADR-001](001-three-tier-architecture.md)     | Three-Tier Architecture           | ✅ Accepted | Oct 2025 |
| [ADR-002](002-vertical-only-communication.md) | Vertical-Only Communication       | ✅ Accepted | Oct 2025 |
| [ADR-003](003-redis-streams-over-queues.md)   | Redis Streams over Message Queues | ✅ Accepted | Oct 2025 |
| [ADR-004](004-supabase-rls-3-layer-auth.md)   | Supabase RLS 3-Layer Auth         | ✅ Accepted | Nov 2025 |
| [ADR-005](005-agent-harness-pattern.md)       | Agent Harness Pattern             | ✅ Accepted | Nov 2025 |
| [ADR-006](006-langgraph-deep-agents.md)       | LangGraph for Deep Agents         | ✅ Accepted | Dec 2025 |

## ADR Status Definitions

| Status        | Meaning                 |
| ------------- | ----------------------- |
| ✅ Accepted   | Decision is in effect   |
| 🔄 Superseded | Replaced by a newer ADR |
| ❌ Deprecated | No longer applicable    |
| 📋 Proposed   | Under discussion        |

## ADR Template

When creating a new ADR, use this template:

```markdown
# ADR-XXX: Title

**Status:** Proposed | Accepted | Deprecated | Superseded  
**Date:** YYYY-MM-DD  
**Superseded by:** ADR-YYY (if applicable)

## Context

What is the issue that we're seeing that is motivating this decision or change?

## Decision

What is the change that we're proposing and/or doing?

## Consequences

What becomes easier or more difficult to do because of this change?

### Positive

- Benefit 1
- Benefit 2

### Negative

- Tradeoff 1
- Tradeoff 2

### Neutral

- Side effect 1

## Alternatives Considered

What other options were considered and why were they rejected?

### Option A: [Name]

- Pros: ...
- Cons: ...
- Why rejected: ...

## References

- Link to relevant documentation
- Link to discussion/issue
```

## Creating a New ADR

1. Copy the template above
2. Number sequentially (ADR-007, ADR-008, etc.)
3. Fill in all sections
4. Submit PR for review
5. Update this index when accepted
