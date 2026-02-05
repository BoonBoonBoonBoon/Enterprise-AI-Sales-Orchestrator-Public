# Audit Orchestrator

The Audit Orchestrator is a Tier 2 component that provides compliance validation, data quality checks, and audit trail management across the Agentic System.

## Overview

| Property        | Value                                                   |
| --------------- | ------------------------------------------------------- |
| **Tier**        | 2 (Orchestration)                                       |
| **Stream**      | `{tenant}:orchestrators:audit:tasks`                    |
| **Uses Agents** | PersistenceAgent (for trail storage)                    |
| **Core File**   | `tiers/tier_2/audit_orchestrator/audit_orchestrator.py` |

## Purpose

The Audit Orchestrator serves as the **compliance gateway** for the entire system:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AUDIT ORCHESTRATOR                               │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Pre-Send    │  │    Data      │  │   Audit      │              │
│  │  Compliance  │  │   Quality    │  │   Trail      │              │
│  │    Check     │  │  Validation  │  │  Generation  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         ▼                 ▼                 ▼                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │              COMPLIANCE RULE ENGINE                        │    │
│  │  • Required Fields    • Forbidden Terms   • PII Detection │    │
│  │  • Domain Blocklist   • Consent Required  • Data Freshness│    │
│  │  • Numeric Range      • Format Validation • Geo Restrict  │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Responsibilities

1. **Pre-Send Compliance** - Validate emails before dispatch
2. **Data Quality** - Ensure leads have required fields and valid formats
3. **Regulatory Compliance** - Enforce GDPR, CCPA, CAN-SPAM requirements
4. **Audit Trails** - Create immutable records for compliance reporting
5. **Compliance Scoring** - Calculate 0-100 compliance scores

## Use Cases

### Pre-Send Email Compliance

Before the Outreach Orchestrator sends any email, it can validate:

- Recipient domain isn't on the blocklist
- Email content doesn't contain forbidden terms
- Lead has valid consent for marketing
- Rate limits haven't been exceeded

```json
{
  "operation": "pre_send_check",
  "target": {
    "to_email": "john@example.com",
    "subject": "Special Offer",
    "body": "Check out our latest...",
    "opt_in": true
  },
  "rules": [
    {
      "rule_id": "blocklist-001",
      "type": "email_domain_blocklist",
      "terms": ["competitor.com", "spam-trap.com"]
    },
    {
      "rule_id": "consent-001",
      "type": "consent_required",
      "fields": ["opt_in"]
    }
  ]
}
```

**Result:**

```json
{
  "status": "success",
  "passed": true,
  "violations": [],
  "compliance_score": 100.0
}
```

### Lead Data Quality Check

Validate incoming leads before processing:

```json
{
  "operation": "data_quality_check",
  "target": {
    "email": "invalid-email",
    "name": "",
    "company": "Acme Inc"
  },
  "rules": [
    {
      "rule_id": "required-001",
      "type": "required_fields",
      "fields": ["email", "name"]
    },
    {
      "rule_id": "format-001",
      "type": "format_validation",
      "fields": ["email"],
      "patterns": ["^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"]
    }
  ]
}
```

**Result:**

```json
{
  "status": "blocked",
  "passed": false,
  "violations": [
    {
      "rule_id": "required-001",
      "field": "name",
      "message": "Missing required field: name",
      "severity": "error"
    },
    {
      "rule_id": "format-001",
      "field": "email",
      "message": "Invalid format for email",
      "severity": "warning"
    }
  ],
  "compliance_score": 80.0
}
```

### GDPR Compliance Check

Verify EU contacts have proper consent and no PII in free-text fields:

```json
{
  "operation": "compliance_check",
  "target": {
    "email": "hans@example.de",
    "country": "DE",
    "gdpr_consent": false,
    "notes": "SSN: 123-45-6789"
  },
  "rules": [
    {
      "rule_id": "gdpr-consent",
      "type": "consent_required",
      "fields": ["gdpr_consent"],
      "metadata": { "regulation": "GDPR" }
    },
    {
      "rule_id": "gdpr-pii",
      "type": "pii_detection",
      "fields": ["notes"],
      "metadata": { "regulation": "GDPR" }
    }
  ]
}
```

### Audit Trail Generation

Create audit trails for compliance reporting:

