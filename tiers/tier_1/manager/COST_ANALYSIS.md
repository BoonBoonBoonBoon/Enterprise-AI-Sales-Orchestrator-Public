# Manager Agent - Cost Analysis & Optimization Guide

**Last Updated**: November 18, 2025  
**Owner**: Tier 1 Manager Team  
**Status**: Active monitoring required

---

## Executive Summary

The Manager Agent uses a **multi-tier fallback architecture** designed to minimize LLM costs while maintaining reliability. Current implementation routes 30-70% of requests through free shortcuts, with deterministic rules handling most remaining traffic. LLM and deep-agent fallbacks are reserved for ambiguous or complex cases.

**Current estimated cost**: $900/month (10K executions/day, mixed workload)  
**Optimized target**: $47/month (95% reduction)  
**Key levers**: Shortcut coverage, LLM caching, fallback model selection, per-tenant quotas

---

## Cost Breakdown by Execution Path

### 1. Shortcut Path (Target: 70%+ coverage)

**Cost per execution**: $0  
**Latency**: <50ms  
**Token usage**: 0

**What it handles**:
- Simple calculations (`"What is 2 + 2?"`)
- Pattern-matched queries (`"Find leads in {industry}"`)
- Direct orchestrator routing (`"Start outreach campaign"`)
- Status checks (`"Check task {id}"`)

**Implementation**: [`ShortcutRegistry`](shortcut_registry.py)

**Current coverage**: Unknown (requires metrics)  
**Optimization target**: 70%+ of all requests

**Cost impact**:
- At 30% coverage: $0/day
- At 70% coverage: $0/day (but reduces load on expensive paths)

---

### 2. Deterministic Pipeline (Target: 25% of traffic)

**Cost per execution**: $0 (rules-only) to $0.0003 (with LLM fallback)  
**Latency**: 50-200ms  
**Components**:

#### 2a. Normalization + Rules Classification
- **Cost**: $0
- **Token usage**: 0
- **Files**: [`intake/normalizer.py`](intake/normalizer.py), [`intent/rules.py`](intent/rules.py)
- **Handles**: Structured inputs with clear intent signals

#### 2b. LLM Fallback (when `confidence < 0.5`)
- **Trigger condition**: Rules confidence < 50%
- **Model**: `gpt-4o-mini` (default, via `MANAGER_LLM_MODEL`)
- **Token usage**:
  - Input: 200-500 tokens (request context + system prompt)
  - Output: 50-100 tokens (intent + confidence + reasoning)
- **Cost per call**: $0.0001-0.0003
- **File**: [`intent/llm_fallback.py`](intent/llm_fallback.py)

**Pricing (gpt-4o-mini as of Nov 2024)**:
- Input: $0.150 per 1M tokens
- Output: $0.600 per 1M tokens
- Average cost: ~$0.0002/call

**Current behavior**:
- LLM auto-enabled when `OPENAI_API_KEY` is set
- Kill-switch: `MANAGER_LLM_ENABLED=0` to disable
- No caching (every similar request re-calls LLM)

**Optimization opportunities**:
1. **Response caching** (Redis): 50-80% reduction
2. **Confidence threshold tuning**: Lower to 0.3 → fewer LLM calls
3. **Embeddings-based pre-filter**: Catch near-duplicates before LLM

---

### 3. Deep Agent Fallback (Target: <5% of traffic)

**Cost per execution**: $0.02-0.05 (gpt-4o) or $0.002-0.005 (gpt-4o-mini)  
**Latency**: 2-10 seconds  
**Trigger**: Deterministic pipeline fails AND `enable_deep_agent=True`

**Token usage**:
- System prompt + tool definitions: 2,000-3,000 tokens
- User goal: 100-500 tokens
- Tool calls (2-5 per execution): 1,000-2,500 tokens
- Agent reasoning: 500-1,500 tokens output
- **Total**: ~3,500-6,500 input, ~500-1,500 output

