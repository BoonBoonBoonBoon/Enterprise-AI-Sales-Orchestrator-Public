# Outreach Orchestrator

**Tier 2 Orchestrator** for multi-channel outreach campaigns.

## Overview

The Outreach Orchestrator coordinates outreach campaigns across email, LinkedIn, and phone channels. It delegates specialized tasks to three operational agents:

- **Copywriter Agent**: Generates personalized campaign content
- **Scheduler Agent**: Schedules meetings with engaged prospects
- **Channel Sequencer Agent**: Optimizes channel order using rules/ML

## Architecture

```
Manager Agent (Tier 1)
    ↓
Outreach Orchestrator (Tier 2) ← This orchestrator
    ↓
Copywriter, Booking, Sequencing Agents (Operational)
```

## Channel Strategy

The orchestrator follows proven multi-channel sequencing:

1. **Email** (Day 0) - Initial touchpoint, scalable
2. **LinkedIn** (Day 3) - If email opened but no reply
3. **Phone** (Day 7) - If LinkedIn engaged but no reply
4. **Follow-up Email** (Day 10) - Re-engagement attempt

### Why This Sequence?

- **Email first**: Low friction, establishes context
- **3-day gaps**: Avoids spam perception
- **LinkedIn second**: Visual presence after email awareness
- **Phone third**: High-touch for warm leads only
- **Follow-up**: Re-engage those who went dark

## Tools

### Deterministic Tools (5)

#### 1. `validate_campaign_tool`

Validates campaign configuration before launch.

**Checks:**
- Required fields (name, leads, channels, touchpoints)
- Channel names (email, linkedin, phone, sms)
- Touchpoint timing (warns if < 2 days apart)
- Campaign size (warns if > 10,000 leads)

**Example:**
```json
{
  "name": "Q4 Enterprise Campaign",
  "leads": ["lead-123", "lead-456"],
  "channels": ["email", "linkedin", "phone"],
  "touchpoints": [
    {"channel": "email", "delay_days": 0},
    {"channel": "linkedin", "delay_days": 3},
    {"channel": "phone", "delay_days": 7}
  ]
}
```

**Returns:**
```json
{
  "valid": true,
  "warnings": [],
  "summary": "Campaign valid: 2 leads, 3 channels, 3 touchpoints"
}
```

#### 2. `create_touchpoint_tool`

Creates a touchpoint in a campaign.

**Arguments:**
- `campaign_id`: Campaign identifier
- `lead_id`: Lead identifier
- `channel`: Channel name (email/linkedin/phone/sms)
- `content`: Message content
- `scheduled_for`: ISO 8601 timestamp

**Example:**
```json
{
  "campaign_id": "camp-123",
  "lead_id": "lead-456",
  "channel": "email",
  "content": "Hi {first_name}, I noticed your recent post...",
  "scheduled_for": "2024-01-15T09:00:00Z"
}
```

**Returns:**
```json
{
  "touchpoint_id": "touch-789",
  "status": "scheduled",
  "message": "Touchpoint created and scheduled for 2024-01-15 09:00:00"
}
```

#### 3. `schedule_touchpoint_tool`

Schedules a touchpoint for delivery.

**Arguments:**
- `touchpoint_id`: Touchpoint identifier
- `scheduled_for`: ISO 8601 timestamp
- `priority`: Priority level (low/normal/high/urgent)

**Example:**
```json
{
  "touchpoint_id": "touch-789",
  "scheduled_for": "2024-01-15T14:00:00Z",
  "priority": "high"
}
```

**Returns:**
```json
{
  "touchpoint_id": "touch-789",
  "scheduled_for": "2024-01-15T14:00:00Z",
  "priority": "high",
  "status": "scheduled"
}
```

#### 4. `query_campaign_metrics_tool`

Gets campaign performance metrics.

**Arguments:**
- `campaign_id`: Campaign identifier

**Returns:**
```json
{
  "campaign_id": "camp-123",
  "sent": 500,
  "opened": 250,
  "clicked": 75,
  "replied": 30,
  "booked": 12,
  "open_rate": 0.50,
  "click_rate": 0.15,
  "reply_rate": 0.06,
  "booking_rate": 0.024
}
```