```json
{
  "operation": "audit_trail",
  "entity_id": "lead-12345",
  "entity_type": "lead",
  "events": [
    {
      "action": "create",
      "actor": "import_agent",
      "timestamp": "2026-01-15T10:00:00Z"
    },
    {
      "action": "enrich",
      "actor": "rag_agent",
      "timestamp": "2026-01-15T10:05:00Z"
    },
    {
      "action": "email_sent",
      "actor": "outreach",
      "timestamp": "2026-01-16T09:00:00Z"
    }
  ]
}
```

## Supported Rule Types

| Rule Type                | Purpose                         | Required Fields                      | Example             |
| ------------------------ | ------------------------------- | ------------------------------------ | ------------------- |
| `required_fields`        | Check for missing required data | `fields`                             | `["email", "name"]` |
| `forbidden_terms`        | Block prohibited content        | `fields`, `terms`                    | Spam keywords       |
| `email_domain_blocklist` | Block specific email domains    | `terms`                              | Competitors         |
| `numeric_range`          | Validate numeric bounds         | `fields`, `min_value`, `max_value`   | Price limits        |
| `pii_detection`          | Detect SSN, credit cards, etc.  | `fields`, `patterns`                 | GDPR/CCPA           |
| `data_freshness`         | Check for stale data            | `fields`, `max_age_hours`            | 24h freshness       |
| `consent_required`       | Verify opt-in flags             | `fields`                             | Marketing consent   |
| `format_validation`      | Validate email/phone formats    | `fields`, `patterns`                 | RFC 5322 email      |
| `geographic_restriction` | Block/allow by region           | `allowed_regions`, `blocked_regions` | EU-only             |

## Violation Severities

| Severity   | Description                                       | Blocks Processing? |
| ---------- | ------------------------------------------------- | ------------------ |
| `info`     | Informational, no action needed                   | No                 |
| `warning`  | Should review but not blocking                    | No                 |
| `error`    | Must resolve before proceeding                    | **Yes**            |
| `critical` | Immediate action required (legal/regulatory risk) | **Yes**            |

## Compliance Scoring

The orchestrator calculates a compliance score (0-100) based on violation severity:

| Severity   | Penalty |
| ---------- | ------- |
| `info`     | -1      |
| `warning`  | -5      |
| `error`    | -15     |
| `critical` | -30     |

Score = max(0, 100 - total_penalty)

## Integration with Other Orchestrators

### From Outreach Orchestrator

```python
# Before sending email
audit_result = await self._delegate_to_audit(
    operation="pre_send_check",
    target=email_payload,
    rules=email_compliance_rules,
)

if not audit_result.passed:
    logger.warning(f"Email blocked: {audit_result.blocking_violations}")
    return create_error_envelope(...)
```

### From Leads Orchestrator

```python
# During lead qualification
audit_result = await self._delegate_to_audit(
    operation="data_quality_check",
    target=lead_data,
    rules=data_quality_rules,
)

if audit_result.compliance_score < 70:
    return route_to_manual_review(lead_data)
```

## Redis Streams

| Direction  | Stream                                 |
| ---------- | -------------------------------------- |
| **Input**  | `{tenant}:orchestrators:audit:tasks`   |
| **Output** | `{tenant}:orchestrators:audit:results` |

## Running the Consumer

```bash
python -m tiers.tier_2.audit_orchestrator.consumer
```

## Configuration

```python
from tiers.tier_2.audit_orchestrator import AuditOrchestrator

orchestrator = AuditOrchestrator(config={
    "default_rules": [],        # Applied when no rules specified
    "fail_on_warning": False,   # Treat warnings as blocking
})
```

## Pre-built Rule Sets

The schemas module provides common rule sets:

```python
from tiers.tier_2.audit_orchestrator.schemas import CommonRuleSets

# Email compliance rules
email_rules = CommonRuleSets.email_compliance()

# Lead data quality rules
quality_rules = CommonRuleSets.lead_data_quality()

# GDPR compliance rules
gdpr_rules = CommonRuleSets.gdpr_compliance()
```

## Implementation Status

| Feature                      | Status      |
| ---------------------------- | ----------- |
| Compliance rule engine       | ✅ Complete |
| 9 rule types                 | ✅ Complete |
| Compliance scoring           | ✅ Complete |
| Audit trail generation       | ✅ Complete |
| Report generation            | ✅ Complete |
| Redis consumer               | ✅ Complete |
| Persistence of results       | 🚧 Planned  |
| Portal dashboard integration | 🚧 Planned  |

## Related Documentation

- [Outreach Orchestrator](outreach.md) - Uses audit for pre-send checks
- [Leads Orchestrator](leads.md) - Uses audit for data quality
- [Environment Variables](../../reference/config/env-vars.md) - Configuration options
