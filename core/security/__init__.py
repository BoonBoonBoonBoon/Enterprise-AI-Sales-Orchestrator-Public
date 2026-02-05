"""
Security module for LLM prompt hardening and output validation.

CRITICAL: This module protects all customer-facing LLM interactions.
Production-grade protection against:
- Prompt injection and jailbreaking
- AI identity disclosure
- AI writing pattern detection
"""

from .prompt_hardening import (
    # Detection functions
    detect_injection_attempt,
    detect_ai_vocabulary,
    # Sanitization
    sanitize_user_input,
    # Prompt hardening
    get_hardened_copywriter_prompt,
    get_hardened_internal_prompt,
    get_hardened_classifier_prompt,
    # Security blocks (for direct use if needed)
    HUMAN_IDENTITY_BLOCK,
    ANTI_INJECTION_BLOCK,
    INTERNAL_AGENT_SECURITY_BLOCK,
    CLASSIFIER_SECURITY_BLOCK,
    # Pattern lists
    INJECTION_PATTERNS,
    AI_VOCABULARY_BANNED,
    AI_REVEAL_PATTERNS,
    # Validation
    validate_llm_output_safe,
    validate_output_comprehensive,
    # Scrubbing
    scrub_ai_references,
    scrub_output_aggressive,
)

__all__ = [
    # Detection
    "detect_injection_attempt",
    "detect_ai_vocabulary",
    # Sanitization
    "sanitize_user_input",
    # Prompt hardening
    "get_hardened_copywriter_prompt",
    "get_hardened_internal_prompt",
    "get_hardened_classifier_prompt",
    # Security blocks
    "HUMAN_IDENTITY_BLOCK",
    "ANTI_INJECTION_BLOCK",
    "INTERNAL_AGENT_SECURITY_BLOCK",
    "CLASSIFIER_SECURITY_BLOCK",
    # Pattern lists
    "INJECTION_PATTERNS",
    "AI_VOCABULARY_BANNED",
    "AI_REVEAL_PATTERNS",
    # Validation
    "validate_llm_output_safe",
    "validate_output_comprehensive",
    # Scrubbing
    "scrub_ai_references",
    "scrub_output_aggressive",
]
