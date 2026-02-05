"""
Audit Orchestrator Schemas

Defines all input/output models for the Audit Orchestrator including:
- Compliance rules and their types
- Audit violations and severity levels
- Audit trails for event tracking
- Reports for aggregated compliance status
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class RuleType(str, Enum):
    """
    Supported compliance rule types.

    Each rule type defines how the audit orchestrator evaluates compliance
    against the target payload.
    """

    # Data Completeness
    REQUIRED_FIELDS = "required_fields"
    """Check that required fields are present and non-empty."""

    # Content Filtering
    FORBIDDEN_TERMS = "forbidden_terms"
    """Flag content containing prohibited words/phrases."""

    # Email Compliance
    EMAIL_DOMAIN_BLOCKLIST = "email_domain_blocklist"
    """Block emails from/to specific domains (competitors, spam, etc.)."""

    # Numeric Validation
    NUMERIC_RANGE = "numeric_range"
    """Validate numeric fields fall within acceptable bounds."""

    # PII Detection
    PII_DETECTION = "pii_detection"
    """Detect personally identifiable information in specified fields."""

    # Data Freshness
    DATA_FRESHNESS = "data_freshness"
    """Check that timestamp fields are within acceptable age limits."""

    # Consent Verification
    CONSENT_REQUIRED = "consent_required"
    """Verify consent/opt-in flags are present and true."""

    # Rate Limiting
    RATE_LIMIT = "rate_limit"
    """Check that entity hasn't exceeded contact frequency limits."""

    # Format Validation
    FORMAT_VALIDATION = "format_validation"
    """Validate field format (email, phone, URL patterns)."""

    # Geographic Compliance
    GEOGRAPHIC_RESTRICTION = "geographic_restriction"
    """Check geographic restrictions (GDPR regions, etc.)."""


class Severity(str, Enum):
    """Violation severity levels for prioritization."""

    INFO = "info"
    """Informational only, no action required."""

    WARNING = "warning"
    """Should be reviewed but not blocking."""

    ERROR = "error"
    """Must be resolved before proceeding."""

    CRITICAL = "critical"
    """Immediate action required, potential legal/regulatory risk."""


class ComplianceRule(BaseModel):
    """
    Defines a single compliance rule to evaluate against a target payload.

    Rules are composable and can be combined in an AuditRequest to perform
    comprehensive compliance checks.

    Example - Required fields rule:
        ```python
        ComplianceRule(
            rule_id="req-001",
            type=RuleType.REQUIRED_FIELDS,
            fields=["email", "name", "company"],
            metadata={"category": "data_quality"}
        )
        ```

    Example - PII detection rule:
        ```python
        ComplianceRule(
            rule_id="pii-001",
            type=RuleType.PII_DETECTION,
            fields=["notes", "description"],
            patterns=["\\b\\d{3}-\\d{2}-\\d{4}\\b"],  # SSN pattern
            metadata={"regulation": "CCPA"}
        )
        ```
    """

    rule_id: str = Field(..., description="Unique rule identifier")
    type: str = Field(..., description="Rule type from RuleType enum")
    fields: List[str] = Field(default_factory=list, description="Target fields to inspect")
    terms: List[str] = Field(default_factory=list, description="Forbidden terms / blocklisted items")
    patterns: List[str] = Field(default_factory=list, description="Regex patterns for format/PII detection")
    min_value: Optional[float] = Field(None, description="Minimum numeric value")
    max_value: Optional[float] = Field(None, description="Maximum numeric value")
    max_age_hours: Optional[float] = Field(None, description="Maximum age for data freshness checks")
    allowed_regions: List[str] = Field(default_factory=list, description="Allowed geographic regions")
    blocked_regions: List[str] = Field(default_factory=list, description="Blocked geographic regions")
    rate_limit_count: Optional[int] = Field(None, description="Max contacts within rate_limit_hours")
    rate_limit_hours: Optional[float] = Field(None, description="Time window for rate limiting")
    severity_override: Optional[str] = Field(None, description="Override default severity for this rule")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AuditViolation(BaseModel):
    """
    Represents a single compliance violation detected during audit.

    Violations are categorized by severity and include enough context
    to locate and remediate the issue.
    """

    rule_id: str = Field(..., description="Rule identifier that failed")
    field: Optional[str] = Field(None, description="Field that triggered violation")
    message: str = Field(..., description="Human-readable violation summary")
    severity: str = Field(default="warning", description="Severity: info|warning|error|critical")
    value: Optional[Any] = Field(None, description="Actual value that triggered violation")
    expected: Optional[str] = Field(None, description="Expected value or format description")
    remediation: Optional[str] = Field(None, description="Suggested remediation action")
    regulation: Optional[str] = Field(None, description="Applicable regulation (GDPR, CCPA, etc.)")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="When violation was detected")


class AuditEvent(BaseModel):
    """
    Single event in an audit trail.

    Captures who did what, when, and with what context.
    """

    event_id: str = Field(..., description="Unique event identifier")
    action: str = Field(..., description="Action performed (create, update, delete, access, etc.)")
    actor: Optional[str] = Field(None, description="User/agent that performed the action")
    entity_type: Optional[str] = Field(None, description="Type of entity affected (lead, message, etc.)")
    entity_id: Optional[str] = Field(None, description="ID of affected entity")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When event occurred")
    before_state: Optional[Dict[str, Any]] = Field(None, description="State before action")
    after_state: Optional[Dict[str, Any]] = Field(None, description="State after action")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class AuditTrail(BaseModel):
    """
    Complete audit trail for an entity or operation.

    Provides chronological record of all actions taken, supporting
    compliance reporting and incident investigation.
    """

    trail_id: str = Field(..., description="Audit trail identifier")
    entity_id: Optional[str] = Field(None, description="Primary entity identifier")
    entity_type: Optional[str] = Field(None, description="Entity type (lead, campaign, etc.)")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Raw events (legacy format)")
    structured_events: List[AuditEvent] = Field(default_factory=list, description="Typed audit events")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Computed summary")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Trail creation time")
    last_updated: Optional[datetime] = Field(None, description="Last event timestamp")


