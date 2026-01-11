from __future__ import annotations

from typing import Tuple, List
import os

from core.schemas.manager import UnifiedManagerRequest


ALLOWED_INTENTS = [
    "start_campaign",
    "lead_enrichment",
    "outreach",
    "audit",
    "inbound",
    "control",
]


def _try_openai_classify(prompt: str) -> tuple[str, float]:
    try:
        from openai import OpenAI  # type: ignore
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "unknown", 0.0
        client = OpenAI(api_key=api_key)
        # Use a small, cheap model if available; fall back to gpt-4o-mini if not set
        model = os.getenv("MANAGER_LLM_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "You are a classification service. Given the user's input and optional payload, "
                    "choose ONE intent from this set: start_campaign, lead_enrichment, outreach, audit, inbound, control. "
                    "Respond strictly as JSON: {\"intent\": <string>, \"confidence\": <float 0..1>}"
                )},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        content = resp.choices[0].message.content or "{}"
        import json as _json
        data = _json.loads(content)
        intent = str(data.get("intent", "unknown")).strip()
        conf = float(data.get("confidence", 0.0))
        if intent not in ALLOWED_INTENTS:
            intent = "unknown"
        return intent, max(0.0, min(1.0, conf))
    except Exception:
        return "unknown", 0.0


def classify_with_llm(req: UnifiedManagerRequest) -> Tuple[str, float, List[str]]:
    """Attempt LLM-based intent classification if an API key is present.

    - If ``OPENAI_API_KEY`` is not set, LLM is treated as disabled.
    - ``MANAGER_LLM_ENABLED`` acts only as a kill-switch: any falsy value
      ("0", "false", "no") disables LLM even if a key is present.

    Returns intent, confidence, reasons. If no LLM is available or an error
    occurs, returns "unknown" with an explanatory reason tag.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "unknown", 0.0, ["llm:disabled:no_api_key"]

    enabled_flag = os.getenv("MANAGER_LLM_ENABLED", "1").lower()
    if enabled_flag in ("0", "false", "no"):
        return "unknown", 0.0, ["llm:disabled:kill_switch"]

    # Build concise prompt
    import json as _json
    parts = {
        "subject": req.subject,
        "text": req.text,
        "payload": req.payload,
    }
    prompt = _json.dumps(parts, default=str)
    intent, conf = _try_openai_classify(prompt)
    reasons: List[str] = ["llm:openai"] if intent != "unknown" else ["llm:openai:no_decision"]
    return intent, conf, reasons
