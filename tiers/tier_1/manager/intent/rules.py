from __future__ import annotations

from typing import Tuple, List
from core.schemas.manager import UnifiedManagerRequest

# Simple keyword heuristics; extend with embeddings/ML as needed
RULES = [
    ("start_campaign", ["start campaign", "launch", "go live", "start q", "launch campaign"]),
    ("lead_enrichment", ["enrich leads", "enrichment", "append data", "qualify leads", "list build", "find leads", "discover leads", "find ", "discover ", "startups"]),
    ("outreach", ["write email", "outreach", "sequence", "follow up", "linkedin", "campaign"]),
    ("audit", ["audit", "qa", "quality", "compliance", "policy"]),
    ("inbound", ["inbound", "reply", "responded", "response", "incoming"]),
    ("control", ["pause", "resume", "throttle", "budget", "schedule", "stop", " start "]),  # " start " to avoid "startp"
]


def classify_by_rules(req: UnifiedManagerRequest) -> Tuple[str, float, List[str]]:
    # Structural shortcut: inbound email flows should not rely on the LLM.
    # If we see an email_event (or explicit reply allowance), treat as inbound with high confidence.
    try:
        payload = req.payload if isinstance(req.payload, dict) else None
        if isinstance(payload, dict):
            ctx = payload.get("context") if isinstance(payload.get("context"), dict) else {}
            actions_allowed = ctx.get("actions_allowed") if isinstance(ctx.get("actions_allowed"), list) else []
            email_event = ctx.get("email_event")
            reply_allowed = "reply" in [str(x).lower() for x in actions_allowed]
            has_email = isinstance(email_event, dict) and bool(email_event)

            if has_email or reply_allowed:
                reasons = []
                if has_email:
                    reasons.append("payload:context.email_event")
                if reply_allowed:
                    reasons.append("payload:context.actions_allowed:reply")
                return "inbound", 0.95, reasons
    except Exception:
        pass

    # Build a text surface combining subject/text and common payload fields like 'goal'
    extra_text = ""
    if req.payload:
        goal_val = req.payload.get("goal") if isinstance(req.payload, dict) else None
        if isinstance(goal_val, str):
            extra_text = goal_val
    text = " ".join(filter(None, [req.subject or "", req.text or "", extra_text])) .lower()
    reasons: List[str] = []
    best_intent, best_score = "unknown", 0.0
    for intent, keys in RULES:
        score = sum(1 for k in keys if k in text)
        if score > best_score:
            best_intent, best_score = intent, float(score)
            reasons = [f"matched:{k}" for k in keys if k in text]
    # payload hints
    if req.payload:
        if "leads" in req.payload:
            if best_score == 0:
                best_intent = "lead_enrichment"; best_score = 1.0
            reasons.append("payload:leads")
        if "campaign" in req.payload and isinstance(req.payload.get("campaign"), dict):
            if best_score < 2:
                best_intent = "start_campaign"; best_score = max(best_score, 2.0)
            reasons.append("payload:campaign")
    confidence = min(0.95, 0.3 + 0.2 * best_score)
    return best_intent, confidence, reasons
