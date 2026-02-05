# Channel Sequencer Agent

The Channel Sequencer Agent executes outbound delivery steps (currently email) and produces delivery results that downstream systems can persist and audit.

> Note
> The broader multi-channel sequencing roadmap (LinkedIn/phone, channel optimization) is still in progress. The current implementation focuses on MVP-safe outbound email execution with guardrails.

## Overview

| Property    | Value                                                     |
| ----------- | --------------------------------------------------------- |
| **Tier**    | 3 (Execution)                                             |
| **Stream**  | `{tenant}:agents:channel_sequencer:tasks`                 |
| **Outputs** | Delivery results + (on send) an outbound persistence task |
| **Path**    | `tiers/tier_3/channel_sequencer_agent/`                   |

## Responsibilities (Current)

- Execute outbound email steps.
- Enforce outbound safety guardrails (approval-mode drafts, hard-stop rules, and throttles).
- Emit delivery results that clearly indicate whether a step was sent, blocked, throttled, or drafted.
- Enqueue outbound persistence (conversation + message) to the Persistence Agent for audit/history.

## Outbound Safety

### Approval mode (draft-only)

When approval mode is enabled, the agent will not send. It returns a delivery marked as `draft` with reason `approval_required`.

- Env var: `OUTBOUND_APPROVAL_MODE`

### Hard-stop rules (never send)

The agent blocks sending when explicit “do not send” signals are present in request context/metadata.

Common hard-stop triggers:

- `do_not_contact`
- `unsubscribe` / `stop`
- `legal_threat`
- `abusive`
- `sensitive`
- `angry`
- A provided `hard_stop_reasons` list

Optionally, the agent can scan a snippet of the most recent inbound content for hard-stop keywords.

- Env var: `OUTBOUND_HARD_STOP_KEYWORDS`

### Throttling (rate limiting)

Throttling uses Redis counters and requires `REDIS_URL`.

- `OUTBOUND_MAX_PER_HOUR`: blocks with reason `throttle:hour_limit`
- `OUTBOUND_MAX_NEW_THREADS_PER_DAY`: blocks with reason `throttle:new_thread_limit` (applies when there is no existing thread/conversation id)

## Outbound Persistence

When an outbound email is successfully sent, the consumer enqueues a compound persistence payload to the Persistence Agent so the outbound message appears in:

- `conversations`
- `messages`

The payload includes message `metadata` with `correlation_id` (when available) so outbound writes can be traced back to the originating workflow.

## Delivery Statuses

Typical delivery statuses returned by the agent:

- `sent`: email was sent
- `draft`: approval mode prevented sending
- `blocked`: hard-stop rules prevented sending
- `throttled`: throttling limits prevented sending

## Related

- Persistence Agent: `components/tier-3/persistence.md`
- Environment variables: `reference/config/env-vars.md`
- Redis Streams: `concepts/redis-streams.md`
