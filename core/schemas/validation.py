"""Validation utilities for payload schemas."""
from typing import Any, Dict, Type, TypeVar
from pydantic import BaseModel, ValidationError as PydanticValidationError


# Re-export Pydantic's ValidationError for convenience
ValidationError = PydanticValidationError


T = TypeVar('T', bound=BaseModel)


def validate_payload(payload: Dict[str, Any], schema: Type[T]) -> T:
    """Validate and parse a payload dict against a Pydantic schema.
    
    Args:
        payload: Raw payload dictionary
        schema: Pydantic model class to validate against
        
    Returns:
        Validated and parsed model instance
        
    Raises:
        ValidationError: If payload doesn't match schema
        
    Example:
        >>> from agent.schemas import RAGTaskPayload
        >>> payload = {"query": {"table": "leads", "filters": {}}}
        >>> task = validate_payload(payload, RAGTaskPayload)
        >>> assert task.query.table == "leads"
    """
    return schema(**payload)


def validate_and_dict(payload: Dict[str, Any], schema: Type[T]) -> Dict[str, Any]:
    """Validate payload and return as dictionary.
    
    Useful for ensuring data matches schema without converting to model instance.
    
    Args:
        payload: Raw payload dictionary
        schema: Pydantic model class to validate against
        
    Returns:
        Validated payload as dictionary
        
    Raises:
        ValidationError: If payload doesn't match schema
    """
    validated = schema(**payload)
    return validated.model_dump(exclude_none=True)


def safe_validate(payload: Dict[str, Any], schema: Type[T]) -> tuple[T | None, list[str]]:
    """Safely validate payload, returning errors instead of raising.
    
    Args:
        payload: Raw payload dictionary
        schema: Pydantic model class to validate against
        
    Returns:
        Tuple of (validated_model, errors)
        - If successful: (model, [])
        - If failed: (None, ["error1", "error2", ...])
        
    Example:
        >>> from agent.schemas import RAGTaskPayload
        >>> payload = {"query": {"table": "leads"}}
        >>> model, errors = safe_validate(payload, RAGTaskPayload)
        >>> if errors:
        ...     print(f"Validation failed: {errors}")
        ... else:
        ...     print(f"Valid: {model.query.table}")
    """
    try:
        validated = schema(**payload)
        return validated, []
    except ValidationError as e:
        errors = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        return None, errors


def get_schema_example(schema: Type[BaseModel]) -> Dict[str, Any]:
    """Get example payload from schema's json_schema_extra.
    
    Args:
        schema: Pydantic model class
        
    Returns:
        Example payload dict if defined, else {}
        
    Example:
        >>> from agent.schemas import RAGTaskPayload
        >>> example = get_schema_example(RAGTaskPayload)
        >>> print(example['query']['table'])
        'leads'
    """
    config = getattr(schema, 'Config', None)
    if config and hasattr(config, 'json_schema_extra'):
        examples = config.json_schema_extra.get('examples', [])
        if examples:
            return examples[0]
    return {}


def validate_envelope_payload(envelope_data: Dict[str, Any], expected_schema: Type[T]) -> T:
    """Validate the payload field of an envelope against expected schema.
    
    Args:
        envelope_data: Full envelope dictionary (with metadata, payload, etc.)
        expected_schema: Expected schema for the payload field
        
    Returns:
        Validated payload model
        
    Raises:
        ValidationError: If payload doesn't match schema
        KeyError: If envelope doesn't have 'payload' field
        
    Example:
        >>> from agent.schemas import RAGTaskPayload
        >>> envelope = {
        ...     "metadata": {"task_id": "task-123", "source": "orchestrator"},
        ...     "payload": {"query": {"table": "leads", "filters": {}}},
        ...     "status": "pending"
        ... }
        >>> task = validate_envelope_payload(envelope, RAGTaskPayload)
        >>> assert task.query.table == "leads"
    """
    if 'payload' not in envelope_data:
        raise KeyError("Envelope missing 'payload' field")
    
    return validate_payload(envelope_data['payload'], expected_schema)
