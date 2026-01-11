# Model Switching Strategy & Configuration

**Purpose:** Guide for selecting between OpenAI models based on campaign requirements

---

## Model Comparison Matrix

| Feature | gpt-4o-mini | gpt-3.5-turbo | gpt-4o |
|---------|-------------|---------------|--------|
| **Cost/Email** | $0.000066 | $0.000192 | $0.001 |
| **Speed** | Fast | Fastest | Slower |
| **Quality** | Good | Good | Excellent |
| **Reasoning** | Excellent | Good | Best |
| **Creativity** | Good | Medium | Excellent |
| **Best For** | Volume | Budget | Quality |

---

## Decision Matrix - Which Model to Use

### High-Volume Campaigns (10k+ daily)
```
Recommendation: gpt-4o-mini
Reasoning: Best cost-quality balance
Cost: $6.60 per 10k emails
Monthly (300k): $19.75
Temperature: 0.65
Max Tokens: 280
```

### Budget-Conscious Campaigns (cost-first)
```
Recommendation: gpt-3.5-turbo
Reasoning: Cheapest alternative if mini doesn't work
Cost: $1.92 per 10k emails (3x more expensive than mini)
Monthly (300k): $57.60
Temperature: 0.65
Max Tokens: 250
Note: Only use if mini fails or specific need
```

### High-Value Leads (1k-5k daily)
```
Recommendation: gpt-4o-mini for volume, gpt-4o for premium
Split: 80% gpt-4o-mini, 20% gpt-4o
Cost: $50-100/month
Quality: Excellent for premium, good for standard
Temperature: 0.65 (mini), 0.7 (gpt-4o)
```

### Premium Quality Only
```
Recommendation: gpt-4o
Reasoning: Best quality for critical campaigns
Cost: $10.00 per 10k emails
Monthly (300k): $300.00
Temperature: 0.75
Max Tokens: 350
Use Only: Executive outreach, VIP prospects
```

---

## Implementation Strategy

### Default Configuration
```python
# Default: Maximum value for cost
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.65
DEFAULT_MAX_TOKENS = 280
```

### Per-Campaign Selection
```python
def select_model_for_campaign(campaign_config):
    lead_tier = campaign_config.get("lead_tier", "standard")
    volume = campaign_config.get("estimated_volume", 1000)
    quality_requirement = campaign_config.get("quality", "medium")
    
    # Tier-based selection
    if lead_tier == "vip":
        return "gpt-4o"  # Premium model
    elif lead_tier == "enterprise":
        return "gpt-4o-mini"  # Good quality, cost-effective
    else:  # SMB or prospect
        if volume > 10000 and quality_requirement == "low":
            return "gpt-3.5-turbo"  # Budget option
        else:
            return "gpt-4o-mini"  # Default best value
```

### Per-Lead Selection
```python
def select_model_for_lead(lead_data):
    lead_value = estimate_deal_size(lead_data)
    
    if lead_value > 100_000:  # Enterprise
        return "gpt-4o"
    elif lead_value > 10_000:  # Mid-market
        return "gpt-4o-mini"
    else:  # SMB/Prospect
        return "gpt-4o-mini"  # Default still good value
```

### Per-Tone Selection
```python
TONE_SETTINGS = {
    "professional": {
        "model": "gpt-4o-mini",
        "temperature": 0.60,
        "max_tokens": 280
    },
    "casual": {
        "model": "gpt-4o-mini",
        "temperature": 0.75,
        "max_tokens": 300
    },
    "creative": {
        "model": "gpt-4o",  # Higher quality for creative
        "temperature": 0.85,
        "max_tokens": 400
    },
    "technical": {
        "model": "gpt-4o-mini",
        "temperature": 0.55,
        "max_tokens": 350
    }
}
```

---

## Temperature Tuning Per Use Case

### Conservative (0.5-0.6)
```
Use Case: Legal, compliance, technical
Characteristics: Consistent, precise, factual
Examples: Technical product descriptions, legal terms, support docs
```

### Professional (0.6-0.7)
```
Use Case: B2B outreach, business communication
Characteristics: Professional, clear, persuasive
Examples: Cold emails, follow-ups, product pitches
```

### Balanced (0.7-0.75)
```
Use Case: Marketing copy, social media, general emails
Characteristics: Engaging, natural, personable
Examples: Campaign emails, brand voice, newsletters
```

### Creative (0.8-0.9)
```
Use Case: Brainstorming, creative campaigns, brand voice
Characteristics: Original, unique, compelling
Examples: Campaign headlines, creative briefs, thought leadership
```

---

## Recommended Configurations

### Scenario 1: Cold Email Campaign (10k daily)
```
Model: gpt-4o-mini
Temperature: 0.65
Max Tokens: 280
Cost: $6.60/day, $198/month
Quality: Good
Speed: Fast
Recommendation: GO WITH THIS
```

### Scenario 2: Premium Account Campaign (500 daily)
```
Model: gpt-4o
Temperature: 0.70
Max Tokens: 320
Cost: $5/day, $150/month
Quality: Excellent
Speed: Medium
Recommendation: Worth premium for high-value deals
```

### Scenario 3: Mixed Tier Campaign
```
VIP Tier (20%): gpt-4o
Standard Tier (80%): gpt-4o-mini
Overall Cost: $16.50/10k emails
Blended Quality: Very Good
Recommendation: OPTIMAL BALANCE
```

### Scenario 4: Budget-First Campaign (50k daily)
```
Model: gpt-3.5-turbo
Temperature: 0.65
Max Tokens: 250
Cost: $9.60/day, $288/month
Quality: Good
Speed: Very Fast
Recommendation: Only if cost is absolute priority
Note: Not recommended - gpt-4o-mini is better value
```

