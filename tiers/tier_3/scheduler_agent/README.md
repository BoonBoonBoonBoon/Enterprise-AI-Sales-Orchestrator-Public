# Scheduler Agent

**Tier:** 3 (Execution) | **Type:** Meeting Scheduling Agent | **Status:** 🚧 Skeleton

## Purpose

The Scheduler Agent books meetings on external calendars for engaged prospects:

- **Calendar integration** — Google Calendar, Outlook, iCal
- **Availability checking** — Find open time slots
- **Meeting creation** — Book with proper invites
- **Conflict handling** — Manage cancellations and reschedules

## Architecture

```
Outreach Orchestrator (Tier 2)
    │
    ▼ {tenant}:agents:booking:tasks
┌──────────────────────────────────────┐
│       SCHEDULER AGENT (Tier 3)       │
│                                      │
│  • Calendar provider integration     │
│  • Availability computation          │
│  • Meeting lifecycle management      │
└───────────────┬──────────────────────┘
                │
                ▼ {tenant}:agents:booking:results
    Outreach Orchestrator (Tier 2)
```

## Key Components

| File                         | Purpose                                 |
| ---------------------------- | --------------------------------------- |
| `scheduler_agent.py`         | Core logic: calendar API calls, booking |
| `scheduler_agent_harness.py` | Redis wrapper: stream consumption       |
| `consumer.py`                | Entry point: runs the harness loop      |
| `validators.py`              | Pydantic request/result models          |
| `worker.py`                  | Synchronous wrapper for direct calls    |

## Quick Start

```bash
# Run the Scheduler Agent consumer
python -m tiers.tier_3.scheduler_agent.consumer
```

## Task Format

```json
{
  "lead_id": "lead-456",
  "meeting_type": "discovery",
  "duration_minutes": 30,
  "preferred_times": [
    "2024-01-18T10:00:00Z",
    "2024-01-18T14:00:00Z",
    "2024-01-19T10:00:00Z"
  ],
  "attendees": ["rep@company.com", "lead@acme.com"],
  "calendar_provider": "google"
}
```

## Response Format

```json
{
  "status": "success",
  "booking": {
    "meeting_id": "mtg-789",
    "scheduled_time": "2024-01-18T10:00:00Z",
    "duration_minutes": 30,
    "calendar_link": "https://calendar.google.com/...",
    "invite_sent": true
  }
}
```

## Supported Providers

| Provider          | Status     | Notes              |
| ----------------- | ---------- | ------------------ |
| Google Calendar   | 🚧 Planned | OAuth2 integration |
| Microsoft Outlook | 🚧 Planned | Graph API          |
| iCal              | 🚧 Planned | Generic ICS format |

## Roadmap

1. **Integrate provider SDKs** — Google, Outlook OAuth
2. **Per-tenant token storage** — Secure credential management
3. **Persist bookings** — Store meeting records with correlation IDs
4. **Handle conflicts** — Cancellations, reschedules, retries

## Database Access

**None** — Meeting context comes from orchestrator. Booking confirmations return via result stream.

## See Also

- [Tier 3 Overview](../README.md)
- [Outreach Orchestrator](../../tier_2/outreach_orchestrator/README.md)