class AuditReport(BaseModel):
    """
    Aggregated audit report with metrics and violations.

    Used for compliance dashboards, scheduled reports, and
    regulatory submissions.
    """

    report_id: Optional[str] = Field(None, description="Report identifier")
    status: str = Field(..., description="Report status: completed|completed_with_issues|failed")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Report generation time")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Aggregated metrics")
    violations: List[AuditViolation] = Field(default_factory=list, description="All violations found")
    violation_summary: Optional[Dict[str, int]] = Field(None, description="Violations by severity")
    compliance_score: Optional[float] = Field(None, description="Overall compliance score (0-100)")
    recommendations: List[str] = Field(default_factory=list, description="Remediation recommendations")


class AuditOperation(str, Enum):
    """Supported audit operations."""

    COMPLIANCE_CHECK = "compliance_check"
    """Run compliance rules against a target payload."""

    AUDIT_TRAIL = "audit_trail"
    """Generate audit trail from events."""

    AUDIT_REPORT = "audit_report"
    """Generate comprehensive audit report."""

    PRE_SEND_CHECK = "pre_send_check"
    """Pre-send compliance check before email/message dispatch."""

    DATA_QUALITY_CHECK = "data_quality_check"
    """Check data quality and completeness."""

    CONSENT_VERIFICATION = "consent_verification"
    """Verify consent/opt-in status."""


class AuditRequest(BaseModel):
    """
    Request for an audit operation.

    Supports multiple operation types for different audit use cases.

    Example - Pre-send compliance check:
        ```python
        AuditRequest(
            operation="pre_send_check",
            target={"to_email": "john@example.com", "body": "..."},
            rules=[
                ComplianceRule(
                    rule_id="blocklist-001",
                    type="email_domain_blocklist",
                    terms=["competitor.com", "spam.com"]
                ),
                ComplianceRule(
                    rule_id="forbidden-001",
                    type="forbidden_terms",
                    fields=["body", "subject"],
                    terms=["guarantee", "free money"]
                )
            ]
        )
        ```
    """

    operation: str = Field(..., description="Operation type from AuditOperation enum")
    target: Dict[str, Any] = Field(default_factory=dict, description="Target payload to audit")
    rules: List[ComplianceRule] = Field(default_factory=list, description="Compliance rules to apply")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Audit events for trail generation")
    entity_id: Optional[str] = Field(None, description="Entity identifier for context")
    entity_type: Optional[str] = Field(None, description="Entity type (lead, campaign, etc.)")
    tenant_id: Optional[str] = Field(None, description="Tenant identifier")
    campaign_id: Optional[str] = Field(None, description="Campaign identifier for campaign-level audits")
    fail_fast: bool = Field(default=False, description="Stop on first violation")
    persist_result: bool = Field(default=False, description="Persist audit result to database")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AuditResult(BaseModel):
    """
    Result of an audit operation.

    Contains violations found, audit trail if requested, and overall
    compliance status.
    """

    status: str = Field(..., description="success|error|blocked")
    passed: bool = Field(default=True, description="True if no blocking violations")
    violations: List[AuditViolation] = Field(default_factory=list, description="All violations found")
    blocking_violations: List[AuditViolation] = Field(default_factory=list, description="Only error/critical violations")
    trail: Optional[AuditTrail] = Field(None, description="Audit trail if requested")
    report: Optional[AuditReport] = Field(None, description="Audit report if requested")
    compliance_score: Optional[float] = Field(None, description="Overall compliance score (0-100)")
    error: Optional[str] = Field(None, description="Error message if status=error")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")


# Convenience type aliases
RuleList = List[ComplianceRule]
ViolationList = List[AuditViolation]


# Pre-built rule sets for common use cases
class CommonRuleSets:
    """
    Pre-built compliance rule sets for common use cases.

    Use these as templates or combine them for comprehensive audits.
    """

    @staticmethod
    def email_compliance() -> RuleList:
        """Rules for email sending compliance."""
        return [
            ComplianceRule(
                rule_id="email-required",
                type=RuleType.REQUIRED_FIELDS.value,
                fields=["to_email", "subject", "body"],
            ),
            ComplianceRule(
                rule_id="email-consent",
                type=RuleType.CONSENT_REQUIRED.value,
                fields=["opt_in", "email_consent"],
            ),
        ]

    @staticmethod
    def lead_data_quality() -> RuleList:
        """Rules for lead data quality validation."""
        return [
            ComplianceRule(
                rule_id="lead-required",
                type=RuleType.REQUIRED_FIELDS.value,
                fields=["email", "name"],
            ),
            ComplianceRule(
                rule_id="lead-email-format",
                type=RuleType.FORMAT_VALIDATION.value,
                fields=["email"],
                patterns=[r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"],
            ),
        ]

    @staticmethod
    def gdpr_compliance() -> RuleList:
        """Rules for GDPR compliance."""
        return [
            ComplianceRule(
                rule_id="gdpr-consent",
                type=RuleType.CONSENT_REQUIRED.value,
                fields=["gdpr_consent", "marketing_consent"],
                metadata={"regulation": "GDPR"},
            ),
            ComplianceRule(
                rule_id="gdpr-pii",
                type=RuleType.PII_DETECTION.value,
                fields=["notes", "description", "body"],
                metadata={"regulation": "GDPR"},
            ),
        ]
