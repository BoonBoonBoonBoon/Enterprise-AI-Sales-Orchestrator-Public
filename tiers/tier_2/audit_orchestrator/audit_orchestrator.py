"""
Audit Orchestrator Implementation

The Audit Orchestrator is a Tier 2 component responsible for:

1. **Compliance Monitoring** - Validates data against configurable rules before
   actions are taken (e.g., pre-send email checks, lead data quality).

2. **Data Validation** - Checks required fields, format validation, numeric
   ranges, and custom business rules.

3. **Audit Trail Generation** - Creates immutable records of system actions
   for compliance reporting and incident investigation.

4. **Report Generation** - Aggregates compliance metrics and violations into
   actionable reports for dashboards and regulatory submissions.

Key Use Cases:
- Pre-send compliance: Block emails to blocklisted domains or with forbidden content
- Lead quality: Validate required fields and data formats before processing
- GDPR/CCPA compliance: Verify consent and detect PII in free-text fields
- Rate limiting: Prevent over-contacting leads (configurable frequency limits)
- Geographic restrictions: Block outreach to restricted regions

Integration Points:
- Called by Outreach Orchestrator before email dispatch
- Called by Leads Orchestrator during lead qualification
- Manager can invoke directly for on-demand audits
- Scheduled tasks for periodic compliance reports
"""

from typing import Any, Dict, List, Optional
import logging
import re
import uuid
from datetime import datetime, timedelta

from core.envelope import Envelope, result as create_result_envelope, error as create_error_envelope

from tiers.tier_2.audit_orchestrator.schemas import (
    AuditRequest,
    AuditResult,
    AuditViolation,
    AuditTrail,
    AuditReport,
    AuditEvent,
    RuleType,
    Severity,
)

logger = logging.getLogger(__name__)

# Common PII patterns
PII_PATTERNS = {
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "phone_us": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
}


