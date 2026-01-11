# Copywriter Agent

**Tier:** 3 (Execution) | **Type:** Content Generation Agent

## Purpose

The Copywriter Agent generates AI-powered personalized content for outreach campaigns:

- **Email copy** — Subject lines and body content
- **SMS messages** — Short, impactful text messages
- **Personalized content** — Tailored to lead context and campaign goals

## Architecture

```
Outreach Orchestrator (Tier 2)
    │
    ▼ {tenant}:agents:copywriter:tasks
┌──────────────────────────────────────┐
│         COPYWRITER AGENT (Tier 3)    │
│                                      │
│  • LLM-powered content generation    │
│  • Template fallback for reliability │
│  • Tone and length customization     │
└───────────────┬──────────────────────┘
                │
                ▼ {tenant}:agents:copywriter:results
    Outreach Orchestrator (Tier 2)
```

## Key Components

| File                          | Purpose                                                   |
| ----------------------------- | --------------------------------------------------------- |
| `copywriter.py`               | Core agent: LLM calls, prompt building, template fallback |
| `copywriter_agent_harness.py` | Redis wrapper: stream consumption, retries                |
| `consumer.py`                 | Entry point: runs the harness loop                        |
| `worker.py`                   | Synchronous execution wrapper                             |
| `schemas/`                    | Pydantic models for request/response                      |

## Quick Start

```bash
# Run the Copywriter Agent consumer
python -m tiers.tier_3.copywriter_agent.consumer
```

## Task Format

### Email Generation

```json
{
  "type": "email",
  "context": {
    "lead_name": "John Smith",
    "company": "Acme Corp",
    "industry": "Technology",
    "goal": "Request discovery call"
  },
  "tone": "professional",
  "length": "medium"
}
```

### SMS Generation

```json
{
  "type": "sms",
  "context": {
    "lead_name": "John",
    "event": "webinar follow-up"
  },
  "tone": "casual",
  "max_length": 160
}
```

## Response Format

```json
{
  "status": "success",
  "copy": {
    "subject": "Quick question about Acme's AI strategy",
    "body": "Hi John,\n\nI noticed Acme Corp has been expanding...",
    "type": "email",
    "metadata": {
      "model": "gpt-4o-mini",
      "tokens_used": 150
    }
  }
}
```

## LLM Integration

The agent supports multiple LLM providers:

| Provider  | SDK             | Environment Variable |
| --------- | --------------- | -------------------- |
| OpenAI    | `openai>=1.0.0` | `OPENAI_API_KEY`     |
| Anthropic | `anthropic`     | `ANTHROPIC_API_KEY`  |

Falls back to templates if no LLM is configured or call fails.

## Tone Options

| Tone           | Use Case                      |
| -------------- | ----------------------------- |
| `professional` | B2B enterprise outreach       |
| `casual`       | Warm, friendly messages       |
| `formal`       | Executive-level communication |

## Harness Configuration

```python
from tiers.tier_3.copywriter_agent.copywriter_agent_harness import CopywriterAgentHarness

harness = CopywriterAgentHarness(
    tenant_id="agentic-dev",
    enable_observability=True,
)
harness.run()
```

## Database Access

**None** — Copywriter Agent has no direct database access. All lead context is passed in the task payload by the orchestrator.

## Testing

```bash
# Unit tests
pytest tiers/tier_3/copywriter_agent/tests/ -v

# Demo with LLM
python examples/copywriter_llm_demo.py
```

## See Also

- [Tier 3 Overview](../README.md)
- [Outreach Orchestrator](../../tier_2/outreach_orchestrator/README.md)
- [Agent Harness](../../../core/harness/README.md)
