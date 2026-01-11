# Inbound Orchestrator - Tier 2

Business logic orchestrator for inbound communication processing.

## Purpose

Coordinates processing of inbound communications including:
- Email/message intake
- Content classification
- Intent detection
- Response routing
- Automated reply coordination

## Architecture

```
inbound_orchestrator/
├── __init__.py                       # Public API
├── inbound_orchestrator.py           # Core orchestration logic
├── inbound_orchestrator_harness.py   # Harness wrapper
├── consumer.py                       # Redis stream consumer
├── schemas/                          # Input/output schemas
├── tests/                            # Unit tests
└── tools/                            # Inbound-specific tools
```

## Usage

### Direct Usage

```python
from tiers.tier_2.inbound_orchestrator import InboundOrchestrator

orchestrator = InboundOrchestrator(config={})
result = await orchestrator.process_task(envelope)
```

### With Harness

```python
from tiers.tier_2.inbound_orchestrator import InboundOrchestratorHarness

harness = InboundOrchestratorHarness(config={})
result = await harness.execute(envelope)
```

### As Consumer

```bash
python -m tiers.tier_2.inbound_orchestrator.consumer
```

## Redis Streams

**Consumes from:** `{tenant}:orchestrators:inbound:tasks`  
**Publishes to:** `{tenant}:orchestrators:inbound:results`

## Implementation Status

⚠️ **SKELETON** - Core implementation pending

**TODO:**
- [ ] Implement message parsing (email, SMS, chat)
- [ ] Add ML-based classification
- [ ] Implement intent detection engine
- [ ] Add routing rules engine
- [ ] Create response templates
- [ ] Implement auto-reply logic
- [ ] Add comprehensive tests
- [ ] Create inbound schemas

## Configuration

```python
config = {
    "supported_channels": ["email", "sms", "chat"],
    "auto_reply": True,
    "classification_model": "default",
    "routing_rules": []
}
```

## Integration Points

- **Email Service**: Receives parsed emails
- **SMS Gateway**: Processes text messages
- **Chat System**: Handles chat messages
- **CRM**: Routes to appropriate contacts/leads
