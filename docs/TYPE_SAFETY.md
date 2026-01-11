# Type Safety Guide

This project relies on **typed task envelopes** + **Pydantic models** to keep Redis-stream messaging safe and debuggable.

## What to Validate

- **Inbound envelopes** (task id, tenant id, payload, metadata)
- **Agent/orchestrator payloads** (required fields, allowed enums, shape constraints)
- **Persistence writes** (FK requirements, non-null fields like `messages.metadata`)

## Where Types Live

- Core envelope + schemas: `core/envelope/` and `core/schemas/`
- Agent-specific input/output validators:
  - `tiers/tier_3/<agent_name>/validators.py`

## Recommended Pattern

1. Validate the full envelope at the boundary (consumer/harness).
2. Validate the payload again at the agent boundary (agent harness → agent core logic).
3. Fail fast with a structured error result (do not partially execute).

## See Also

- [API Reference](api/reference.md)
- [Incident Playbooks](INCIDENT_PLAYBOOKS.md)
