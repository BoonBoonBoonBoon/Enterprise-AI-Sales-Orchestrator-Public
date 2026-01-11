from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.persistence.service import build_supabase_service, PersistenceService

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(record: Optional[Dict[str, Any]]) -> Optional[Any]:
    if isinstance(record, dict):
        return record.get("id")
    return None


def promote_staging_lead_to_lead(
    *, staging_lead_id: str, lead_id: str, service: Optional[PersistenceService] = None
) -> Dict[str, Any]:
    """Copy staging conversations/messages into primary tables, then archive staging rows.

    Uses only PersistenceService public APIs (write/upsert/query); avoids non-existent update().
    Soft-archives staging conversations/messages/leads via upsert on id.
    """

    svc = service or build_supabase_service()
    now = _utc_now_iso()

    created_conversations: List[Dict[str, Any]] = []
    created_messages = 0

    staging_convs = svc.query(
        "staging_conversations",
        filters={"staging_lead_id": staging_lead_id, "archived_at": None},
        limit=500,
    ) or []

    for sc in staging_convs:
        thread_id = sc.get("thread_id")
        subject = sc.get("subject")
        channel = sc.get("channel") or "email"

        conv_payload = {
            "lead_id": lead_id,
            "thread_id": thread_id,
            "subject": subject,
            "channel": channel,
            "metadata": sc.get("metadata") or {},
        }

        if thread_id:
            conv = svc.upsert("conversations", conv_payload, on_conflict=["lead_id", "thread_id"])
        else:
            conv = svc.write("conversations", conv_payload)

        conversation_id = _safe_id(conv)
        if not conversation_id:
            logger.warning(
                "Promotion: conversation missing id; skipping messages for staging_conversation=%s", sc.get("id")
            )
            continue

        created_conversations.append(conv)

        staging_msgs = svc.query(
            "staging_messages",
            filters={"staging_conversation_id": sc.get("id"), "archived_at": None},
            limit=2000,
        ) or []

        for sm in staging_msgs:
            message_id = sm.get("message_id")
            msg_payload = {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "direction": sm.get("direction") or sm.get("sender_type") or "inbound",
                "content": sm.get("content") or sm.get("body"),
                "metadata": sm.get("metadata") or {},
            }

            try:
                if message_id:
                    svc.upsert("messages", msg_payload, on_conflict=["conversation_id", "message_id"])
                else:
                    svc.write("messages", msg_payload)
                created_messages += 1
            except Exception as exc:
                logger.warning(
                    "Promotion: failed to write message for staging_message=%s (%s)", sm.get("id"), exc
                )

            sm_id = _safe_id(sm)
            if sm_id:
                svc.upsert("staging_messages", {"id": sm_id, "archived_at": now}, on_conflict=["id"])

        sc_id = _safe_id(sc)
        if sc_id:
            svc.upsert("staging_conversations", {"id": sc_id, "archived_at": now}, on_conflict=["id"])

    try:
        svc.upsert(
            "staging_leads",
            {"id": staging_lead_id, "archived_at": now},
            on_conflict=["id"],
        )
    except Exception as exc:
        logger.warning("Promotion: failed to archive staging_lead=%s (%s)", staging_lead_id, exc)

    return {
        "ok": True,
        "staging_lead_id": staging_lead_id,
        "lead_id": lead_id,
        "copied_conversations": len(created_conversations),
        "copied_messages": created_messages,
        "archived_at": now,
    }
