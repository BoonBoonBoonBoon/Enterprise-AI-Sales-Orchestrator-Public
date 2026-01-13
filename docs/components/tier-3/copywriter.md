# Copywriter Agent

The Copywriter Agent generates AI-powered email content, including subject lines, bodies, and personalized replies.

## Overview

| Property          | Value                                               |
| ----------------- | --------------------------------------------------- |
| **Tier**          | 3 (Execution)                                       |
| **Stream**        | `{tenant}:agents:copywriter:tasks`                  |
| **Database Role** | None (no direct DB access)                          |
| **Core File**     | `tiers/tier_3/copywriter_agent/copywriter_agent.py` |

## Responsibilities

- Generate personalized email copy
- Draft replies based on conversation context
- Create subject lines
- Apply brand voice and tone
- Follow outreach templates

## Actions

### `draft_reply`

Generate a reply to an inbound email.

**Request:**

```json
{
  "action": "draft_reply",
  "reply_packet": {
    "lead_id": "uuid-lead",
    "lead_source": "leads",
    "context": {
      "name": "John Doe",
      "company": "Acme Inc",
      "recent_messages": [
        { "role": "lead", "content": "I'm interested in your product..." }
      ]
    },
    "thread_id": "uuid-conv"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "subject": "Re: Your inquiry about our product",
    "body": "Hi John,\n\nThank you for reaching out...",
    "metadata": {
      "tone": "professional",
      "tokens_used": 245
    }
  }
}
```

### `generate_outreach`

Create initial outreach email.

**Request:**

```json
{
  "action": "generate_outreach",
  "lead": {
    "name": "Jane Smith",
    "company": "TechCorp",
    "role": "CTO"
  },
  "campaign": {
    "template": "cold_outreach_v2",
    "value_prop": "AI automation platform"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "subject": "Quick question about TechCorp's automation",
    "body": "Hi Jane,\n\nI noticed TechCorp is scaling...",
    "personalization_score": 0.85
  }
}
```

### `generate_subject`

Create subject line only.

**Request:**

```json
{
  "action": "generate_subject",
  "context": {
    "purpose": "follow_up",
    "previous_subject": "Re: Our conversation",
    "lead_name": "John"
  },
  "options": {
    "max_length": 50,
    "style": "casual"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "result": {
    "subject": "John - quick follow up",
    "alternatives": ["Checking in, John", "Following up on our chat"]
  }
}
```

## LLM Configuration

### Provider Settings

```python
# config/settings.py
LLM_PROVIDER = "openai"  # or "anthropic"
LLM_MODEL = "gpt-4o"
LLM_TEMPERATURE = 0.7  # Higher for creative copy
```

### Environment Variables

| Variable            | Default  | Description       |
| ------------------- | -------- | ----------------- |
| `OPENAI_API_KEY`    | —        | OpenAI API key    |
| `ANTHROPIC_API_KEY` | —        | Anthropic API key |
| `LLM_MODEL`         | `gpt-4o` | Model to use      |
| `LLM_TEMPERATURE`   | `0.7`    | Creativity level  |

## File Structure

```
tiers/tier_3/copywriter_agent/
├── copywriter_agent.py      # LangGraph StateGraph
├── copywriter_harness.py    # Redis wrapper
├── consumer.py              # Entry point
├── prompts/                 # Prompt templates
│   ├── reply.txt
│   ├── outreach.txt
│   └── subject.txt
├── validators.py            # Pydantic models
└── README.md
```

## Prompt Engineering

### Template Structure

```
prompts/reply.txt
---
You are a professional sales representative.

CONTEXT:
Lead Name: {{lead_name}}
Company: {{company}}
Previous Messages:
{{conversation_history}}

TASK:
Draft a reply that:
- Addresses their inquiry
- Maintains professional tone
- Includes clear next steps
- Is concise (under 150 words)

RESPONSE FORMAT:
Subject: <subject line>
Body: <email body>
```

### Dynamic Injection

```python
def build_prompt(self, action: str, context: dict) -> str:
    template = self.load_template(f"{action}.txt")
    return template.format(**context)
```

## Error Codes

| Code               | Description                   |
| ------------------ | ----------------------------- |
| `LLM_ERROR`        | LLM API call failed           |
| `RATE_LIMITED`     | Provider rate limit hit       |
| `CONTEXT_TOO_LONG` | Input exceeded token limit    |
| `INVALID_ACTION`   | Unknown action type           |
| `MISSING_CONTEXT`  | Required context not provided |

## Usage Example

### From Orchestrator

```python
async def draft_reply(self, reply_packet: dict) -> dict:
    task = {
        "task_id": str(uuid.uuid4()),
        "tenant_id": self.tenant_id,
        "payload": {
            "action": "draft_reply",
            "reply_packet": reply_packet
        },
        "metadata": {"source": "outreach_orchestrator"}
    }

    await self.redis.xadd(
        f"{self.tenant_id}:agents:copywriter:tasks",
        {"data": json.dumps(task)}
    )

    # Wait for result...
    return result["body"], result["subject"]
```

### Running Consumer

```powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.copywriter_agent.consumer
```

## Demo

Try the copywriter without Redis:

```powershell
& ".venv/Scripts/python.exe" examples/copywriter_llm_demo.py
```

## No Database Access

!!! warning "Important"
The Copywriter Agent has **no direct database access**.

    All lead context must be provided in the task payload. This is by design:

    - RAG Agent retrieves context
    - Orchestrator passes context to Copywriter
    - Copywriter generates content
    - Persistence Agent stores the result

## Related

- [RAG Agent](rag.md) — Provides context
- [Outreach Orchestrator](../tier-2/outreach.md) — Coordinates drafting
- [Agent Harness](../../concepts/agent-harness.md) — Agent framework
- [Creating Agents](../../guides/dev/new-agent.md)