**Pricing (gpt-4o)**:
- Input: $2.50 per 1M tokens
- Output: $10.00 per 1M tokens
- **Average cost**: ~$0.03/execution

**Pricing (gpt-4o-mini - recommended)**:
- Input: $0.150 per 1M tokens
- Output: $0.600 per 1M tokens
- **Average cost**: ~$0.003/execution (10x cheaper)

**Current model**: `gpt-4o` (configured in `__init__(model="gpt-4o")`)

**File**: [`deep_agent_factory.py`](deep_agent_factory.py)

**Optimization**:
- Switch to `gpt-4o-mini` for 90% cost reduction
- Most Manager decisions don't need gpt-4o reasoning
- Reserve gpt-4o for Tier-2/Tier-3 complex workflows

---

## Monthly Cost Projections

### Baseline Scenario (Current Implementation)
**Assumptions**:
- 10,000 executions/day (300K/month)
- Path distribution (unoptimized):
  - 30% shortcuts
  - 60% deterministic (20% trigger LLM)
  - 10% deep agent
- Models: gpt-4o-mini (LLM), gpt-4o (deep agent)

**Daily costs**:
- Shortcuts: 3,000 × $0 = **$0**
- Deterministic + LLM: 6,000 × 20% × $0.0002 = **$0.24**
- Deep agent: 1,000 × $0.03 = **$30.00**

**Monthly total**: ~**$900**

---

### Optimized Scenario (With Improvements)
**Assumptions**:
- Same volume (300K/month)
- Path distribution (optimized):
  - 70% shortcuts (improved registry)
  - 25% deterministic (10% trigger LLM via caching)
  - 5% deep agent
- Models: gpt-4o-mini for both LLM and deep agent

**Daily costs**:
- Shortcuts: 7,000 × $0 = **$0**
- Deterministic + LLM: 2,500 × 10% × $0.0002 = **$0.05**
- Deep agent: 500 × $0.003 = **$1.50**

**Monthly total**: ~**$47**

**Savings**: $853/month (95% reduction)

---

### High-Volume Scenario (100K/day)
**Assumptions**:
- 100,000 executions/day (3M/month)
- Optimized path distribution
- gpt-4o-mini for all LLM usage

**Daily costs**:
- Shortcuts: 70,000 × $0 = **$0**
- Deterministic + LLM: 25,000 × 10% × $0.0002 = **$0.50**
- Deep agent: 5,000 × $0.003 = **$15.00**

**Monthly total**: ~**$465**

---

## Optimization Strategies

### Immediate (30 minutes)

#### 1. Add Path Metrics
**Goal**: Understand current traffic distribution  
**Implementation**:
```python
# In manager_agent.py execute()
logger.info(json.dumps({
    "event": "manager.decision",
    "tenant_id": self.tenant_id,
    "path": path,  # shortcut | deterministic_pipeline | deep_agent_fallback
    "intent": intent,
    "confidence": confidence,
    "used_fallback": used_fallback,
    "latency_ms": latency_ms,
}))
```

**Value**: Baseline data for optimization decisions  
**Cost impact**: $0

---

#### 2. Switch Deep Agent Model to gpt-4o-mini
**Goal**: 90% cost reduction on deep agent calls  
**Implementation**:
```python
# In __init__:
deep_agent_model = os.getenv("MANAGER_DEEP_AGENT_MODEL", "gpt-4o-mini")
self.agent = create_manager_deep_agent(
    tools=self.tools,
    model=deep_agent_model,  # Changed from self.model_name
    ...
)
```

**Value**: $0.03 → $0.003 per deep agent execution  
**Cost impact**: -$870/month (baseline scenario)

---

