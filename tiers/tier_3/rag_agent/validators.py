"""
RAG Entity Validation Layer

Provides deterministic validation of entity payloads with:
- Required field checks
- Type validation
- Completeness scoring
- Field-level error reporting

Used as gatekeeper before deterministic RAG operations.
"""

import logging
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass
from enum import Enum

try:
    from config.rag_entities import (
        EntityType,
        get_schema,
        get_required_fields,
        FieldDefinition
    )
except ImportError:
    from rag_entities import (
        EntityType,
        get_schema,
        get_required_fields,
        FieldDefinition
    )

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Validation error severity levels"""
    ERROR = "error"      # Blocking - prevents deterministic processing
    WARNING = "warning"  # Non-blocking - can proceed with reduced confidence
    INFO = "info"        # Informational - minor issues


@dataclass
class ValidationError:
    """Single validation error"""
    field: str
    severity: ValidationSeverity
    message: str
    expected_type: Optional[str] = None
    actual_value: Optional[Any] = None


@dataclass
class ValidationResult:
    """Result of entity payload validation"""
    is_valid: bool
    entity_type: EntityType
    completeness_score: float  # 0.0 to 1.0
    errors: List[ValidationError]
    warnings: List[ValidationError]
    missing_required_fields: List[str]
    missing_optional_fields: List[str]
    present_fields: Set[str]
    
    def can_use_deterministic_path(self) -> bool:
        """Check if payload is good enough for deterministic processing"""
        # Threshold: 0.7 completeness and no blocking errors
        return self.completeness_score >= 0.7 and len(self.errors) == 0
    
    def needs_llm_repair(self) -> bool:
        """Check if LLM repair should be attempted"""
        # Repair if completeness is low but some data exists
        return 0.3 < self.completeness_score < 0.7
    
    def is_hopeless(self) -> bool:
        """Check if payload is too incomplete to repair"""
        return self.completeness_score < 0.3
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for envelope payload"""
        return {
            "is_valid": self.is_valid,
            "entity_type": self.entity_type.value,
            "completeness_score": self.completeness_score,
            "errors": [
                {
                    "field": e.field,
                    "severity": e.severity.value,
                    "message": e.message
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "field": w.field,
                    "severity": w.severity.value,
                    "message": w.message
                }
                for w in self.warnings
            ],
            "missing_required_fields": self.missing_required_fields,
            "missing_optional_fields": self.missing_optional_fields[:10],  # Limit output
            "present_fields": sorted(list(self.present_fields))
        }


def validate_entity_payload(
    entity_type: EntityType,
    payload: Dict[str, Any]
) -> ValidationResult:
    """
    Validate entity payload against schema.
    
    Args:
        entity_type: Type of entity to validate
        payload: Payload data to validate
    
    Returns:
        ValidationResult with completeness score and errors
    
    Example:
        >>> result = validate_entity_payload(
        ...     EntityType.LEAD,
        ...     {"email": "test@example.com", "first_name": "John"}
        ... )
        >>> result.is_valid
        False
        >>> result.completeness_score
        0.6
        >>> result.missing_required_fields
        ['last_name', 'client_id', 'id']
    """
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []
    
    # Get schema
    try:
        schema = get_schema(entity_type)
    except ValueError as e:
        return ValidationResult(
            is_valid=False,
            entity_type=entity_type,
            completeness_score=0.0,
            errors=[ValidationError(
                field="entity_type",
                severity=ValidationSeverity.ERROR,
                message=str(e)
            )],
            warnings=[],
            missing_required_fields=[],
            missing_optional_fields=[],
            present_fields=set()
        )
    
    # Get required fields
    required_fields = get_required_fields(entity_type)
    all_fields = {f.name for f in schema.fields}
    present_fields = set(payload.keys())
    
    # Check required fields
    missing_required = required_fields - present_fields
    for field in missing_required:
        errors.append(ValidationError(
            field=field,
            severity=ValidationSeverity.ERROR,
            message=f"Required field '{field}' is missing"
        ))
    
    # Check optional fields
    optional_fields = all_fields - required_fields
    missing_optional = optional_fields - present_fields
    
    # Validate field types
    field_map = {f.name: f for f in schema.fields}
    for field_name, value in payload.items():
        if field_name not in field_map:
            warnings.append(ValidationError(
                field=field_name,
                severity=ValidationSeverity.WARNING,
                message=f"Unknown field '{field_name}' not in schema",
                actual_value=value
            ))
            continue
        
        field_def = field_map[field_name]
        
        # Skip None values (allowed for optional fields)
        if value is None:
            if field_def.required:
                errors.append(ValidationError(
                    field=field_name,
                    severity=ValidationSeverity.ERROR,
                    message=f"Required field '{field_name}' is None",
                    expected_type=field_def.field_type
                ))
            continue
        
        # Type validation
        type_valid = _validate_field_type(field_def, value)
        if not type_valid:
            severity = ValidationSeverity.ERROR if field_def.required else ValidationSeverity.WARNING
            errors.append(ValidationError(
                field=field_name,
                severity=severity,
                message=f"Field '{field_name}' has invalid type",
                expected_type=field_def.field_type,
                actual_value=type(value).__name__
            ))
        
        # Enum validation
        if field_def.enum_values and value not in field_def.enum_values:
            errors.append(ValidationError(
                field=field_name,
                severity=ValidationSeverity.WARNING,
                message=f"Field '{field_name}' value '{value}' not in allowed values: {field_def.enum_values}",
                actual_value=value
            ))
        
        # String length validation
        if field_def.max_length and isinstance(value, str) and len(value) > field_def.max_length:
            warnings.append(ValidationError(
                field=field_name,
                severity=ValidationSeverity.WARNING,
                message=f"Field '{field_name}' exceeds max length {field_def.max_length}",
                actual_value=len(value)
            ))
    
    # Calculate completeness score
    # Weight: required fields = 0.7, optional fields = 0.3
    required_score = (len(required_fields) - len(missing_required)) / len(required_fields) if required_fields else 1.0
    optional_score = (len(optional_fields) - len(missing_optional)) / len(optional_fields) if optional_fields else 1.0
    completeness_score = 0.7 * required_score + 0.3 * optional_score
    
    # Determine validity
    is_valid = len(errors) == 0 and len(missing_required) == 0
    
    return ValidationResult(
        is_valid=is_valid,
        entity_type=entity_type,
        completeness_score=completeness_score,
        errors=[e for e in errors if e.severity == ValidationSeverity.ERROR],
        warnings=[e for e in errors if e.severity == ValidationSeverity.WARNING] + warnings,
        missing_required_fields=sorted(list(missing_required)),
        missing_optional_fields=sorted(list(missing_optional)),
        present_fields=present_fields
    )


