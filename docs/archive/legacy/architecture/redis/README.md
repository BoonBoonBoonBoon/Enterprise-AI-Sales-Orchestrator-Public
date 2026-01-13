# Redis Documentation

This directory contains consolidated Redis Streams documentation for the Agentic System.

## Contents

| Document                               | Purpose                                        |
| -------------------------------------- | ---------------------------------------------- |
| [overview.md](overview.md)             | Architecture, naming conventions, data flow    |
| [implementation.md](implementation.md) | Code examples, envelope format, best practices |
| [operations.md](operations.md)         | Monitoring, troubleshooting, scaling           |

## Quick Reference

### Stream Naming Pattern

```
{tenant_id}:{tier}:{component}:{stream_type}
```

### Example Streams

```
agentic-dev:manager:tasks              # Manager input
agentic-dev:orchestrators:leads:tasks  # Leads orchestrator input
agentic-dev:agents:rag:tasks           # RAG agent input
```

### Key Rules

1. **Vertical communication only** — No orchestrator-to-orchestrator streams
2. **Always use tenant prefix** — Multi-tenancy is mandatory
3. **Use consumer groups** — For reliable message delivery
4. **Acknowledge after processing** — Not before

## Migration Note

This directory consolidates previously scattered Redis documentation:

- `services/REDIS_ARCHITECTURE.md` → `overview.md`
- `services/redis-*.md` → merged into these 3 docs
- Various Redis docs → archived to `docs/archive/`
