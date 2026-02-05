"""Classifier Agent - Email Classification with Rules + Optional LLM.

Tier 3 agent that classifies inbound emails into categories to determine
whether they should be routed to Leads for reply, stored only, or dropped.

Classification approach:
1. Rules-based classification (fast, deterministic, no LLM cost)
2. Optional LLM fallback for ambiguous cases (configurable)
"""
from __future__ import annotations

import logging
import os
import re
import asyncio
import json
from typing import Any, Dict, List, Optional, Set

from .schemas import (
    ClassificationAction,
    ClassificationResult,
    EmailCategory,
    EmailPriority,
    get_action_for_category,
)
from core.security.prompt_hardening import (
    detect_injection_attempt,
    sanitize_user_input,
    get_hardened_classifier_prompt,
)

logger = logging.getLogger(__name__)

# Environment configuration
CLASSIFIER_LLM_ENABLED = os.getenv("CLASSIFIER_LLM_ENABLED", "0").lower() in ("1", "true", "yes")
CLASSIFIER_LLM_CONFIDENCE_THRESHOLD = float(os.getenv("CLASSIFIER_LLM_CONFIDENCE_THRESHOLD", "0.6"))
CLASSIFIER_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Known sender patterns / domains
# ---------------------------------------------------------------------------

# Domains that typically send personal/business emails (whitelist)
PERSONAL_DOMAINS: Set[str] = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "protonmail.com",
    "me.com",
    "live.com",
    "msn.com",
}

# Domains that are always marketing/newsletters (blacklist)
MARKETING_DOMAINS: Set[str] = {
    "mailchimp.com",
    "sendgrid.net",
    "hubspot.com",
    "constantcontact.com",
    "getresponse.com",
    "campaignmonitor.com",
    "klaviyo.com",
    "drip.com",
    "convertkit.com",
    "activecampaign.com",
    "sendinblue.com",
    "mailgun.org",
    "amazonses.com",
    "sparkpost.com",
    "postmarkapp.com",
    "mandrillapp.com",
}

# Subject patterns indicating personal/business inquiry
PERSONAL_SUBJECT_PATTERNS: List[str] = [
    r"^re:\s*",  # Reply to previous conversation
    r"^fwd?:\s*",  # Forwarded message
    r"question\s+(about|regarding)",
    r"inquiry\s+(about|regarding|for)",
    r"interested\s+in",
    r"following\s+up",
    r"quick\s+question",
    r"need\s+help",
    r"can\s+you\s+help",
    r"would\s+like\s+to",
    r"wanted\s+to\s+(ask|discuss|talk)",
    r"reaching\s+out",
    r"introduction",
    r"meeting\s+request",
    r"schedule\s+a\s+call",
    r"partnership",
    r"collaboration",
    r"proposal",
]

# Subject patterns indicating newsletters/marketing
MARKETING_SUBJECT_PATTERNS: List[str] = [
    r"newsletter",
    r"weekly\s+digest",
    r"monthly\s+(update|roundup)",
    r"special\s+offer",
    r"limited\s+time",
    r"discount\s+code",
    r"flash\s+sale",
    r"don't\s+miss",
    r"exclusive\s+deal",
    r"save\s+\d+%",
    r"free\s+(trial|demo|webinar)",
    r"register\s+now",
    r"join\s+us",
    r"upcoming\s+event",
    r"webinar\s+invitation",
    r"product\s+update",
    r"new\s+feature",
    r"release\s+notes",
    r"tips\s+(&|and)\s+tricks",
]

# Body patterns indicating personal/business communication
PERSONAL_BODY_PATTERNS: List[str] = [
    r"i\s+noticed\s+(your|you)",
    r"i\s+saw\s+(your|you)",
    r"i\s+came\s+across",
    r"i('m|\s+am)\s+interested",
    r"i\s+would\s+like\s+to",
    r"can\s+we\s+(meet|chat|talk|discuss)",
    r"let('s|\s+us)\s+schedule",
    r"looking\s+forward\s+to\s+hearing",
    r"please\s+(let\s+me\s+know|respond|reply)",
    r"what\s+are\s+your\s+thoughts",
    r"do\s+you\s+have\s+time",
    r"attached\s+(is|are|please\s+find)",
    r"as\s+discussed",
    r"per\s+our\s+conversation",
    r"following\s+up\s+on",
]