#### 5. `update_campaign_status_tool`

Updates campaign status.

**Arguments:**
- `campaign_id`: Campaign identifier
- `status`: New status (draft/active/paused/completed/cancelled)
- `reason`: Reason for status change

**Example:**
```json
{
  "campaign_id": "camp-123",
  "status": "paused",
  "reason": "Revising messaging based on low reply rate"
}
```

### Delegation Tools (3)

#### 6. `delegate_to_copywriter_tool`

Enqueues copy generation task to Copywriter agent.

**Arguments:**
- `lead_id`: Lead identifier
- `channel`: Channel name
- `tone`: Tone (professional/casual/friendly)
- `goal`: Copy goal
- `context`: Additional context

**Example:**
```json
{
  "lead_id": "lead-456",
  "channel": "email",
  "tone": "professional",
  "goal": "Request discovery call",
  "context": "Lead downloaded our whitepaper on AI automation"
}
```

**Returns:**
```json
{
  "status": "delegated",
  "stream": "acme:copywriter:tasks",
  "task_id": "copy-123",
  "message": "Copy generation enqueued for Copywriter agent"
}
```

#### 7. `delegate_to_booking_agent_tool`

Enqueues meeting scheduling task to Booking agent.

**Arguments:**
- `lead_id`: Lead identifier
- `meeting_type`: Meeting type (discovery/demo/review)
- `duration_minutes`: Duration
- `preferred_times`: Preferred time slots

**Example:**
```json
{
  "lead_id": "lead-456",
  "meeting_type": "discovery",
  "duration_minutes": 30,
  "preferred_times": ["2024-01-18T10:00:00Z", "2024-01-18T14:00:00Z"]
}
```

**Returns:**
```json
{
  "status": "delegated",
  "stream": "acme:booking:tasks",
  "task_id": "booking-123",
  "message": "Meeting scheduling enqueued for Booking agent"
}
```

#### 8. `delegate_to_sequencing_agent_tool`

Enqueues sequence optimization task to Sequencing agent.

**Arguments:**
- `campaign_id`: Campaign identifier
- `current_performance`: Current metrics
- `optimization_goal`: Goal (maximize_replies/maximize_bookings/minimize_spam)

**Example:**
```json
{
  "campaign_id": "camp-123",
  "current_performance": {
    "email_open_rate": 0.45,
    "linkedin_engagement_rate": 0.20,
    "phone_connect_rate": 0.10
  },
  "optimization_goal": "maximize_bookings"
}
```

**Returns:**
```json
{
  "status": "delegated",
  "stream": "acme:sequencing:tasks",
  "task_id": "seq-123",
  "message": "Sequence optimization enqueued for Sequencing agent"
}
```

## Campaign Workflows

### Example 1: Simple Single-Lead Campaign

**User Request:**
"Launch email campaign for lead-456"

**Orchestrator Steps:**
1. **Validate**: Check campaign config
2. **Delegate to Copywriter**: Generate personalized email
3. **Create Touchpoint**: Email touchpoint with generated copy
4. **Schedule**: Schedule for immediate delivery
5. **Monitor**: Query metrics after 24 hours

### Example 2: Multi-Channel Campaign (100 Leads)

**User Request:**
"Launch Q4 enterprise campaign across email, LinkedIn, phone"

**Orchestrator Steps:**
1. **Validate**: 100 leads, 3 channels, 4 touchpoints
2. **Batch Create**: Create touchpoints for all leads
   - Email: Day 0
   - LinkedIn: Day 3 (conditional on email open)
   - Phone: Day 7 (conditional on LinkedIn engagement)
   - Follow-up: Day 10
3. **Delegate to Copywriter**: Generate copy for each channel/lead
4. **Schedule**: Schedule all touchpoints
5. **Monitor**: Query metrics daily
6. **Optimize**: Delegate to Sequencing agent for ML optimization

### Example 3: A/B Test Campaign

**User Request:**
"A/B test email subject lines for 500 leads"

