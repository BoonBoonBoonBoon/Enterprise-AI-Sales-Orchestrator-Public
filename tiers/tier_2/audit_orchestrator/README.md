# Audit Orchestrator - Tier 2

The Audit Orchestrator is a business logic orchestrator for compliance, data validation, and audit trail management. It ensures data quality and regulatory compliance across the Agentic System.

## Purpose

The Audit Orchestrator serves as a **compliance gateway** for the system:

1. **Pre-Send Compliance** - Validates outgoing emails against blocklists, forbidden terms, and consent requirements before dispatch
2. **Data Quality Validation** - Ensures leads and messages have required fields and valid formats
3. **Regulatory Compliance** - Enforces GDPR, CCPA, and other regulatory requirements
4. **Audit Trail Generation** - Creates immutable records of system actions for compliance reporting
5. **Compliance Reporting** - Aggregates metrics and violations for dashboards and audits

## Key Use Cases

### 1. Pre-Send Email Compliance Check

Before sending any email, the Outreach Orchestrator can invoke the Audit Orchestrator to validate:

- Recipient domain isn't blocklisted (competitors, spam traps)
- Email body doesn't contain forbidden terms ("guarantee", "free money", etc.)
- Lead has given consent for marketing communications
- Rate limits haven't been exceeded

```python
request = AuditRequest(
    operation="pre_send_check",
    target={
        "to_email": "john@competitor.com",
        "subject": "Special Offer",
        "body": "Get our guaranteed results...",
        "opt_in": True,
    },
    rules=[
        ComplianceRule(
            rule_id="blocklist-001",
            type="email_domain_blocklist",
            terms=["competitor.com", "spam-trap.com"],
        ),
        ComplianceRule(
            rule_id="forbidden-001",
            type="forbidden_terms",
            fields=["subject", "body"],
            terms=["guarantee", "free money", "risk-free"],
        ),
        ComplianceRule(
            rule_id="consent-001",
            type="consent_required",
            fields=["opt_in", "email_consent"],
        ),
    ],
)
```

### 2. Lead Data Quality Validation

Validate incoming leads have required data and proper formats:

```python
request = AuditRequest(
    operation="data_quality_check",
    target={
        "email": "invalid-email",
        "name": "",
        "company": "Acme Inc",
    },
    rules=[
        ComplianceRule(
            rule_id="required-001",
            type="required_fields",
            fields=["email", "name"],
        ),
        ComplianceRule(
            rule_id="format-001",
            type="format_validation",
            fields=["email"],
            patterns=[r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"],
        ),
    ],
)
```

### 3. GDPR Compliance Check

Verify consent and detect PII before processing EU contacts:

```python
request = AuditRequest(
    operation="compliance_check",
    target={
        "email": "hans@example.de",
        "country": "DE",
        "gdpr_consent": False,
        "notes": "SSN: 123-45-6789",  # PII detected!
    },
    rules=[
        ComplianceRule(
            rule_id="gdpr-consent",
            type="consent_required",
            fields=["gdpr_consent"],
            metadata={"regulation": "GDPR"},
        ),
        ComplianceRule(
            rule_id="gdpr-pii",
            type="pii_detection",
            fields=["notes", "description"],
            patterns=[r"\b\d{3}-\d{2}-\d{4}\b"],  # SSN pattern
            metadata={"regulation": "GDPR"},
        ),
    ],
)
```

### 4. Audit Trail for Compliance Reporting

Generate audit trails for incident investigation or regulatory submissions:

```python
request = AuditRequest(
    operation="audit_trail",
    entity_id="lead-12345",
    entity_type="lead",
    events=[
        {"action": "create", "actor": "import_agent", "timestamp": "2026-01-15T10:00:00Z"},
        {"action": "enrich", "actor": "rag_agent", "timestamp": "2026-01-15T10:05:00Z"},
        {"action": "email_sent", "actor": "outreach", "timestamp": "2026-01-16T09:00:00Z"},
    ],
)
```