def _extract_domain(email: str) -> str:
    """Extract domain from email address."""
    if "@" in email:
        return email.split("@")[-1].lower()
    return ""


def _matches_any(text: str, patterns: List[str]) -> bool:
    """Check if text matches any regex pattern."""
    text_lower = (text or "").lower()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def _count_matches(text: str, patterns: List[str]) -> int:
    """Count how many patterns match the text."""
    text_lower = (text or "").lower()
    count = 0
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            count += 1
    return count


class ClassifierAgent:
    """Email classifier using rules-based classification with optional LLM fallback."""

    def __init__(self, llm_enabled: bool = CLASSIFIER_LLM_ENABLED):
        self.llm_enabled = llm_enabled
        self.version = CLASSIFIER_VERSION
        self.use_langgraph = os.getenv("LANGGRAPH_WORKFLOWS_ENABLED", "1").lower() in ("1", "true", "yes")
        self._graph_runner = None

    def _llm_classify(self, email_event: Dict[str, Any]) -> Optional[ClassificationResult]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        enabled_flag = os.getenv("CLASSIFIER_LLM_ENABLED", "1").lower()
        if enabled_flag in ("0", "false", "no"):
            return None

        try:
            from openai import OpenAI  # type: ignore

            model = os.getenv("CLASSIFIER_LLM_MODEL", "gpt-4o-mini")
            client = OpenAI(api_key=api_key)

            # Check for injection attempts in email content
            email_body = str(email_event.get("body") or "")
            email_subject = str(email_event.get("subject") or "")
            is_injection, pattern = detect_injection_attempt(email_body + " " + email_subject)
            
            if is_injection:
                logger.warning(f"Injection attempt detected in email: {pattern}")
                # Classify as spam immediately - don't let LLM process injection attempts
                return ClassificationResult(
                    category=EmailCategory.SPAM,
                    priority=EmailPriority.LOW,
                    confidence=0.95,
                    action=ClassificationAction.DROP,
                    reasoning="Injection attempt detected - classified as spam",
                    signals=["injection_detected", f"pattern:{pattern[:50]}"],
                    classifier_version=self.version,
                )

            # Sanitize all user content before embedding in LLM payload
            payload = {
                "from_email": sanitize_user_input(str(email_event.get("from_email") or email_event.get("from") or "")),
                "subject": sanitize_user_input(email_subject),
                "body": sanitize_user_input(email_body),
                "headers": {
                    "list_unsubscribe": (email_event.get("headers") or {}).get("list_unsubscribe"),
                    "precedence": (email_event.get("headers") or {}).get("precedence"),
                    "auto_response_suppress": (email_event.get("headers") or {}).get("auto_response_suppress"),
                    "x_mailer": (email_event.get("headers") or {}).get("x_mailer"),
                },
                "pre_filter": email_event.get("pre_filter") or {},
            }

            allowed = [c.value for c in EmailCategory]
            base_system_prompt = (
                f"Choose ONE category from: {', '.join(allowed)}. "
                "Return strict JSON: {\"category\": <string>, \"confidence\": <float 0..1>, "
                "\"priority\": <high|normal|low>, \"reasoning\": <string>}"
            )
            
            # Apply security hardening to classifier prompt
            system_prompt = get_hardened_classifier_prompt(base_system_prompt)

            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, default=str)},
                ],
                temperature=0.0,
            )

            content = resp.choices[0].message.content or "{}"
            data = json.loads(content)

            category_val = str(data.get("category", "unknown")).strip().lower()
            if category_val not in allowed:
                return None

            priority_val = str(data.get("priority", "normal")).strip().lower()
            if priority_val not in ("high", "normal", "low"):
                priority_val = "normal"

            try:
                confidence = float(data.get("confidence", 0.0))
            except Exception:
                confidence = 0.0

            reasoning = str(data.get("reasoning", "LLM classification"))

            category = EmailCategory(category_val)
            priority = EmailPriority(priority_val)
            action = get_action_for_category(category)

            return ClassificationResult(
                category=category,
                priority=priority,
                confidence=max(0.0, min(1.0, confidence)),
                action=action,
                reasoning=reasoning,
                signals=["llm:openai"],
                classifier_version=self.version,
            )
        except Exception:
            return None

    def _get_graph_runner(self):
        if self._graph_runner is not None:
            return self._graph_runner
        from core.langgraph import LangGraphRunner

        def _execute_graph(state):
            payload = state.get("email_event") or {}
            result = self.classify(payload)
            return result.model_dump()

        def _guardrails(state):
            output = state.get("output") or {}
            if not output.get("category"):
                return {"status": "error", "error": "missing_category"}
            return output

        self._graph_runner = LangGraphRunner(
            name="classifier",
            execute_fn=_execute_graph,
            required_input_keys=["email_event"],
            guardrails_fn=_guardrails,
        )
        return self._graph_runner

    def execute(self, email_event: Dict[str, Any]) -> Dict[str, Any]:
        if self.use_langgraph:
            runner = self._get_graph_runner()
            try:
                asyncio.get_running_loop()
                return self.classify(email_event).model_dump()
            except RuntimeError:
                graph_result = asyncio.run(
                    runner.run(
                        state_input={
                            "email_event": email_event,
                            "task_id": email_event.get("task_id"),
                            "correlation_id": email_event.get("correlation_id"),
                        },
                        execution_id=str(email_event.get("task_id") or email_event.get("correlation_id") or ""),
                    )
                )
            if graph_result.get("status") == "success":
                return graph_result.get("output", {})
            return {
                "status": "error",
                "error": graph_result.get("error", "langgraph_failed"),
                "trace": graph_result.get("trace", []),
            }
        return self.classify(email_event).model_dump()

    def classify(self, email_event: Dict[str, Any]) -> ClassificationResult:
        """Classify an inbound email event.

        Args:
            email_event: Dict with keys: from_email, subject, body, headers, pre_filter, etc.

        Returns:
            ClassificationResult with category, priority, confidence, action, reasoning
        """
        from_email = email_event.get("from_email") or email_event.get("from", "")
        subject = email_event.get("subject", "") or ""
        body = email_event.get("body", "") or ""
        headers = email_event.get("headers", {}) or {}
        pre_filter = email_event.get("pre_filter", {}) or {}

        signals: List[str] = []
        sender_domain = _extract_domain(from_email)

        # 1. Check pre-filter result first (Tier-0 already ran)
        pre_filter_category = pre_filter.get("category")
        pre_filter_confidence = pre_filter.get("confidence", 0.0)

        if pre_filter_category and pre_filter_confidence >= 0.7:
            # Trust pre-filter for high-confidence classifications
            category_map = {
                "bounce": EmailCategory.BOUNCE,
                "unsubscribe": EmailCategory.NEWSLETTER,
                "newsletter": EmailCategory.NEWSLETTER,
                "auto_reply": EmailCategory.AUTO_REPLY,
                "system": EmailCategory.TRANSACTIONAL,
            }
            if pre_filter_category in category_map:
                cat = category_map[pre_filter_category]
                signals.append(f"pre_filter: {pre_filter_category} ({pre_filter_confidence:.2f})")
                return ClassificationResult(
                    category=cat,
                    priority=EmailPriority.LOW,
                    confidence=pre_filter_confidence,
                    action=get_action_for_category(cat),
                    reasoning=pre_filter.get("reason", "Pre-filter classification"),
                    signals=signals,
                    classifier_version=self.version,
                )

        # 2. Check headers for newsletter/marketing signals
        if headers.get("list_unsubscribe"):
            signals.append("header: List-Unsubscribe present")
        if headers.get("precedence") in ("bulk", "list", "junk"):
            signals.append(f"header: Precedence={headers.get('precedence')}")

        # 3. Check sender domain
        if sender_domain in MARKETING_DOMAINS:
            signals.append(f"domain: {sender_domain} is marketing ESP")
            return ClassificationResult(
                category=EmailCategory.MARKETING,
                priority=EmailPriority.LOW,
                confidence=0.85,
                action=ClassificationAction.STORE_ONLY,
                reasoning=f"Sender domain {sender_domain} is a known marketing/ESP platform",
                signals=signals,
                classifier_version=self.version,
            )

        # 4. Check subject patterns
        personal_subject_matches = _count_matches(subject, PERSONAL_SUBJECT_PATTERNS)
        marketing_subject_matches = _count_matches(subject, MARKETING_SUBJECT_PATTERNS)

        if personal_subject_matches > 0:
            signals.append(f"subject: {personal_subject_matches} personal pattern(s)")
        if marketing_subject_matches > 0:
            signals.append(f"subject: {marketing_subject_matches} marketing pattern(s)")

        # 5. Check body patterns
        personal_body_matches = _count_matches(body[:2000], PERSONAL_BODY_PATTERNS)  # Limit body scan
        if personal_body_matches > 0:
            signals.append(f"body: {personal_body_matches} personal pattern(s)")

        # 6. Check if it's a reply (Re: in subject or thread_id present)
        is_reply = subject.lower().startswith("re:") or email_event.get("thread_id")
        if is_reply:
            signals.append("context: reply to existing thread")

        # 7. Score and decide
        personal_score = personal_subject_matches * 2 + personal_body_matches + (3 if is_reply else 0)
        marketing_score = marketing_subject_matches * 2 + (2 if headers.get("list_unsubscribe") else 0)

        # Personal domain boost
        if sender_domain in PERSONAL_DOMAINS:
            signals.append(f"domain: {sender_domain} is personal email provider")
            personal_score += 2

        # Decision logic
        if personal_score >= 3 and personal_score > marketing_score:
            confidence = min(0.9, 0.5 + personal_score * 0.1)
            # Determine if business inquiry vs personal
            category = EmailCategory.BUSINESS_INQUIRY if "inquiry" in subject.lower() or "question" in subject.lower() else EmailCategory.PERSONAL
            return ClassificationResult(
                category=category,
                priority=EmailPriority.NORMAL if is_reply else EmailPriority.NORMAL,
                confidence=confidence,
                action=ClassificationAction.ROUTE_TO_LEADS,
                reasoning=f"Personal/business signals ({personal_score}) outweigh marketing ({marketing_score})",
                signals=signals,
                classifier_version=self.version,
            )

        if marketing_score >= 2 and marketing_score > personal_score:
            confidence = min(0.85, 0.5 + marketing_score * 0.1)
            return ClassificationResult(
                category=EmailCategory.NEWSLETTER if headers.get("list_unsubscribe") else EmailCategory.MARKETING,
                priority=EmailPriority.LOW,
                confidence=confidence,
                action=ClassificationAction.STORE_ONLY,
                reasoning=f"Marketing signals ({marketing_score}) outweigh personal ({personal_score})",
                signals=signals,
                classifier_version=self.version,
            )

        # 8. Ambiguous case - low confidence
        confidence = 0.4
        if self.llm_enabled and confidence < CLASSIFIER_LLM_CONFIDENCE_THRESHOLD:
            llm_result = self._llm_classify(email_event)
            if llm_result and llm_result.confidence >= CLASSIFIER_LLM_CONFIDENCE_THRESHOLD:
                llm_result.signals = list(dict.fromkeys(signals + llm_result.signals + ["llm_fallback:openai"]))
                return llm_result
            if llm_result:
                signals.append("llm_fallback:openai:low_confidence")
            else:
                signals.append("llm_fallback:openai:unavailable")

        # Default: treat as unknown, route to review
        return ClassificationResult(
            category=EmailCategory.UNKNOWN,
            priority=EmailPriority.NORMAL,
            confidence=confidence,
            action=ClassificationAction.REVIEW,
            reasoning=f"Ambiguous: personal_score={personal_score}, marketing_score={marketing_score}",
            signals=signals,
            classifier_version=self.version,
        )

    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a classification task (harness entry point).

        Args:
            task: Task envelope payload with email_event

        Returns:
            Result dict with classification
        """
        email_event = task.get("payload", {}).get("context", {}).get("email_event", {})
        pre_filter = task.get("payload", {}).get("context", {}).get("pre_filter", {})

        # Merge pre_filter into email_event for classify()
        email_event["pre_filter"] = pre_filter

        result = self.classify(email_event)

        return {
            "status": "success",
            "classification": result.to_dict(),
            "message_id": email_event.get("message_id"),
        }
