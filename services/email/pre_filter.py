"""Email pre-filter for Tier-0 classification.

Cheap header/pattern-based filtering that runs BEFORE publishing to Manager.
Identifies obvious low-value messages (bounces, marketing/newsletters, auto-replies)
without incurring LLM costs.

Important:
- List-Unsubscribe is a useful signal, but many legitimate notifications also include it.
    We treat it as a weak marketing signal unless reinforced by other indicators.

Categories:
- bounce: MAILER-DAEMON, delivery failure, postmaster
- auto_reply: X-Auto-Response-Suppress, Out of Office patterns
- system: Transactional/operational notifications (security, access requests, receipts, alerts)
- marketing: Promotions / sales / webinars / bulk marketing
- newsletter: Informational digests / product updates
- None: Passed pre-filter; needs full classification
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, List, Set

logger = logging.getLogger(__name__)


# Known bounce sender patterns
BOUNCE_SENDERS: Set[str] = {
    "mailer-daemon",
    "postmaster",
    "mail-daemon",
}

# Known bulk email / marketing platforms (indicator, not sufficient by itself)
MARKETING_PLATFORM_DOMAINS: Set[str] = {
    "mailchimp.com",
    "mailgun.org",
    "sendgrid.net",
    "sparkpostmail.com",
    "sparkpost.com",
    "postmarkapp.com",
    "mandrillapp.com",
    "intercom-mail.com",
    "hubspot.com",
    "customeriomail.com",
    "iterable.com",
}

# Known transactional/system sender domains (higher confidence indicator)
SYSTEM_DOMAINS: Set[str] = {
    "stripe.com",
    "paypal.com",
    "github.com",
    "gitlab.com",
    "atlassian.net",
    "atlassian.com",
    "jira.com",
    "slack.com",
    "zoom.us",
    "google.com",
    "googleapis.com",
    "apple.com",
    "microsoft.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "reddit.com",
    "reddit.io",
}

# Known marketing/newsletter sender patterns
MARKETING_SENDER_PATTERNS: List[str] = [
    r"newsletter@",
    r"marketing@",
    r"promo@",
    r"offers@",
    r"deals@",
    r"updates@",
    r"digest@",
    r"weekly@",
    r"daily@",
    r"notifications?@",
    r"campaigns?@",
    r"productmarketing@",
]

# Marketing-heavy language (subject/body)
MARKETING_KEYWORDS: List[str] = [
    r"\b(unsubscribe|opt\s?out)\b",
    r"\b(offer|deal|sale|discount|%\s?off|save\s+\$|promo\s?code|coupon)\b",
    r"\b(limited\s*time|last\s+chance|ends\s+today|today\s+only)\b",
    r"\b(redeem|claim\s+now|buy\s+now|upgrade\s+now|get\s+started)\b",
    r"\b(webinar|roundtable|live\s+soon|join\s+us\s+live)\b",
    r"utm_(source|medium|campaign)=",
]

# Newsletter-ish (less salesy) language
NEWSLETTER_KEYWORDS: List[str] = [
    r"\b(weekly|daily|monthly)\b",
    r"\b(digest|newsletter|update|product\s+update)\b",
]

# Subject patterns that indicate system/transactional emails
SYSTEM_SUBJECT_PATTERNS: List[str] = [
    r"order\s+(confirmation|shipped|delivered)",
    r"your\s+(order|receipt|invoice|payment)",
    r"password\s+(reset|changed|updated)",
    r"verify\s+your\s+(email|account)",
    r"account\s+(created|activated|suspended)",
    r"security\s+alert",
    r"login\s+(attempt|notification)",
    r"two-factor|2fa|mfa",
    r"subscription\s+(confirmed|cancelled|renewed)",
    r"security\s+advisor",
    r"share\s+request\b",
    r"requests?\s+access\b",
    r"action\s+required\b",
    r"welcome\s+to\s+",
    r"thank\s+you\s+for\s+(signing|registering|subscribing)",
]

# Subject patterns for auto-replies / OOO
AUTO_REPLY_SUBJECT_PATTERNS: List[str] = [
    r"^(re:\s*)?out\s+of\s+(the\s+)?office",
    r"^(re:\s*)?automatic\s+reply",
    r"^(re:\s*)?auto[\-\s]?reply",
    r"^(re:\s*)?away\s+from\s+(my\s+)?(desk|office|email)",
    r"^(re:\s*)?vacation\s+(reply|response)",
    r"^(re:\s*)?i('m|\s+am)\s+(currently\s+)?(out|away|on\s+leave)",
    r"^(re:\s*)?will\s+be\s+out",
    r"delivery\s+(status|failure)\s+notification",
    r"undeliverable",
    r"mail\s+delivery\s+(failed|error)",
]

# Subject patterns for bounces
BOUNCE_SUBJECT_PATTERNS: List[str] = [
    r"delivery\s+(status|failure)\s+notification",
    r"undeliverable",
    r"mail\s+delivery\s+(failed|error|subsystem)",
    r"returned\s+mail",
    r"failure\s+notice",
    r"message\s+not\s+delivered",
]


@dataclass
class PreFilterResult:
    """Result from Tier-0 pre-filter."""

    category: Optional[str]  # bounce, auto_reply, system, marketing, newsletter, or None
    confidence: float  # 0.0-1.0
    reason: str  # Human-readable explanation


def _normalize(s: Optional[str]) -> str:
    """Lowercase and strip for comparison."""
    return (s or "").lower().strip()


def _matches_any(text: str, patterns: List[str]) -> bool:
    """Check if text matches any regex pattern."""
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _extract_sender_local(from_email: str) -> str:
    """Extract local part of email (before @)."""
    return from_email.split("@")[0].lower() if "@" in from_email else from_email.lower()


def _extract_domain(email: str) -> str:
    """Extract domain from email address."""
    if "@" in email:
        return email.split("@")[-1].lower()
    return ""


def pre_filter_email(
    *,
    from_email: str,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    list_unsubscribe: Optional[str] = None,
    precedence: Optional[str] = None,
    auto_response_suppress: Optional[str] = None,
    x_mailer: Optional[str] = None,
    from_name: Optional[str] = None,
) -> PreFilterResult:
    """Apply cheap pre-filter rules to classify obvious email types.

    Args:
        from_email: Sender email address
        subject: Email subject line
        body: Email body (optional, for deeper analysis)
        list_unsubscribe: List-Unsubscribe header value
        precedence: Precedence header value (bulk/list/junk)
        auto_response_suppress: X-Auto-Response-Suppress header
        x_mailer: X-Mailer header

    Returns:
        PreFilterResult with category, confidence, and reason
    """
    from_email_norm = _normalize(from_email)
    subject_norm = _normalize(subject)
    body_norm = _normalize(body)
    sender_local = _extract_sender_local(from_email_norm)
    sender_domain = _extract_domain(from_email_norm)

    # 1. Check for bounces (highest priority)
    if sender_local in BOUNCE_SENDERS:
        return PreFilterResult(
            category="bounce",
            confidence=0.95,
            reason=f"Sender local part '{sender_local}' indicates bounce/system mail",
        )

    if _matches_any(subject_norm, BOUNCE_SUBJECT_PATTERNS):
        return PreFilterResult(
            category="bounce",
            confidence=0.90,
            reason="Subject matches bounce/delivery failure pattern",
        )

    # 2. Check for auto-replies / OOO
    if auto_response_suppress:
        return PreFilterResult(
            category="auto_reply",
            confidence=0.95,
            reason=f"X-Auto-Response-Suppress header present: {auto_response_suppress}",
        )

    if _matches_any(subject_norm, AUTO_REPLY_SUBJECT_PATTERNS):
        return PreFilterResult(
            category="auto_reply",
            confidence=0.85,
            reason="Subject matches auto-reply/OOO pattern",
        )

    # 3. Check for system/transactional emails.
    # Do this BEFORE List-Unsubscribe heuristics: many legitimate services include List-Unsubscribe.
    if sender_domain in SYSTEM_DOMAINS:
        return PreFilterResult(
            category="system",
            confidence=0.85,
            reason=f"Sender domain '{sender_domain}' is a known system/transactional sender",
        )

    if _matches_any(subject_norm, SYSTEM_SUBJECT_PATTERNS):
        return PreFilterResult(
            category="system",
            confidence=0.80,
            reason="Subject matches transactional/system email pattern",
        )

    # 4. Marketing/newsletters (scored)
    marketing_score = 0.0
    newsletter_score = 0.0
    reasons: List[str] = []

    prec_norm = _normalize(precedence)
    if prec_norm in ("bulk", "list", "junk"):
        newsletter_score += 0.65
        reasons.append(f"Precedence={prec_norm}")

    if list_unsubscribe:
        # Weak signal by itself (many products include it)
        marketing_score += 0.30
        newsletter_score += 0.30
        reasons.append("List-Unsubscribe present")

    if sender_domain in MARKETING_PLATFORM_DOMAINS:
        marketing_score += 0.25
        reasons.append(f"marketing-platform domain={sender_domain}")

    if _matches_any(from_email_norm, MARKETING_SENDER_PATTERNS):
        marketing_score += 0.25
        newsletter_score += 0.10
        reasons.append("sender pattern")

    if _matches_any(subject_norm, MARKETING_KEYWORDS) or _matches_any(body_norm, MARKETING_KEYWORDS):
        marketing_score += 0.35
        reasons.append("marketing keywords")

    if _matches_any(subject_norm, NEWSLETTER_KEYWORDS) or _matches_any(body_norm, NEWSLETTER_KEYWORDS):
        newsletter_score += 0.25
        reasons.append("newsletter keywords")

    # Decide category
    if marketing_score >= 0.65:
        return PreFilterResult(
            category="marketing",
            confidence=min(0.95, 0.55 + marketing_score),
            reason="; ".join(reasons) or "marketing indicators",
        )

    if newsletter_score >= 0.60:
        return PreFilterResult(
            category="newsletter",
            confidence=min(0.90, 0.50 + newsletter_score),
            reason="; ".join(reasons) or "newsletter indicators",
        )

    # 5. Passed pre-filter → needs full classification
    return PreFilterResult(
        category=None,
        confidence=0.0,
        reason="No pre-filter match; requires full classification",
    )