class AuditOrchestrator:
    """
    Tier 2 Orchestrator for audit operations.

    Coordinates audit-related tasks across the system including compliance
    checks, data validation, and audit trail management.

    The orchestrator is stateless and can process multiple concurrent requests.
    For persistent audit storage, it delegates to the Persistence Agent.

    Attributes:
        config: Configuration dictionary with optional settings:
            - default_rules: List of rules to apply when none specified
            - persist_violations: Whether to persist violations by default
            - fail_on_warning: Treat warnings as blocking violations
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Audit Orchestrator.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._default_rules = self.config.get("default_rules", [])
        self._fail_on_warning = self.config.get("fail_on_warning", False)
        logger.info("AuditOrchestrator initialized")

    async def process_task(self, envelope: Envelope) -> Envelope:
        """
        Process an audit task from the envelope.

        Supports the following operations:
        - compliance_check: Run rules against target payload
        - pre_send_check: Pre-send email compliance validation
        - data_quality_check: Validate data completeness and format
        - consent_verification: Verify consent/opt-in flags
        - audit_trail: Generate audit trail from events
        - audit_report: Full compliance report with trail and violations

        Args:
            envelope: Task envelope containing audit request

        Returns:
            Envelope with audit results
        """
        logger.info(f"Processing audit task: {envelope.metadata.task_id}")

        try:
            request = AuditRequest(**(envelope.payload or {}))
        except Exception as exc:
            return create_error_envelope(
                original=envelope,
                error_msg=f"invalid_audit_request: {exc}",
                source="orchestrators:audit",
                code="AUDIT_VALIDATION_ERROR",
            )

        violations: List[AuditViolation] = []
        trail: Optional[AuditTrail] = None
        report: Optional[AuditReport] = None

        operation = request.operation.lower()

        if operation in ("compliance_check", "pre_send_check", "data_quality_check", "consent_verification"):
            violations = self._run_compliance_checks(request)
            blocking = [v for v in violations if v.severity in ("error", "critical")]
            if self._fail_on_warning:
                blocking.extend([v for v in violations if v.severity == "warning"])

            compliance_score = self._calculate_compliance_score(violations)
            report = AuditReport(
                report_id=f"rpt_{uuid.uuid4().hex[:8]}",
                status="completed" if not blocking else "completed_with_issues",
                metrics={"violations": len(violations), "blocking": len(blocking)},
                violations=violations,
                violation_summary=self._summarize_by_severity(violations),
                compliance_score=compliance_score,
            )
        elif operation == "audit_trail":
            trail = self._generate_audit_trail(request)
            report = AuditReport(
                report_id=f"rpt_{uuid.uuid4().hex[:8]}",
                status="completed",
                metrics=trail.summary if trail else {},
                violations=[],
            )
        elif operation == "audit_report":
            trail = self._generate_audit_trail(request)
            violations = self._run_compliance_checks(request)
            report = self._build_report(trail, violations)
        else:
            return create_error_envelope(
                original=envelope,
                error_msg=f"unsupported_operation: {request.operation}",
                source="orchestrators:audit",
                code="AUDIT_UNSUPPORTED_OPERATION",
            )

        blocking_violations = [v for v in violations if v.severity in ("error", "critical")]
        passed = len(blocking_violations) == 0

        result = AuditResult(
            status="success" if passed else "blocked",
            passed=passed,
            violations=violations,
            blocking_violations=blocking_violations,
            trail=trail,
            report=report,
            compliance_score=report.compliance_score if report else None,
        )

        return create_result_envelope(
            original=envelope,
            payload=result.model_dump(),
            source="orchestrators:audit",
        )

    async def run_compliance_check(self, target: str, rules: List[str]) -> Dict[str, Any]:
        """
        Run compliance check against specified rules.
        
        Args:
            target: Target entity/data to audit
            rules: List of compliance rules to check
            
        Returns:
            Compliance check results
        """
        violations = [
            AuditViolation(
                rule_id="legacy_rule",
                field=None,
                message="Legacy compliance check invoked; use structured AuditRequest.",
                severity="info",
            )
        ]
        return {
            "target": target,
            "rules": rules,
            "status": "completed",
            "violations": [v.model_dump() for v in violations],
        }

    async def generate_audit_trail(self, entity_id: str, actions: List[Dict]) -> str:
        """
        Generate audit trail for entity actions.
        
        Args:
            entity_id: Entity identifier
            actions: List of actions to audit
            
        Returns:
            Audit trail ID
        """
        return f"audit_trail_{entity_id}_{uuid.uuid4().hex}"

    def _run_compliance_checks(self, request: AuditRequest) -> List[AuditViolation]:
        violations: List[AuditViolation] = []
        target = request.target or {}

        for rule in request.rules:
            rule_type = str(rule.type).lower()

            if rule_type == RuleType.REQUIRED_FIELDS.value:
                for field in rule.fields:
                    if target.get(field) in (None, ""):
                        violations.append(
                            AuditViolation(
                                rule_id=rule.rule_id,
                                field=field,
                                message=f"Missing required field: {field}",
                                severity=rule.severity_override or "error",
                            )
                        )

            elif rule_type == RuleType.FORBIDDEN_TERMS.value:
                terms = [t.lower() for t in rule.terms]
                for field in rule.fields:
                    value = target.get(field)
                    if isinstance(value, str):
                        lowered = value.lower()
                        for term in terms:
                            if term and term in lowered:
                                violations.append(
                                    AuditViolation(
                                        rule_id=rule.rule_id,
                                        field=field,
                                        message=f"Forbidden term '{term}' found in {field}",
                                        severity=rule.severity_override or "warning",
                                    )
                                )

            elif rule_type == RuleType.EMAIL_DOMAIN_BLOCKLIST.value:
                email_value = None
                for field in rule.fields or ["email", "to_email", "from_email"]:
                    if target.get(field):
                        email_value = target.get(field)
                        break
                if isinstance(email_value, str) and "@" in email_value:
                    domain = email_value.split("@", 1)[1].lower()
                    blocklist = {t.lower() for t in rule.terms}
                    if domain in blocklist:
                        violations.append(
                            AuditViolation(
                                rule_id=rule.rule_id,
                                field="email",
                                message=f"Email domain '{domain}' is blocklisted",
                                severity=rule.severity_override or "error",
                                value=email_value,
                                remediation="Remove or replace the email address",
                            )
                        )

            elif rule_type == RuleType.NUMERIC_RANGE.value:
                for field in rule.fields:
                    value = target.get(field)
                    if value is None:
                        continue
                    try:
                        numeric = float(value)
                    except (TypeError, ValueError):
                        violations.append(
                            AuditViolation(
                                rule_id=rule.rule_id,
                                field=field,
                                message=f"Non-numeric value for {field}",
                                severity="warning",
                                value=value,
                            )
                        )
                        continue
                    if rule.min_value is not None and numeric < rule.min_value:
                        violations.append(
                            AuditViolation(
                                rule_id=rule.rule_id,
                                field=field,
                                message=f"Value {numeric} below minimum {rule.min_value} for {field}",
                                severity=rule.severity_override or "warning",
                                value=numeric,
                                expected=f">= {rule.min_value}",
                            )
                        )
                    if rule.max_value is not None and numeric > rule.max_value:
                        violations.append(
                            AuditViolation(
                                rule_id=rule.rule_id,
                                field=field,
                                message=f"Value {numeric} above maximum {rule.max_value} for {field}",
                                severity=rule.severity_override or "warning",
                                value=numeric,
                                expected=f"<= {rule.max_value}",
                            )
                        )

            elif rule_type == RuleType.PII_DETECTION.value:
                patterns = rule.patterns or list(PII_PATTERNS.values())
                for field in rule.fields:
                    value = target.get(field)
                    if isinstance(value, str):
                        for pattern in patterns:
                            if re.search(pattern, value, re.IGNORECASE):
                                violations.append(
                                    AuditViolation(
                                        rule_id=rule.rule_id,
                                        field=field,
                                        message=f"Potential PII detected in {field}",
                                        severity=rule.severity_override or "critical",
                                        remediation="Remove or mask PII before processing",
                                        regulation=rule.metadata.get("regulation"),
                                    )
                                )
                                break  # One violation per field

            elif rule_type == RuleType.DATA_FRESHNESS.value:
                max_age_hours = rule.max_age_hours or 24
                for field in rule.fields:
                    value = target.get(field)
                    if value is None:
                        continue
                    try:
                        if isinstance(value, str):
                            ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        elif isinstance(value, datetime):
                            ts = value
                        else:
                            continue
                        age = datetime.utcnow() - ts.replace(tzinfo=None)
                        if age > timedelta(hours=max_age_hours):
                            violations.append(
                                AuditViolation(
                                    rule_id=rule.rule_id,
                                    field=field,
                                    message=f"Data in {field} is {age.days}d {age.seconds // 3600}h old (max: {max_age_hours}h)",
                                    severity=rule.severity_override or "warning",
                                    value=value if isinstance(value, str) else value.isoformat(),
                                    expected=f"< {max_age_hours} hours old",
                                )
                            )
                    except (ValueError, TypeError):
                        pass  # Skip invalid timestamps

            elif rule_type == RuleType.CONSENT_REQUIRED.value:
                for field in rule.fields:
                    value = target.get(field)
                    # Consent must be explicitly True or "true" or 1
                    if value not in (True, "true", "True", 1, "1", "yes", "Yes"):
                        violations.append(
                            AuditViolation(
                                rule_id=rule.rule_id,
                                field=field,
                                message=f"Required consent not granted: {field}",
                                severity=rule.severity_override or "error",
                                value=value,
                                expected="true",
                                regulation=rule.metadata.get("regulation"),
                                remediation="Obtain explicit consent before proceeding",
                            )
                        )

            elif rule_type == RuleType.FORMAT_VALIDATION.value:
                for field in rule.fields:
                    value = target.get(field)
                    if not isinstance(value, str):
                        continue
                    for pattern in rule.patterns:
                        if not re.match(pattern, value, re.IGNORECASE):
                            violations.append(
                                AuditViolation(
                                    rule_id=rule.rule_id,
                                    field=field,
                                    message=f"Invalid format for {field}",
                                    severity=rule.severity_override or "warning",
                                    value=value,
                                    expected=f"match pattern: {pattern}",
                                )
                            )

            elif rule_type == RuleType.GEOGRAPHIC_RESTRICTION.value:
                # Check country/region fields
                for field in rule.fields or ["country", "region", "location"]:
                    value = target.get(field)
                    if not isinstance(value, str):
                        continue
                    value_lower = value.lower()
                    if rule.blocked_regions:
                        blocked = {r.lower() for r in rule.blocked_regions}
                        if value_lower in blocked:
                            violations.append(
                                AuditViolation(
                                    rule_id=rule.rule_id,
                                    field=field,
                                    message=f"Geographic region '{value}' is restricted",
                                    severity=rule.severity_override or "error",
                                    value=value,
                                    regulation=rule.metadata.get("regulation"),
                                )
                            )
                    if rule.allowed_regions:
                        allowed = {r.lower() for r in rule.allowed_regions}
                        if value_lower not in allowed:
                            violations.append(
                                AuditViolation(
                                    rule_id=rule.rule_id,
                                    field=field,
                                    message=f"Geographic region '{value}' not in allowed list",
                                    severity=rule.severity_override or "error",
                                    value=value,
                                )
                            )

        return violations

    def _calculate_compliance_score(self, violations: List[AuditViolation]) -> float:
        """Calculate a compliance score from 0-100 based on violations."""
        if not violations:
            return 100.0

        # Weight by severity
        weights = {"info": 1, "warning": 5, "error": 15, "critical": 30}
        total_penalty = sum(weights.get(v.severity, 5) for v in violations)
        # Cap at 100 penalty
        score = max(0.0, 100.0 - min(total_penalty, 100))
        return round(score, 1)

    def _summarize_by_severity(self, violations: List[AuditViolation]) -> Dict[str, int]:
        """Count violations by severity level."""
        summary: Dict[str, int] = {}
        for v in violations:
            severity = v.severity or "unknown"
            summary[severity] = summary.get(severity, 0) + 1
        return summary

    def _generate_audit_trail(self, request: AuditRequest) -> AuditTrail:
        events = request.events or []
        by_action: Dict[str, int] = {}
        for event in events:
            action = str(event.get("action") or "unknown")
            by_action[action] = by_action.get(action, 0) + 1

        summary = {
            "event_count": len(events),
            "actions": by_action,
            "generated_at": datetime.utcnow().isoformat(),
        }

        trail_id = f"audit_trail_{request.entity_id or 'unknown'}_{uuid.uuid4().hex}"
        return AuditTrail(
            trail_id=trail_id,
            entity_id=request.entity_id,
            entity_type=request.entity_type,
            events=events,
            summary=summary,
        )

    def _build_report(self, trail: Optional[AuditTrail], violations: List[AuditViolation]) -> AuditReport:
        metrics = {}
        if trail:
            metrics.update(trail.summary)
        metrics["violations"] = len(violations)

        blocking = [v for v in violations if v.severity in ("error", "critical")]
        status = "completed" if not blocking else "completed_with_issues"
        compliance_score = self._calculate_compliance_score(violations)

        recommendations = []
        if blocking:
            recommendations.append("Resolve all error/critical violations before proceeding")
        if any(v.severity == "warning" for v in violations):
            recommendations.append("Review warning-level issues for potential improvements")

        return AuditReport(
            report_id=f"rpt_{uuid.uuid4().hex[:8]}",
            status=status,
            metrics=metrics,
            violations=violations,
            violation_summary=self._summarize_by_severity(violations),
            compliance_score=compliance_score,
            recommendations=recommendations,
        )
