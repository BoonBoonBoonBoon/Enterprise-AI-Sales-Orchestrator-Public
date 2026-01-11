# A/B Testing Framework — Complete Guide

Comprehensive framework for running data-driven experiments in cold email outreach campaigns.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Framework Architecture](#framework-architecture)
4. [Core Concepts](#core-concepts)
5. [Integration Guide](#integration-guide)
6. [Statistical Methods](#statistical-methods)
7. [Best Practices](#best-practices)
8. [API Reference](#api-reference)

---

## Overview

### Why A/B Testing Matters

**Data-Driven Decisions:** Replace "gut feelings" with statistical evidence

**Continuous Improvement:** Small improvements compound over time
- 5% improvement in open rate × 1M leads = 50K additional opens
- 2% improvement in conversion rate = 20K new customers

**Risk Mitigation:** Test before full rollout
- Roll out to 10% first, verify impact
- Instantly rollback failing variants
- No downtime for customers

**Product Learning:** Build institutional knowledge
- What tone works best for different industries
- Optimal personalization levels per lead source
- Subject line patterns that work

### Real-World Impact Scenarios

**Example 1: Professional vs Casual Tone**
- Variant A (Control): Professional tone
- Variant B: Casual, friendly tone
- Result: +14% open rate improvement (statistically significant)
- Recommendation: Roll out casual tone to all campaigns

**Example 2: Subject Line Length**
- Variant A (Control): 5-7 words
- Variant B: 10-12 words
- Result: -5.6% open rate (not statistically significant)
- Recommendation: Keep current subject line length

**Example 3: Personalization Level**
- Variant A (Control): Basic (name only)
- Variant B: Advanced (name + company + recent news)
- Result: +60% reply rate improvement
- Recommendation: Invest in enrichment for personalization

---

## Quick Start

### 1. Define an Experiment

```python
from agent.utils.ab_testing import (
    ExperimentConfig, VariantConfig, BucketStrategy
)
from datetime import datetime, timedelta

config = ExperimentConfig(
    experiment_id="exp-tone-professional-casual-2024",
    name="Professional vs Casual Tone Test",
    hypothesis="Casual tone increases open rates by 15%",
    variants=[
        VariantConfig(
            name="A",
            weight=0.5,
            template="cold_email",
            tone="professional",
            description="Standard professional tone"
        ),
        VariantConfig(
            name="B",
            weight=0.5,
            template="cold_email",
            tone="casual",
            description="Casual, friendly tone"
        ),
    ],
    bucketing_strategy=BucketStrategy.TRAFFIC_SPLIT,
    start_date=datetime.utcnow(),
    end_date=datetime.utcnow() + timedelta(days=30),
    min_sample_size=500,
    significance_threshold=0.95,
    campaign_id="camp-123"
)
```

### 2. Assign Variants to Leads

```python
from agent.utils.ab_testing import assign_variant

# During lead retrieval in RAG agent
lead_id = "lead-123"
experiment_id = "exp-tone-professional-casual-2024"

assigned_variant = assign_variant(
    lead_id=lead_id,
    experiment_id=experiment_id,
    variants=config.variants
)

print(f"Lead {lead_id} assigned to variant {assigned_variant}")
# Output: "Lead lead-123 assigned to variant A"

# Same lead always gets same variant (deterministic)
```

### 3. Track Conversion Events

```python
from agent.utils.ab_testing import track_conversion, ConversionEvent

# When email sent
track_conversion(
    lead_id=lead_id,
    experiment_id="exp-tone-professional-casual-2024",
    variant=assigned_variant,
    event_type=ConversionEvent.SENT
)

# When email opened (from webhook)
track_conversion(
    lead_id=lead_id,
    experiment_id="exp-tone-professional-casual-2024",
    variant=assigned_variant,
    event_type=ConversionEvent.OPENED
)

# When lead replied
track_conversion(
    lead_id=lead_id,
    experiment_id="exp-tone-professional-casual-2024",
    variant=assigned_variant,
    event_type=ConversionEvent.REPLIED
)
```

### 4. Analyze Results

```python
results = store.calculate_results(
    experiment_id="exp-tone-professional-casual-2024",
    event_type=ConversionEvent.OPENED,
    control_variant="A"
)

print(f"Winner: {results.winner}")
print(f"Lift: {results.lift:.1f}%")
print(f"Recommendation: {results.recommendation}")

# Output:
# Winner: B
# Lift: 14.9%
# Recommendation: Variant B showed 14.9% improvement. Consider rolling out.
```

---

## Framework Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│ A/B Testing Framework (agent/utils/ab_testing.py)     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Variant Assignment                               │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ • assign_variant(lead_id, exp_id, variants)     │  │
│  │ • Deterministic hashing (lead_id + exp_id)      │  │
│  │ • Consistent across system                      │  │
│  │ • Same lead → Same variant (always)             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Conversion Tracking                              │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ • track_conversion(lead_id, exp_id, variant)    │  │
│  │ • Record event type (opened, clicked, etc.)     │  │
│  │ • Metadata + optional conversion value          │  │
│  │ • Persisted to database                         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Statistical Analysis                             │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ • calculate_conversion_rate()                    │  │
│  │ • calculate_confidence_interval()                │  │
│  │ • is_statistically_significant()                 │  │
│  │ • Two-proportion z-test                          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Storage & Retrieval                              │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ • ABTestingStore (in-memory, placeholder)        │  │
│  │ • Production: Redis + PostgreSQL                 │  │
│  │ • Query conversions by exp/variant/event         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Data Models

```python
ExperimentConfig          # Experiment definition
├─ experiment_id
├─ name, hypothesis
├─ variants[]             # VariantConfig
├─ bucketing_strategy
├─ start_date, end_date
└─ min_sample_size, significance_threshold

VariantConfig            # Individual variant
├─ name (A, B, etc.)
├─ weight (traffic %)
├─ template, tone
└─ description

ConversionRecord         # Track a conversion event
├─ lead_id
├─ experiment_id
├─ variant
├─ event_type            # OPENED, CLICKED, REPLIED, etc.
├─ timestamp
├─ value                 # Optional conversion value
└─ metadata

ExperimentResults        # Analysis output
├─ experiment_id
├─ status
├─ variants_stats[]      # VariantStats (per variant)
├─ winner                # Winning variant
├─ lift                  # % improvement
└─ recommendation
```

---

## Core Concepts

### Variants

Variants represent different versions of content to test:

```python
VariantConfig(
    name="A",              # Control variant
    weight=0.5,            # 50% of traffic
    tone="professional",   # Variant parameter
    template="cold_email",
    description="Standard professional tone"
)
```

**Common Variant Parameters:**
- `tone`: professional, casual, friendly, urgent
- `template`: cold_email, follow_up_step_2, nurture_sequence
- `subject_line_length`: short (5-7 words), medium (8-10), long (11-15)
- `body_length`: concise (<100 words), standard (100-200), detailed (200+)
- `personalization_level`: basic (name), medium (name + company), high (name + company + recent news)
- `cta`: explicit vs subtle, urgent vs relaxed

### Bucketing Strategy

Determines how leads are assigned to variants:

```python
BucketStrategy.TRAFFIC_SPLIT   # Even distribution (50/50, 60/40, etc.)
BucketStrategy.WEIGHTED        # Custom weights per variant
BucketStrategy.SEQUENTIAL      # Ramp up: 5% → 25% → 100%
```

### Conversion Events

Track different types of user actions:

```python
ConversionEvent.SENT           # Email sent (baseline)
ConversionEvent.OPENED         # Email opened (engagement)
ConversionEvent.CLICKED        # Link clicked (engagement)
ConversionEvent.REPLIED        # Lead replied (interaction)
ConversionEvent.MEETING        # Meeting booked (conversion)
ConversionEvent.CONVERTED      # Purchase/signup (revenue)
ConversionEvent.UNSUBSCRIBED   # Opted out (negative)
ConversionEvent.BOUNCED        # Delivery failed (quality)
```

### Experiment Lifecycle

```
DRAFT
  ↓ (Start experiment)
RUNNING
  ├─ (Pause if needed)
  └─ PAUSED → RUNNING
  ↓ (End date reached or enough data)
COMPLETED
  ↓ (Analysis done, archival)
ARCHIVED
```

---

## Integration Guide

### End-to-End Flow

```
1. Orchestrator creates experiment config
        │
        ▼
2. RAG agent retrieves leads
        │
        ▼
3. For each lead:
   a. Assign variant (consistent hash)
   b. Track SENT event
   c. Pass variant to copywriter
        │
        ▼
4. Copywriter generates copy with variant tone/template
   a. Uses assigned variant settings
   b. Tracks generation metadata
        │
        ▼
5. Persistence saves copy with variant
        │
        ▼
6. Email delivery service:
   a. Tracks OPENED event when opened
   b. Tracks CLICKED event when link clicked
   c. Tracks REPLIED event when lead responds
        │
        ▼
7. Webhook receivers update conversion records
        │
        ▼
8. Analysis job calculates results daily
   a. Determines winner (if significant)
   b. Updates dashboard
   c. Triggers alerts if thresholds met
```

### Integration with RAG Agent

```python
from agent.utils.ab_testing import assign_variant
from agent.schemas import CopywriterTaskPayload, CampaignContext

# In RAG agent after retrieving leads
experiment_config = ExperimentConfig(...)

for lead in leads:
    # Assign variant
    variant = assign_variant(
        lead_id=lead["id"],
        experiment_id=experiment_config.experiment_id,
        variants=experiment_config.variants
    )
    
    # Create copywriter task with variant
    payload = CopywriterTaskPayload(
        lead_data=LeadData(**lead),
        campaign_context=CampaignContext(
            campaign_id=experiment_config.campaign_id,
            variant=variant,  # Pass variant!
            sequence_step=1
        ),
        instructions=CopyInstructions(
            # Tone determined by variant
            tone="professional" if variant == "A" else "casual",
            template="cold_email"
        ),
        ab_experiment_id=experiment_config.experiment_id,
        ab_variant=variant
    )
    
    # Send to copywriter stream
    send_to_stream("copywriter:tasks", payload.model_dump())
    
    # Track sent event
    track_conversion(
        lead_id=lead["id"],
        experiment_id=experiment_config.experiment_id,
        variant=variant,
        event_type=ConversionEvent.SENT
    )
```

### Modified CopywriterTaskPayload

```python
class CopywriterTaskPayload(BaseModel):
    lead_data: LeadData
    campaign_context: CampaignContext
    instructions: CopyInstructions
    ab_experiment_id: Optional[str] = None  # NEW
    ab_variant: Optional[str] = None        # NEW
    previous_interactions: List[Dict] = []
    timeout_ms: int = 60000
```

---

## Statistical Methods

### Two-Proportion Z-Test

**Decision:** Use z-test for statistical significance (not t-test or chi-square)

**Why:**
- Large sample sizes (n > 500)
- Binomial distribution approximates normal
- Standard industry practice (Google, Facebook, Airbnb use this)
- Fast to compute

**Assumptions:**
- Sample size ≥ 500 per variant
- Expected successes ≥ 5 in each group

### Confidence Intervals

Provides range of plausible conversion rates:

```python
# Variant A: 57% conversion rate
# 95% confidence interval: (52%, 62%)
# Interpretation: True rate is 95% likely between 52% and 62%
```

### Lift Calculation

Percentage improvement over control:

```
Lift = ((Treatment Rate - Control Rate) / Control Rate) × 100
```

Example:
- Control: 57% opened
- Treatment: 65.6% opened
- Lift: ((0.656 - 0.57) / 0.57) × 100 = **15.1%**

---

## Best Practices

### Sample Size Planning

**Minimum recommended:** 500 leads per variant

**Calculate required sample size:**
```python
from agent.utils.ab_testing import calculate_required_sample_size

n = calculate_required_sample_size(
    baseline_rate=0.25,      # Current conversion rate
    minimum_detectable_effect=0.05,  # Want to detect 5% absolute improvement
    significance=0.95,       # 95% confidence
    power=0.80               # 80% power
)
print(f"Need {n} leads per variant")
```

### Testing Cadence

- **Run for full week:** Account for day-of-week effects
- **Avoid holidays:** Can skew results
- **End early only if:** Clear winner and significance reached

### Variant Design

- **Test one variable:** Don't change tone AND length simultaneously
- **Keep control simple:** Baseline should be current best practice
- **Limit variants:** Start with 2 (A/B), max 4 (A/B/C/D)

### Statistical Rigor

- **Set significance threshold before starting:** Don't move goalposts
- **Don't peek too early:** Wait for minimum sample size
- **Account for multiple comparisons:** Use Bonferroni correction for multiple tests

---

## API Reference

### assign_variant(lead_id, experiment_id, variants)

Deterministically assigns a lead to a variant using consistent hashing.

**Parameters:**
- `lead_id` (str): Unique lead identifier
- `experiment_id` (str): Experiment identifier
- `variants` (List[VariantConfig]): List of variants with weights

**Returns:** str (variant name, e.g., "A", "B")

**Example:**
```python
variant = assign_variant("lead-123", "exp-tone-2024", [
    VariantConfig(name="A", weight=0.5),
    VariantConfig(name="B", weight=0.5)
])
# Returns: "A" (deterministic - always same for this lead+experiment)
```

### track_conversion(lead_id, experiment_id, variant, event_type, value=None, metadata=None)

Records a conversion event for tracking.

**Parameters:**
- `lead_id` (str): Lead identifier
- `experiment_id` (str): Experiment identifier
- `variant` (str): Assigned variant (A, B, etc.)
- `event_type` (ConversionEvent): Type of conversion
- `value` (Optional[float]): Conversion value (e.g., $500)
- `metadata` (Optional[Dict]): Additional context

**Returns:** ConversionRecord

**Example:**
```python
record = track_conversion(
    lead_id="lead-123",
    experiment_id="exp-tone-2024",
    variant="B",
    event_type=ConversionEvent.OPENED,
    metadata={"email_provider": "gmail", "device": "mobile"}
)
```

### calculate_results(experiment_id, event_type, control_variant)

Computes statistics and determines winner.

**Parameters:**
- `experiment_id` (str): Experiment identifier
- `event_type` (ConversionEvent): Event to analyze
- `control_variant` (str): Control variant name (usually "A")

**Returns:** ExperimentResults

**Example:**
```python
results = store.calculate_results(
    experiment_id="exp-tone-2024",
    event_type=ConversionEvent.OPENED,
    control_variant="A"
)
print(results.winner)  # "B"
print(results.lift)    # 14.9
print(results.recommendation)  # "Variant B showed 14.9% improvement..."
```

---

## Production Deployment

### Storage Layer (PostgreSQL + Redis)

**PostgreSQL for conversions (append-only):**
```sql
CREATE TABLE conversions (
    id BIGSERIAL PRIMARY KEY,
    lead_id VARCHAR NOT NULL,
    experiment_id VARCHAR NOT NULL,
    variant VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    value DECIMAL(10, 2),
    metadata JSONB
);

CREATE INDEX idx_conversions_exp_var 
ON conversions(experiment_id, variant, event_type);
```

**Redis for experiment config (cache):**
```python
# Cache experiment config
redis.set(
    f"agency:experiment:{exp_id}",
    json.dumps(config.dict()),
    ex=86400  # 24 hour TTL
)

# Redis HyperLogLog for unique lead counting
redis.pfadd(f"agency:experiment:{exp_id}:leads:{variant}", lead_id)
unique_count = redis.pfcount(f"agency:experiment:{exp_id}:leads:A")
```

### Webhook Integration

```python
@app.post("/webhooks/email-opened")
def email_opened_webhook(payload: EmailEvent):
    track_conversion(
        lead_id=payload.lead_id,
        experiment_id=payload.experiment_id,
        variant=payload.variant,
        event_type=ConversionEvent.OPENED,
        metadata={"provider": payload.provider}
    )
    return {"status": "recorded"}
```

### Daily Analysis Job

```python
from celery import Celery
from agent.utils.ab_testing import calculate_results

@celery.task
def analyze_active_experiments():
    experiments = Experiment.query.filter_by(status="RUNNING").all()
    
    for exp in experiments:
        results = calculate_results(
            experiment_id=exp.id,
            event_type=ConversionEvent.OPENED,
            control_variant="A"
        )
        
        if results.winner and results.lift > 10:
            send_alert(f"Experiment {exp.name} has a winner: {results.winner}")
```

---

## Implementation Status

**✅ Complete:**
- Core framework (`agent/utils/ab_testing.py` - 600+ lines)
- Full documentation
- Pydantic schemas with validation
- Deterministic variant assignment
- Statistical significance testing
- Confidence interval calculation

**⏳ Pending:**
- PostgreSQL storage integration
- Redis caching layer
- Webhook handlers
- Daily analysis job
- Dashboard UI

---

## Next Steps

### Short Term (Week 1)
1. ✅ Create framework skeleton
2. ✅ Write comprehensive documentation
3. Integrate variant assignment into RAG agent
4. Add AB_TESTING_EXPERIMENT environment variable support

### Medium Term (Week 2-3)
1. Implement PostgreSQL storage for conversions
2. Implement Redis cache for experiment configs
3. Create webhook handlers for conversion events
4. Build daily analysis job

### Long Term (Week 4+)
1. Dashboard UI for experiment results
2. Automatic winner detection and rollout
3. Multi-armed bandit strategy for ramp-up
4. Interleaved experiments (multiple parallel tests)
5. Causal inference for harder-to-measure impacts

---

**Implementation File:** `agent/utils/ab_testing.py` (600+ lines)  
**Last Updated:** November 9, 2025  
**Status:** Framework complete, storage layer pending
