# Classifier Agent

Tier 3 agent that classifies inbound emails to determine routing.

## Purpose

Classifies emails into categories:

- **personal** / **business_inquiry** → Route to Leads for reply
- **newsletter** / **marketing** → Store only, no reply
- **transactional** → Store only, no reply (order confirmations, etc.)
- **bounce** → Drop
- **auto_reply** → Store only (OOO, vacation)
- **spam** → Drop
- **unknown** → Route to review queue

## Classification Approach

1. **Pre-filter check**: If Tier-0 pre-filter already classified with high confidence, trust it
2. **Rules-based classification**: Pattern matching on sender, subject, body
3. **Optional LLM fallback**: For ambiguous cases (env: `CLASSIFIER_LLM_ENABLED=1`)

## Usage

### As Consumer

```powershell
.\.venv\Scripts\python.exe -m tiers.tier_3.classifier_agent.consumer
```

### Programmatic

```python
from tiers.tier_3.classifier_agent import ClassifierAgent

classifier = ClassifierAgent()
result = classifier.classify({
    "from_email": "someone@gmail.com",
    "subject": "Question about your services",
    "body": "Hi, I'm interested in...",
})
print(result.category, result.action, result.confidence)
```

## Configuration

| Env Var                               | Default | Description                             |
| ------------------------------------- | ------- | --------------------------------------- |
| `CLASSIFIER_LLM_ENABLED`              | `0`     | Enable LLM fallback for ambiguous cases |
| `CLASSIFIER_LLM_CONFIDENCE_THRESHOLD` | `0.6`   | Min rules confidence before LLM         |

## Streams

- **Input**: `{tenant}:agents:classifier:tasks`
- **Output**: `{tenant}:agents:classifier:results`
