"""Classifier Agent package."""
from .classifier_agent import ClassifierAgent
from .schemas import (
    ClassificationAction,
    ClassificationResult,
    EmailCategory,
    EmailPriority,
    get_action_for_category,
)

__all__ = [
    "ClassifierAgent",
    "ClassificationAction",
    "ClassificationResult",
    "EmailCategory",
    "EmailPriority",
    "get_action_for_category",
]
