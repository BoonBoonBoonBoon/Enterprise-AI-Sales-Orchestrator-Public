from __future__ import annotations

from typing import Dict, Any, List
import os
import json
from functools import lru_cache

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

from core.schemas.manager import UnifiedManagerRequest, ManagerDecision

ORCH_ALIASES = {"outreach": "outbound"}

# Built-in defaults as a safe fallback
DEFAULT_INTENT_TO_ORCH = {
    "start_campaign": ["control", "leads", "outbound"],
    "lead_enrichment": ["leads"],
    "outbound": ["outbound"],
    "outreach": ["outbound"],
    "audit": ["audit"],
    # Inbound email is currently handled by LeadsOrchestrator (deep reply flow + persistence/RAG)
    # and then chained by Manager to Outbound for Copywriter.
    "inbound": ["leads"],
    "control": ["control"],
    # Lead qualification: evaluate staging leads for promotion to leads table
    "qualify_lead": ["leads"],
}


def determine_context_depth(req: UnifiedManagerRequest) -> str:
    """Decide whether a request needs deep context (conversation-aware) or shallow.

    Deep triggers:
    - actions_allowed contains "reply" (implies tailored response)
    - payload.context.email_event present
    - goal/text mention reply/history/thread/context keywords
    """
    try:
        payload = req.payload if isinstance(req.payload, dict) else {}
        ctx = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        actions_allowed = ctx.get("actions_allowed") if isinstance(ctx.get("actions_allowed"), list) else []
        email_event = ctx.get("email_event")

        reply_allowed = "reply" in [str(x).lower() for x in actions_allowed]
        has_email = isinstance(email_event, dict) and bool(email_event)

        text_blobs = " ".join(
            [
                str(req.subject or ""),
                str(req.text or ""),
                json.dumps(payload, default=str) if payload else "",
            ]
        ).lower()
        deep_keywords = ["reply", "respond", "thread", "history", "context", "previous", "conversation"]
        keyword_hit = any(k in text_blobs for k in deep_keywords)

        if reply_allowed or has_email or keyword_hit:
            return "deep"
    except Exception:
        pass
    return "shallow"


def stream_for(tenant_id: str, orch: str) -> str:
    return f"{tenant_id}:orchestrators:{canonical_orchestrator(orch)}:tasks"


def canonical_orchestrator(orch: str) -> str:
    """Map legacy orchestrator names to canonical values."""
    return ORCH_ALIASES.get(orch, orch)


def _default_routing() -> Dict[str, List[str]]:
    return DEFAULT_INTENT_TO_ORCH


@lru_cache(maxsize=128)
def get_routing_map(tenant_id: str | None = None) -> Dict[str, List[str]]:
    """Load routing map from YAML configuration with tenant override.

    Search order:
    1) config/tenants/{tenant_id}/manager_routing.yaml (if tenant_id provided)
    2) config/manager/routing.yaml
    3) DEFAULT_INTENT_TO_ORCH
    """
    # Allow override via env var
    env_path = os.getenv("MANAGER_ROUTING_CONFIG")
    if env_path and os.path.isfile(env_path):
        try:
            if yaml is None:
                raise RuntimeError("PyYAML is required for MANAGER_ROUTING_CONFIG")
            with open(env_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            intents = data.get("intents", {})
            return intents or _default_routing()
        except Exception:
            return _default_routing()

    # Tenant-specific override
    if tenant_id:
        tenant_path = os.path.join(
            "config", "tenants", str(tenant_id), "manager_routing.yaml"
        )
        if os.path.isfile(tenant_path):
            try:
                if yaml is None:
                    raise RuntimeError("PyYAML is required for YAML routing config")
                with open(tenant_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                intents = data.get("intents", {})
                if intents:
                    return intents
            except Exception:
                pass

    # Default config
    default_path = os.path.join("config", "manager", "routing.yaml")
    if os.path.isfile(default_path):
        try:
            if yaml is None:
                raise RuntimeError("PyYAML is required for YAML routing config")
            with open(default_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            intents = data.get("intents", {})
            return intents or _default_routing()
        except Exception:
            return _default_routing()

    return _default_routing()


def _get_default_fallback_orchestrator(tenant_id: str | None = None) -> str:
    # Env override first
    env_val = os.getenv("MANAGER_DEFAULT_FALLBACK_ORCH")
    if env_val:
        return env_val

    # Try read from tenant or default YAML
    # Not caching separately; acceptable as we use small files and lru_cache on map
    try:
        import yaml  # type: ignore
        if tenant_id:
            tenant_path = os.path.join("config", "tenants", str(tenant_id), "manager_routing.yaml")
            if os.path.isfile(tenant_path):
                with open(tenant_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                v = data.get("default_fallback_orchestrator")
                if isinstance(v, str) and v:
                    return v
        default_path = os.path.join("config", "manager", "routing.yaml")
        if os.path.isfile(default_path):
            with open(default_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            v = data.get("default_fallback_orchestrator")
            if isinstance(v, str) and v:
                return v
    except Exception:
        pass
    return "control"  # hard default


def build_plan(intent: str, confidence: float, reasons: List[str], req: UnifiedManagerRequest) -> ManagerDecision:
    context_depth = determine_context_depth(req)
    mapping = get_routing_map(req.tenant_id or "default")
    orch_list = mapping.get(intent, [])
    used_fallback = False
    if not orch_list:
        # Use configured fallback orchestrator if mapping missing
        fallback = _get_default_fallback_orchestrator(req.tenant_id)
        orch_list = [fallback]
        used_fallback = True
    canonical_orch_list: List[str] = []
    for orch in orch_list:
        canon = canonical_orchestrator(orch)
        if canon not in canonical_orch_list:
            canonical_orch_list.append(canon)

    tasks: List[Dict[str, Any]] = []
    for orch in canonical_orch_list:
        task = {
            "stream": stream_for(req.tenant_id or "default", orch),
            "payload": {
                "tenant_id": req.tenant_id,
                "source": req.source,
                "intent": intent,
                "subject": req.subject,
                "text": req.text,
                "payload": req.payload or {},
            },
        }
        tasks.append(task)
    return ManagerDecision(
        intent=intent,
        confidence=confidence,
        reasons=reasons,
        orchestrators=canonical_orch_list,
        tasks=tasks,
        used_fallback=used_fallback,
        context_depth=context_depth,
    )