---

## Cost-Quality Tradeoff Analysis

### Question: When is GPT-4 Worth It?

**Answer:** When lead value > 15x the model cost difference

```
Cost Difference: gpt-4 vs gpt-4o-mini = $0.000934/email
If lead value is > $0.014: Worth using gpt-4

Example:
- Deal value: $50,000
- Lead-to-close rate: 5%
- Expected value: $2,500
- Cost of premium model: $0.001
- ROI: 2,500,000% = WORTH IT
```

### Guidelines:

```
Deal Value < $1,000:   Use gpt-4o-mini (never use gpt-4)
Deal Value $1k-$10k:   Use gpt-4o-mini (quality gap not worth cost)
Deal Value $10k-$50k:  Consider gpt-4 (might improve conversion 2-5%)
Deal Value > $50k:     Use gpt-4 (premium quality justified)
```

---

## A/B Testing Matrix

### Test 1: Model Comparison (Week 1)
```
Variant A: gpt-4o-mini (temperature 0.65)
Variant B: gpt-3.5-turbo (temperature 0.65)
Metric: Open rate, reply rate, MQL rate
Sample: 1000 leads each
Expected: gpt-4o-mini wins (better quality, similar cost)
```

### Test 2: Temperature Optimization (Week 2)
```
Variant A: gpt-4o-mini (temperature 0.55)
Variant B: gpt-4o-mini (temperature 0.65)
Variant C: gpt-4o-mini (temperature 0.75)
Metric: Engagement, conversion
Sample: 500 leads each
Expected: 0.65 wins for professional tone
```

### Test 3: Tone Variations (Week 3)
```
Variant A: Professional (0.65 temp, mini)
Variant B: Casual (0.75 temp, mini)
Variant C: Persuasive (0.70 temp, 4o)
Metric: Click-through rate, reply rate
Sample: 1000 leads each
Expected: Professional wins for B2B
```

### Test 4: Model by Lead Tier (Week 4)
```
SMB Leads:
- Variant A: gpt-4o-mini (80% of budget)
- Variant B: gpt-3.5-turbo (50% of budget)

Enterprise Leads:
- Variant A: gpt-4o-mini (80% of budget)
- Variant B: gpt-4o (premium)

Metric: Conversion rate by tier
Expected: gpt-4o-mini best for all
```

---

## When to Switch Models

### Switch FROM Mini TO 3.5-Turbo WHEN:
- Cost absolutely critical (rare)
- Volume > 50k daily and budget exhausted
- Only if mini-caused quality issues persist
- **Recommendation: Unlikely scenario, stick with mini**

### Switch FROM Mini TO 4o WHEN:
- VIP/Enterprise deals (>$50k value)
- Campaign conversion critical
- Brand reputation on the line
- A/B testing shows 3+ point lift
- **Recommendation: Use sparingly for premium segment**

### Switch FROM 3.5-Turbo BACK TO Mini WHEN:
- Cost becomes manageable
- Quality issues appear
- Volume management becomes priority
- A/B testing shows mini outperforms
- **Recommendation: Always switch back to mini (better value)**

---

## Cost Optimization Tips

### Tip 1: Use gpt-4o-mini as Default
- 3x cheaper than 3.5-turbo
- Better quality than 3.5-turbo
- Use for 95% of emails

### Tip 2: Reserve gpt-4o for Premium Only
- Only for enterprise/VIP deals
- Allocate 5-20% of volume to premium
- Measure ROI carefully

### Tip 3: Optimize Token Usage
```
Current max_tokens: 300
Actual usage: 233
Target: 280 (save 10% tokens)
Potential savings: $2 per 10k emails
```

### Tip 4: Batch Processing
- Send 100 emails at once
- No per-request overhead
- Parallel processing possible
- Cost savings: 5-10%

### Tip 5: Cache Prompts
- Reuse system prompts
- Only change lead-specific data
- Reduce prompt tokens by 50%
- Cost savings: 20-30%

---

## Monitoring & Alerts

### Daily Monitoring
```
- Total emails generated today
- Cost per email (should be < $0.0001)
- Model distribution (% mini vs 3.5 vs 4o)
- API response time (should be < 3s)
```

### Weekly Review
```
- Total cost vs budget
- Quality metrics (open rate, reply rate)
- Model performance comparison
- Temperature effectiveness
```

### Monthly Review
```
- Cost trend (should be flat or down)
- ROI by model
- A/B test results
- Model selection effectiveness
```

---

## Implementation Checklist

- [ ] Set gpt-4o-mini as default model
- [ ] Configure temperature to 0.65 for B2B
- [ ] Set max_tokens to 280 (save 10%)
- [ ] Implement model selection logic by lead tier
- [ ] Set up cost tracking and alerts
- [ ] Configure A/B testing framework
- [ ] Document model decisions in campaign configs
- [ ] Monitor quality metrics weekly
- [ ] Run monthly optimization review

---

## Questions & Answers

**Q: Should we always use gpt-4o-mini?**
A: Yes, 95% of the time. Only use 4o for premium leads (>$50k value).

**Q: Is temperature 0.65 best for all campaigns?**
A: 0.65 is good for B2B. Test 0.55-0.75 range for your specific use cases.

**Q: When should we use gpt-3.5-turbo?**
A: Rarely. gpt-4o-mini is 3x cheaper AND better quality. Only if absolutely budget-constrained.

**Q: How do we know if a model is working well?**
A: Track open rate, reply rate, and conversion. Compare to baseline. Use A/B testing.

**Q: Can we change models mid-campaign?**
A: Yes, but track model used in database so you can A/B test properly.

---

**Status:** Ready for implementation  
**Next Step:** Configure model selection logic in copywriter worker