**Orchestrator Steps:**
1. **Split**: Create 2 campaigns (250 leads each)
2. **Delegate to Copywriter**: Generate variants A and B
3. **Create**: Create touchpoints for both groups
4. **Schedule**: Schedule for same time
5. **Monitor**: Query metrics after 48 hours
6. **Analyze**: Compare open rates, click rates
7. **Scale**: Use winning variant for remaining leads

## Integration with Subagents

### Copywriter Agent

**Responsibility:** Generate personalized campaign content

**Delegation:**
```python
delegate_to_copywriter_tool(
    lead_id="lead-456",
    channel="email",
    tone="professional",
    goal="Request discovery call",
    context="Downloaded AI whitepaper"
)
```

**Redis Stream:** `{tenant}:agents:copywriter:tasks`

**Expected Result:** Personalized email copy

### Scheduler Agent

**Responsibility:** Schedule meetings with engaged prospects

**Delegation:**
```python
delegate_to_scheduler_agent_tool(
  lead_id="lead-456",
  meeting_type="discovery",
  duration_minutes=30,
  preferred_times=[...]
)
```

**Redis Stream:** `{tenant}:agents:booking:tasks`

**Expected Result:** Meeting scheduled on calendar

### Channel Sequencer Agent

**Responsibility:** Build/optimize channel sequences using rules/ML

**Delegation:**
```python
delegate_to_channel_sequencer_agent_tool(
  campaign_id="camp-123",
  current_sequence=[...],
  optimization_goal="maximize_bookings"
)
```

**Redis Stream:** `{tenant}:agents:sequencing:tasks`

**Expected Result:** Optimized touchpoint sequence

## Harness Configuration

### Development

```python
harness = OutreachOrchestratorHarness(
    redis_client,
    tenant_id="acme",
    environment="development",
    enable_observability=False,
    enable_checkpointing=False
)
```

**Configuration:**
- 5 retries (campaigns are valuable)
- 120s timeout (copy generation can be slow)
- No checkpointing (short tests)
- Memory quota backend

### Production

```python
harness = OutreachOrchestratorHarness(
    redis_client,
    tenant_id="acme",
    environment="production",
    enable_observability=True,
    enable_checkpointing=True
)
```

**Configuration:**
- 5 retries with jittered backoff
- 120s timeout
- Redis checkpointing (resume long campaigns)
- 500 requests/hour quota (protect external APIs)
- Datadog observability

## Best Practices

### Campaign Design

1. **Start with email**: Lowest friction, establishes context
2. **Wait 3+ days**: Between touchpoints to avoid spam
3. **Personalize**: Use Copywriter agent for each lead
4. **Conditional progression**: Only move to next channel if engaged
5. **Track metrics**: Query metrics daily to optimize

### Spam Prevention

The orchestrator includes validation to prevent spam patterns:

- **Warns if touchpoints < 2 days apart**
- **Warns if > 10,000 leads** (suggests batching)
- **Checks touchpoint order** (earlier touchpoints should have earlier delays)

### Rate Limiting

- **500 requests/hour** default quota
- Protects external APIs (email providers, LinkedIn, calendar)
- Use Redis quota backend for multi-instance coordination

### Checkpointing

Enable checkpointing for:
- Long-running campaigns (> 1 day)
- Large campaigns (> 1,000 leads)
- Production environments

This allows campaign resumption after failures.

## Error Handling

The harness provides automatic error handling:

- **Transient failures**: Retries with backoff
- **Timeout**: 120s timeout for slow operations
- **Quota exceeded**: Returns quota_exceeded error
- **Invalid input**: Returns validation error

## Observability

### Metrics (Datadog)

- `agentic_system.outreach.touchpoints_created`
- `agentic_system.outreach.touchpoints_scheduled`
- `agentic_system.outreach.campaign_metrics_queried`
- `agentic_system.outreach.delegations_sent`

### Traces

All operations traced with:
- Campaign ID
- Lead ID
- Channel
- Tenant ID
- Environment

## Future Enhancements

1. **Multi-variant testing**: Built-in A/B/n testing
2. **Auto-optimization**: Automatic sequence optimization based on metrics
3. **Reply detection**: Automatic campaign pause when lead replies
4. **Sentiment analysis**: Adjust tone based on lead sentiment
5. **Calendar integration**: Direct booking link in emails