def _validate_field_type(field_def: FieldDefinition, value: Any) -> bool:
    """
    Validate that value matches field type.
    
    Args:
        field_def: Field definition with type
        value: Value to validate
    
    Returns:
        True if type is valid
    """
    field_type = field_def.field_type
    
    # UUID validation (string representation)
    if field_type == "uuid":
        if not isinstance(value, str):
            return False
        # Basic UUID format check (8-4-4-4-12 hex chars)
        parts = value.split("-")
        if len(parts) != 5:
            return False
        if len(parts[0]) != 8 or len(parts[1]) != 4 or len(parts[2]) != 4:
            return False
        if len(parts[3]) != 4 or len(parts[4]) != 12:
            return False
        return True
    
    # Text validation
    if field_type == "text":
        return isinstance(value, str)
    
    # JSONB validation (dict or list)
    if field_type == "jsonb":
        return isinstance(value, (dict, list))
    
    # Timestamp validation (ISO string or datetime object)
    if field_type == "timestamptz":
        if isinstance(value, str):
            # Basic ISO format check
            return "T" in value or "-" in value
        return False
    
    # Integer validation
    if field_type == "int8":
        return isinstance(value, int)
    
    # Boolean validation
    if field_type == "bool":
        return isinstance(value, bool)
    
    # Unknown type - be permissive
    return True


def get_validation_summary(result: ValidationResult) -> str:
    """
    Get human-readable validation summary.
    
    Args:
        result: ValidationResult to summarize
    
    Returns:
        Summary string for logging
    """
    summary = f"Validation for {result.entity_type.value}:\n"
    summary += f"  Valid: {result.is_valid}\n"
    summary += f"  Completeness: {result.completeness_score:.2f}\n"
    summary += f"  Can use deterministic: {result.can_use_deterministic_path()}\n"
    summary += f"  Needs LLM repair: {result.needs_llm_repair()}\n"
    
    if result.errors:
        summary += f"  Errors ({len(result.errors)}):\n"
        for err in result.errors[:5]:  # Limit to first 5
            summary += f"    - {err.field}: {err.message}\n"
    
    if result.warnings:
        summary += f"  Warnings ({len(result.warnings)}):\n"
        for warn in result.warnings[:3]:  # Limit to first 3
            summary += f"    - {warn.field}: {warn.message}\n"
    
    if result.missing_required_fields:
        summary += f"  Missing required: {', '.join(result.missing_required_fields)}\n"
    
    return summary


__all__ = [
    "ValidationSeverity",
    "ValidationError",
    "ValidationResult",
    "validate_entity_payload",
    "get_validation_summary",
]
