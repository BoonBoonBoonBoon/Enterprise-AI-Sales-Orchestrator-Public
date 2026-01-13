# Orchestrator Horizontal Isolation (Tier 2) — Verification

## Requirement
Tier 2 orchestrators **must not communicate with each other** (no horizontal comms). They may only communicate:
- **Upward** to Tier 1 Manager via `{tenant}:orchestrators:{name}:results`
- **Downward** to Tier 3 agents via `{tenant}:agents:{agent_name}:tasks`

## What enforces this
### 1) Stream naming convention
- **Manager**: `{tenant}:manager:tasks` → `{tenant}:manager:results`
- **Orchestrators**: `{tenant}:orchestrators:{orchestrator_name}:tasks` → `{tenant}:orchestrators:{orchestrator_name}:results`
- **Agents**: `{tenant}:agents:{agent_name}:tasks` → `{tenant}:agents:{agent_name}:results`

### 2) Code guardrail for Tier 2 publishes
Tier 2 orchestrators must call a guard before publishing to Redis:
- Guard: `core.streams.assert_agents_stream(stream_name)`
- Rule: Tier 2 may only publish to streams containing `:agents:`.
- Any attempt to publish to manager or other orchestrator streams is rejected.

## Verification checklist
- Search Tier 2 for any publish to `:orchestrators:` other than its own `...:results`
- Ensure every Tier 2 `xadd` to agent task streams is preceded by `assert_agents_stream(...)`
- Confirm Tier 2 does not import or instantiate other orchestrators

## Notes
This verification is also documented in the Copilot manual: see `.github/copilot-instructions.md` under **Communication Rules (CRITICAL)** and **Enforcement**.