#### 3. Add LLM Response Caching
**Goal**: Eliminate redundant LLM calls for similar inputs  
**Implementation**:
```python
# In intent/llm_fallback.py
def classify_with_llm(req: UnifiedManagerRequest) -> Tuple[str, float, List[str]]:
    # Generate cache key from normalized input
    cache_key = f"manager:intent:{hashlib.sha256(req.text.encode()).hexdigest()}"
    
    # Check cache
    cached = redis.get(cache_key)
    if cached:
        result = json.loads(cached)
        return result["intent"], result["confidence"], result["reasons"] + ["cached"]
    
    # ... call LLM ...
    
    # Store in cache (1 hour TTL)
    redis.setex(cache_key, 3600, json.dumps({
        "intent": intent,
        "confidence": conf,
        "reasons": reasons,
    }))
```

**Value**: 50-80% reduction in LLM calls  
**Cost impact**: -$0.12/day (~$36/month)

---

### Short-term (2 hours)

#### 4. Improve Shortcut Coverage
**Goal**: Route more requests through free path  
**Process**:
1. Log all deterministic pipeline requests for 7 days
2. Identify top 20 patterns (e.g., "find leads in X", "check status Y")
3. Add shortcuts for each pattern in `shortcut_registry.py`
4. Monitor coverage increase

**Target**: 30% → 70% shortcut coverage  
**Value**: Reduces load on expensive paths  
**Cost impact**: Indirect (enables other optimizations)

---

#### 5. Add Per-Tenant Budget Enforcement
**Goal**: Prevent cost overruns from single tenant  
**Implementation**:
```python
# In manager_agent.py execute()
def execute(self, task_data_or_goal, context=None):
    # Check tenant quota before expensive operations
    month_key = datetime.now().strftime("%Y-%m")
    spend_key = f"manager:spend:{self.tenant_id}:{month_key}"
    current_spend = float(self.redis.get(spend_key) or 0)
    
    budget_limit = float(os.getenv("MANAGER_TENANT_BUDGET_USD", "100"))
    if current_spend >= budget_limit:
        logger.warning(f"Tenant {self.tenant_id} exceeded budget: ${current_spend:.2f}")
        return {
            "success": False,
            "error": "quota_exceeded",
            "current_spend": current_spend,
            "budget_limit": budget_limit,
        }
    
    # ... normal execution ...
    
    # Track spend
    if path in ["deterministic_pipeline", "deep_agent_fallback"]:
        estimated_cost = 0.0002 if "llm" in reasons else 0.003 if path == "deep_agent" else 0
        self.redis.incrbyfloat(spend_key, estimated_cost)
        self.redis.expire(spend_key, 60 * 60 * 24 * 35)  # 35 days
```

**Value**: Cost predictability, prevent abuse  
**Cost impact**: $0 (enforcement only)

---

#### 6. Tune LLM Confidence Threshold
**Goal**: Reduce unnecessary LLM fallback calls  
**Implementation**:
```python
# In manager_agent.py execute()
LLM_THRESHOLD = float(os.getenv("MANAGER_LLM_CONFIDENCE_THRESHOLD", "0.5"))

if self.enable_llm_fallback and confidence < LLM_THRESHOLD:
    # ... LLM fallback ...
```

**Configuration**:
- Default: 0.5 (call LLM when rules confidence <50%)
- Aggressive: 0.3 (trust rules more, reduce LLM calls)
- Conservative: 0.7 (use LLM more often for accuracy)

**Value**: Fine-tune cost vs accuracy tradeoff  
**Cost impact**: ~20-40% reduction in LLM calls (at 0.3 threshold)

---

### Medium-term (1 day)

#### 7. Semantic Caching with Embeddings
**Goal**: Cache intent classification for semantically similar inputs  
**Architecture**:
```
Input → Generate embedding (sentence-transformers local model)
      → Check similarity to cached embeddings (cosine > 0.95)
      → Return cached intent if match
      → Otherwise, proceed to rules/LLM
```

**Implementation**:
- Model: `all-MiniLM-L6-v2` (local, no API cost)
- Storage: Redis with vector similarity (RedisSearch)
- Cache TTL: 7 days

