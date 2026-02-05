# Core Utilities

This section documents the core utility modules that provide cross-cutting functionality for the Agentic System.

## Intent Enum

**Module:** `core/intent.py`

Provides a canonical `Intent` enum to replace hardcoded intent strings throughout the codebase.

### Usage

```python
from core.intent import Intent, ROUTING_INTENTS

# Type-safe intent values
intent = Intent.INBOUND

# Parse from string (case-insensitive)
intent = Intent.from_string("inbound")  # Returns Intent.INBOUND
intent = Intent.from_string("unknown_value")  # Returns Intent.UNKNOWN

# Validate intent strings
Intent.is_valid("inbound")  # True
Intent.is_valid("not_real")  # False

# Works with string comparisons
if intent == "inbound":
    handle_inbound()

# Check intent categories
if intent in ROUTING_INTENTS:
    route_to_orchestrator()
```

### Available Intents

| Intent            | Value               | Description                       |
| ----------------- | ------------------- | --------------------------------- |
| `INBOUND`         | `"inbound"`         | Inbound email received            |
| `OUTREACH`        | `"outreach"`        | Outreach campaign request         |
| `LEAD_ENRICHMENT` | `"lead_enrichment"` | Lead enrichment/discovery         |
| `START_CAMPAIGN`  | `"start_campaign"`  | Start a campaign                  |
| `REPLY_EMAIL`     | `"reply_email"`     | Generate reply email              |
| `QUALIFY_LEAD`    | `"qualify_lead"`    | Qualify/score a lead              |
| `UNKNOWN`         | `"unknown"`         | Fallback for unrecognized intents |

---

## Dead Letter Queue (DLQ)

**Module:** `core/dlq.py`

Provides DLQ support for messages that fail after exhausting retries.

### Configuration

| Environment Variable | Default | Description                   |
| -------------------- | ------- | ----------------------------- |
| `DLQ_ENABLED`        | `1`     | Enable/disable DLQ            |
| `DLQ_MAX_RETRIES`    | `3`     | Retries before sending to DLQ |
| `DLQ_STREAM_SUFFIX`  | `:dlq`  | Suffix for DLQ stream names   |

### Usage

```python
from core.dlq import DeadLetterQueue

# Create DLQ for a stream
dlq = DeadLetterQueue(
    redis_client=redis,
    source_stream="agentic-dev:agents:rag:tasks",
    max_retries=3,
)

# Check if message should go to DLQ
if dlq.should_dlq(failure_count=3):
    dlq.send_to_dlq(
        message=original_message,
        message_id="12345-0",
        error=exception,
        failure_reason="max_retries_exceeded",
    )

# Inspect DLQ
messages = dlq.peek_dlq(count=10)
dlq_length = dlq.get_dlq_length()

# Requeue a DLQ message for retry
dlq.requeue_message("dlq-msg-id")
```

### Stream Naming

DLQ streams follow the pattern: `{original_stream}:dlq`

Example:

- Source: `agentic-dev:agents:rag:tasks`
- DLQ: `agentic-dev:agents:rag:tasks:dlq`

---

## Graceful Shutdown

**Module:** `core/shutdown.py`

Provides signal handling for clean consumer shutdown.

### Usage

```python
from core.shutdown import ShutdownHandler

# Create handler
handler = ShutdownHandler(
    name="MyConsumer",
    shutdown_timeout=30.0,
)

# Register signal handlers (call from main thread)
handler.register_signals()

# Main loop
while not handler.should_stop:
    with handler.processing_context("task-123"):
        # Process task - shutdown will wait for this to complete
        process_task(...)
```

### Features

- Catches `SIGTERM` and `SIGINT` signals
- Waits for in-flight tasks to complete (with timeout)
- Thread-safe stop flag
- Configurable shutdown timeout

---

## Token Utilities

**Module:** `core/tokens.py`

Provides token counting and context window management utilities.

### Configuration

| Environment Variable | Default | Description                 |
| -------------------- | ------- | --------------------------- |
| `MAX_CONTEXT_TOKENS` | `8000`  | Default context window size |
| `CHARS_PER_TOKEN`    | `4.0`   | Character-to-token ratio    |

### Usage

```python
from core.tokens import (
    estimate_tokens,
    truncate_messages_by_tokens,
    TokenBudget,
)

# Estimate token count
tokens = estimate_tokens("Hello, world!")  # ~4

# Truncate messages to fit budget (preserves recent)
messages = [...]
truncated = truncate_messages_by_tokens(
    messages,
    max_tokens=4000,
    preserve_recent=True,  # Keep newest messages
)

# Track token budget while building context
budget = TokenBudget(max_tokens=8000)
budget.add("system_prompt", system_prompt)
budget.add("lead_info", lead_data)

# Use remaining budget for messages
remaining = budget.remaining
messages = truncate_messages_by_tokens(messages, max_tokens=remaining)
budget.add("messages", messages)

print(f"Total: {budget.total}, Remaining: {budget.remaining}")
```

### RAG Context Limiting

The `build_reply_context` function now supports `max_tokens` parameter:

```python
from tiers.tier_3.rag_agent.strategies.reply_context import build_reply_context

context = build_reply_context(
    adapter,
    email="lead@example.com",
    max_messages=20,
    max_tokens=4000,  # NEW: Limit context window
)
```

---

## Email Dry-Run Mode

**Module:** `services/email/gmail_sender.py`

### Configuration

| Environment Variable | Default | Description                               |
| -------------------- | ------- | ----------------------------------------- |
| `EMAIL_DRY_RUN`      | `0`     | Enable dry-run mode (log instead of send) |

When enabled, emails are logged but not actually sent:

```
[DRY_RUN] Would send email: to=lead@example.com, subject=Re: Inquiry, message_id=<...>
```

### Usage

```bash
# Enable dry-run for testing
export EMAIL_DRY_RUN=1

# Start your services - emails will be logged but not sent
python -m tiers.tier_3.channel_sequencer_agent.consumer
```

---

## Inbox Poller Backpressure

**Module:** `services/email/inbox_poller.py`

### Configuration

| Environment Variable         | Default | Description                      |
| ---------------------------- | ------- | -------------------------------- |
| `INBOX_BACKPRESSURE_ENABLED` | `1`     | Enable backpressure check        |
| `INBOX_MAX_PENDING`          | `100`   | Skip poll if pending > threshold |

When enabled, the inbox poller skips polling cycles if the Manager stream has too many pending messages:

```
Backpressure: 150 pending messages (threshold=100), skipping poll
```

This prevents overwhelming downstream components during high load or outages.