## Supported Rule Types

| Rule Type                | Purpose                                      | Key Fields                           |
| ------------------------ | -------------------------------------------- | ------------------------------------ |
| `required_fields`        | Check for missing/empty required fields      | `fields`                             |
| `forbidden_terms`        | Flag content with prohibited words           | `fields`, `terms`                    |
| `email_domain_blocklist` | Block emails to/from specific domains        | `terms`                              |
| `numeric_range`          | Validate numeric values within bounds        | `fields`, `min_value`, `max_value`   |
| `pii_detection`          | Detect PII patterns (SSN, credit card, etc.) | `fields`, `patterns`                 |
| `data_freshness`         | Check timestamp fields aren't stale          | `fields`, `max_age_hours`            |
| `consent_required`       | Verify consent/opt-in flags are true         | `fields`                             |
| `format_validation`      | Validate field formats (email, phone, etc.)  | `fields`, `patterns`                 |
| `geographic_restriction` | Block/allow by geographic region             | `allowed_regions`, `blocked_regions` |

## Architecture

```
audit_orchestrator/
├── __init__.py                      # Public API exports
├── audit_orchestrator.py            # Core orchestration logic
├── audit_orchestrator_harness.py    # Harness wrapper for Redis
├── consumer.py                      # Redis stream consumer
├── schemas/
│   └── __init__.py                  # Pydantic models (rules, violations, reports)
├── tests/                           # Unit tests
└── tools/                           # Audit-specific tools
```

## Usage

### Direct Usage (for testing)

```python
from tiers.tier_2.audit_orchestrator import AuditOrchestrator
from tiers.tier_2.audit_orchestrator.schemas import AuditRequest, ComplianceRule

orchestrator = AuditOrchestrator()
result = await orchestrator.process_task(envelope)
```

### Via Redis Streams (production)

```bash
python -m tiers.tier_2.audit_orchestrator.consumer
```

### From Other Orchestrators

The Outreach Orchestrator can delegate to Audit before sending:

```python
# In OutreachOrchestrator
audit_result = await self._delegate_to_audit(
    operation="pre_send_check",
    target=email_payload,
    rules=self._get_email_compliance_rules(),
)
if not audit_result.passed:
    return create_error_envelope(
        original=envelope,
        error_msg=f"Compliance check failed: {audit_result.blocking_violations}",
        code="COMPLIANCE_BLOCKED",
    )
```

## Redis Streams

| Direction  | Stream                                 |
| ---------- | -------------------------------------- |
| **Input**  | `{tenant}:orchestrators:audit:tasks`   |
| **Output** | `{tenant}:orchestrators:audit:results` |

## Response Structure

The `AuditResult` contains:

```python
class AuditResult:
    status: str           # "success" | "blocked" | "error"
    passed: bool          # True if no blocking violations
    violations: list      # All violations found
    blocking_violations: list  # Only error/critical violations
    compliance_score: float    # 0-100 score based on violations
    report: AuditReport   # Full report with metrics
```

## Violation Severities

| Severity   | Meaning                 | Blocks Processing?                 |
| ---------- | ----------------------- | ---------------------------------- |
| `info`     | Informational only      | No                                 |
| `warning`  | Should review           | No (unless `fail_on_warning=True`) |
| `error`    | Must resolve            | **Yes**                            |
| `critical` | Immediate action needed | **Yes**                            |

## Configuration

```python
config = {
    "default_rules": [],        # Rules applied when none specified
    "fail_on_warning": False,   # Treat warnings as blocking
}
```

## Implementation Status

✅ **ACTIVE** - Core implementation complete

- [x] Compliance rule engine with 9 rule types
- [x] Audit trail generation
- [x] Compliance scoring (0-100)
- [x] Report generation with recommendations
- [x] Pydantic schemas for all inputs/outputs
- [x] Redis stream consumer
- [ ] Persistence of audit results (planned)
- [ ] Scheduled compliance reports (planned)
- [ ] Integration with portal dashboard (planned)
