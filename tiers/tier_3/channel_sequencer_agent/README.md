# Channel Sequencer Agent

**Tier:** 3 (Execution) | **Type:** Sequence Optimization Agent | **Status:** 🚧 Skeleton

## Purpose

The Channel Sequencer Agent optimizes multi-channel outreach sequences using rules and ML:

- **Channel selection** — Determine optimal channel order (email → LinkedIn → phone)
- **Timing optimization** — Calculate ideal touchpoint delays
- **A/B testing** — Support sequence variant testing
- **Rate limiting** — Respect per-channel throttling rules

## Architecture

```
Outreach Orchestrator (Tier 2)
    │
    ▼ {tenant}:agents:sequencing:tasks
┌──────────────────────────────────────┐
│    CHANNEL SEQUENCER AGENT (Tier 3)  │
│                                      │
│  • Rule-based sequence selection     │
│  • ML-optimized timing (future)      │
│  • Channel eligibility checks        │
└───────────────┬──────────────────────┘
                │
                ▼ {tenant}:agents:sequencing:results
    Outreach Orchestrator (Tier 2)
```

## Key Components

| File                                 | Purpose                                  |
| ------------------------------------ | ---------------------------------------- |
| `channel_sequencer_agent.py`         | Core logic: sequence rules, optimization |
| `channel_sequencer_agent_harness.py` | Redis wrapper: stream consumption        |
| `consumer.py`                        | Entry point: runs the harness loop       |
| `validators.py`                      | Pydantic request/result models           |
| `worker.py`                          | Synchronous wrapper for direct calls     |

## Quick Start

```bash
# Run the Channel Sequencer Agent consumer
python -m tiers.tier_3.channel_sequencer_agent.consumer
```

## Task Format

```json
{
  "campaign_id": "camp-123",
  "current_sequence": [
    { "channel": "email", "delay_days": 0 },
    { "channel": "linkedin", "delay_days": 3 }
  ],
  "current_performance": {
    "email_open_rate": 0.45,
    "linkedin_engagement_rate": 0.2
  },
  "optimization_goal": "maximize_bookings"
}
```

## Response Format

```json
{
  "status": "success",
  "optimized_sequence": [
    { "channel": "email", "delay_days": 0 },
    { "channel": "linkedin", "delay_days": 2 },
    { "channel": "phone", "delay_days": 5 }
  ],
  "rationale": "Shortened LinkedIn delay based on high email open rate",
  "confidence": 0.85
}
```

## Supported Channels

| Channel  | Status     | Notes                     |
| -------- | ---------- | ------------------------- |
| Email    | ✅ Active  | Primary touchpoint        |
| LinkedIn | ✅ Active  | Social engagement         |
| Phone    | ✅ Active  | High-touch for warm leads |
| SMS      | 🚧 Planned | Short notifications       |
| WhatsApp | 🚧 Planned | International outreach    |

## Roadmap

1. **Plug in channel eligibility rules** — Rate limits, throttling
2. **Resolve sender identities** — Per-channel sender selection
3. **Template selection** — Channel-appropriate content
4. **ML optimization** — Learning from campaign performance

## Database Access

**None** — Receives all context via task payload from orchestrator.

## See Also

- [Tier 3 Overview](../README.md)
- [Outreach Orchestrator](../../tier_2/outreach_orchestrator/README.md)
