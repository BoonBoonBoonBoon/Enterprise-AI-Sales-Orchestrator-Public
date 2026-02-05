"""Lead Qualification Module.

Provides scoring and decision logic for lead qualification:
- Rule-based scoring from email classification, conversation signals, and profile data
- LLM fallback for ambiguous cases
- Fast-track rules for high-intent leads
- Promotion decisions for staging → leads table

Usage:
    from tiers.tier_2.leads_orchestrator.qualification import (
        QualificationScorer,
        QualificationResult,
        score_lead_sync
    )
"""

from .scorer import (
    QualificationScorer,
    QualificationResult,
    QualificationConfig,
    score_lead_sync,
)

__all__ = [
    "QualificationScorer",
    "QualificationResult", 
    "QualificationConfig",
    "score_lead_sync",
]