**Value**: 70-90% cache hit rate for production traffic  
**Cost impact**: -$0.15/day (~$45/month)

---

#### 8. Tiered Fallback Strategy
**Goal**: Add cheap intermediate layer before expensive LLM  
**Architecture**:
```
Rules (free)
  ↓ if confidence < 0.5
Embeddings classifier (cheap, local)
  ↓ if confidence < 0.7
gpt-4o-mini LLM (medium cost)
  ↓ if still fails
Deep agent (expensive, last resort)
```

**Embeddings classifier**:
- Train on historical Manager decisions (intent labels)
- Use `sentence-transformers` + logistic regression
- Cost: $0 (runs locally)
- Accuracy: 85-90% on seen patterns

**Value**: Catches 60-80% of ambiguous cases before LLM  
**Cost impact**: -$0.18/day (~$54/month)

---

#### 9. Observability Dashboard
**Goal**: Real-time cost and performance monitoring  
**Metrics to track**:
- `manager.decisions.total` (counter, by path/intent/tenant)
- `manager.decision.latency_ms` (histogram)
- `manager.llm.calls.total` (counter)
- `manager.cost.estimated_usd` (counter, by tenant)
- `manager.confidence.avg` (gauge)

**Implementation**:
- Export to Prometheus/DataDog/CloudWatch
- Alert thresholds:
  - Deep agent usage >10% of traffic
  - Tenant daily spend >$10
  - LLM fallback rate >30%

**Value**: Proactive cost anomaly detection  
**Cost impact**: $0 (monitoring infrastructure only)

---

## Cost Control Guardrails

### 1. Rate Limiting
**Per-tenant limits**:
- 100 requests/minute (burst: 200)
- 10,000 requests/day
- Enforced at Manager consumer level

### 2. Circuit Breaker for LLM
**Trigger**: LLM error rate >20% over 5 minutes  
**Action**: Disable LLM fallback, route all to deterministic + default orchestrator  
**Recovery**: Auto-enable after 15 minutes

### 3. Deep Agent Quotas
**Default**: Disabled (`enable_deep_agent=False`)  
**When enabled**:
- Max 5% of tenant traffic
- Hard limit: 100 deep agent calls/day per tenant
- Override via `MANAGER_DEEP_AGENT_QUOTA`

### 4. Emergency Kill Switch
**Environment variable**: `MANAGER_COST_CONTROL_MODE`  
**Values**:
- `normal` (default): All features enabled
- `conservative`: Disable deep agent, LLM threshold → 0.3
- `emergency`: Shortcuts + deterministic only, no LLM/deep agent

---

## Monitoring & Alerts

### Key Performance Indicators (KPIs)

1. **Cost per 1K executions** (target: <$0.50)
2. **Shortcut hit rate** (target: >70%)
3. **LLM cache hit rate** (target: >60%)
4. **Deep agent usage** (target: <5%)
5. **Average latency** (target: <200ms p95)

### Alert Conditions

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Daily cost | >$5 | >$10 | Review tenant usage, check for abuse |
| Deep agent % | >8% | >15% | Investigate why deterministic failing |
| LLM fallback % | >30% | >50% | Improve rules coverage |
| Tenant spend | >$50/month | >$100/month | Enforce quota, contact customer |
| Error rate | >5% | >10% | Check Redis, LLM service health |

---

## Cost Attribution by Tenant

### Tracking Implementation
```python
# In manager_agent.py
decision_cost = 0.0

if "llm:openai" in reasons:
    decision_cost += 0.0002  # Estimated LLM call cost

if path == "deep_agent_fallback":
    decision_cost += 0.003  # gpt-4o-mini deep agent

# Log cost attribution
logger.info(json.dumps({
    "event": "manager.cost",
    "tenant_id": self.tenant_id,
    "execution_id": execution_id,
    "cost_usd": decision_cost,
    "path": path,
}))

# Persist to Redis for billing
month_key = datetime.now().strftime("%Y-%m")
cost_key = f"manager:cost:{self.tenant_id}:{month_key}"
self.redis.incrbyfloat(cost_key, decision_cost)
```

