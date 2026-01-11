from __future__ import annotations

from typing import Any, Dict, Union, Optional
from core.schemas.manager import UnifiedManagerRequest


def normalize_input(
    data: Union[str, Dict[str, Any]],
    *,
    source: str = "unknown",
    content_type: Optional[str] = None,
    tenant_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> UnifiedManagerRequest:
    """Normalize free text or dict payloads into a UnifiedManagerRequest."""
    meta = meta or {}
    if isinstance(data, str):
        # Treat as free text
        return UnifiedManagerRequest(
            tenant_id=tenant_id,
            subject=None,
            text=data,
            payload=None,
            source=source,
            content_type=content_type,
            meta=meta,
        )

    if isinstance(data, dict):
        subject = str(data.get("subject") or data.get("title") or "")
        text = str(data.get("text") or data.get("message") or data.get("body") or "")
        tenant = tenant_id or data.get("tenant_id")
        correlation_id = data.get("correlation_id") or meta.get("correlation_id")
        return UnifiedManagerRequest(
            tenant_id=tenant,
            correlation_id=str(correlation_id) if correlation_id else None,
            subject=subject or None,
            text=text or None,
            payload=data,
            source=source,
            content_type=content_type,
            meta=meta,
        )

    # Fallback
    return UnifiedManagerRequest(
        tenant_id=tenant_id,
        text=str(data),
        source=source,
        content_type=content_type,
        meta=meta,
    )
