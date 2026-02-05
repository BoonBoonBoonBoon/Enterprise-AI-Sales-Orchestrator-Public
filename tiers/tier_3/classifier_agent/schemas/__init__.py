"""Email classification schemas and enums.

Defines the category taxonomy and classification result structure used by
the Classifier Agent and downstream consumers (Inbound Orchestrator, Leads).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import List, Optional


class EmailCategory(str, Enum):
    """Email classification categories.

    Determines how the system should handle the email:
    - PERSONAL: Direct personal communication → route to Leads for reply
    - BUSINESS_INQUIRY: Business/sales inquiry → route to Leads for reply
    - NEWSLETTER: Marketing newsletter → store only, no reply
    - MARKETING: Promotional/advertising → store only, no reply
    - TRANSACTIONAL: Order confirmations, receipts → store only, no reply
    - BOUNCE: Delivery failure notification → drop or store for audit
    - AUTO_REPLY: Out of office, vacation reply → store only, no reply
    - SPAM: Obvious spam → drop
    - UNKNOWN: Could not classify → route to Leads for human review
    """

    PERSONAL = "personal"
    BUSINESS_INQUIRY = "business_inquiry"
    NEWSLETTER = "newsletter"
    MARKETING = "marketing"
    TRANSACTIONAL = "transactional"
    BOUNCE = "bounce"
    AUTO_REPLY = "auto_reply"
    SPAM = "spam"
    UNKNOWN = "unknown"


class EmailPriority(str, Enum):
    """Email priority levels."""

    HIGH = "high"  # Urgent, time-sensitive
    NORMAL = "normal"  # Standard processing
    LOW = "low"  # Can be delayed


class ClassificationAction(str, Enum):
    """Actions based on classification result."""

    ROUTE_TO_LEADS = "route_to_leads"  # Forward to Leads Orchestrator for reply
    STORE_ONLY = "store_only"  # Store in DB but don't reply
    DROP = "drop"  # Discard entirely
    REVIEW = "review"  # Flag for human review


# Map categories to default actions
CATEGORY_ACTION_MAP = {
    EmailCategory.PERSONAL: ClassificationAction.ROUTE_TO_LEADS,
    EmailCategory.BUSINESS_INQUIRY: ClassificationAction.ROUTE_TO_LEADS,
    EmailCategory.NEWSLETTER: ClassificationAction.STORE_ONLY,
    EmailCategory.MARKETING: ClassificationAction.STORE_ONLY,
    EmailCategory.TRANSACTIONAL: ClassificationAction.STORE_ONLY,
    EmailCategory.BOUNCE: ClassificationAction.DROP,
    EmailCategory.AUTO_REPLY: ClassificationAction.STORE_ONLY,
    EmailCategory.SPAM: ClassificationAction.DROP,
    EmailCategory.UNKNOWN: ClassificationAction.REVIEW,
}


@dataclass
class ClassificationResult:
    """Result from email classification.

    Attributes:
        category: Primary classification category
        priority: Email priority level
        confidence: Classifier confidence (0.0-1.0)
        action: Recommended action based on category
        reasoning: Human-readable explanation of classification
        signals: List of signals that contributed to classification
        classifier_version: Version of classifier that produced result
    """

    category: EmailCategory
    priority: EmailPriority
    confidence: float
    action: ClassificationAction
    reasoning: str
    signals: List[str]
    classifier_version: str = "1.0.0"

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        d = asdict(self)
        d["category"] = self.category.value
        d["priority"] = self.priority.value
        d["action"] = self.action.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ClassificationResult":
        """Create from dict."""
        return cls(
            category=EmailCategory(d["category"]),
            priority=EmailPriority(d["priority"]),
            confidence=d["confidence"],
            action=ClassificationAction(d["action"]),
            reasoning=d["reasoning"],
            signals=d.get("signals", []),
            classifier_version=d.get("classifier_version", "1.0.0"),
        )


def get_action_for_category(category: EmailCategory) -> ClassificationAction:
    """Get the default action for a category."""
    return CATEGORY_ACTION_MAP.get(category, ClassificationAction.REVIEW)