### Monthly Billing Query
```python
def get_tenant_monthly_cost(tenant_id: str, year_month: str) -> float:
    """Get total Manager cost for tenant in given month."""
    cost_key = f"manager:cost:{tenant_id}:{year_month}"
    return float(redis.get(cost_key) or 0)
```

---

## Optimization Roadmap

### Phase 1: Foundation (Week 1)
- [ ] Add path metrics logging
- [ ] Switch deep agent to gpt-4o-mini
- [ ] Implement LLM response caching
- [ ] Add per-tenant budget enforcement

**Expected savings**: 80% cost reduction

### Phase 2: Intelligence (Week 2-3)
- [ ] Improve shortcut coverage (target 70%)
- [ ] Add embeddings-based semantic caching
- [ ] Implement tiered fallback strategy
- [ ] Tune LLM confidence threshold

**Expected savings**: Additional 10-15% reduction

### Phase 3: Scale (Month 2)
- [ ] Deploy observability dashboard
- [ ] Set up cost anomaly alerts
- [ ] A/B test different model combinations
- [ ] Optimize prompt engineering for token efficiency

**Expected savings**: Maintain low costs at 10x scale

---

## Model Selection Guide

### When to use gpt-4o-mini
- ✅ Intent classification
- ✅ Simple routing decisions
- ✅ Confidence scoring
- ✅ Manager-level reasoning (most cases)
- ✅ Deep agent fallback (Manager tier)

**Cost**: ~$0.0002-0.003 per execution

### When to use gpt-4o
- ✅ Complex multi-step planning (rare Manager cases)
- ✅ Tier 2 orchestrators (campaign strategy, lead qualification)
- ✅ Tier 3 agents (copywriting, technical analysis)
- ❌ Manager intent classification (overkill)

**Cost**: ~$0.02-0.05 per execution

### When to use embeddings + local models
- ✅ Semantic similarity checks
- ✅ Duplicate detection
- ✅ Pre-filtering before LLM
- ✅ Intent classification (with training data)

**Cost**: $0 (compute only)

---

## FAQ

### Q: Why not disable LLM fallback entirely?
**A**: Handles edge cases and ambiguous inputs that rules miss. Adds ~$0.24/day but prevents routing failures that could cause customer issues.

### Q: Can we use GPT-3.5-turbo instead of gpt-4o-mini?
**A**: Deprecated as of Jan 2025. gpt-4o-mini is cheaper, faster, and more capable.

### Q: How do we handle cost spikes?
**A**: Circuit breakers, per-tenant quotas, and emergency kill switch provide automatic protection. Alerts notify team within 5 minutes of anomalies.

### Q: What's the ROI of semantic caching?
**A**: 70% cache hit rate saves ~$0.15/day ($54/month). Implementation cost: 4-6 hours. ROI: positive within first month.

### Q: Should we cache deep agent responses?
**A**: No. Deep agent handles complex, context-specific requests that are unlikely to repeat exactly. Cache would have low hit rate and risk stale responses.

---

## Change Log

| Date | Change | Impact |
|------|--------|--------|
| 2025-11-18 | Initial cost analysis document created | Baseline established |
| TBD | Implement LLM caching | -50% LLM costs |
| TBD | Switch deep agent to gpt-4o-mini | -90% deep agent costs |
| TBD | Improve shortcut coverage to 70% | -40% overall costs |

---

## References

- OpenAI Pricing: https://openai.com/api/pricing/
- Manager Agent Code: [`manager_agent.py`](manager_agent.py)
- Routing Config: [`../../config/manager/routing.yaml`](../../config/manager/routing.yaml)
- Cost Tracking: `tools/cost_analysis.py` (TODO)

---

**Next Review Date**: December 1, 2025  
**Owner**: @tier1-team  
**Escalation**: Costs >$15/day or error rate >10%
