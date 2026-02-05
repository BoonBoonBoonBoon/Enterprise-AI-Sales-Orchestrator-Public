"""Conversation selection strategies.

Business rules for choosing which conversation to use in replies.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _as_list(result: Any) -> List[Dict[str, Any]]:
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    if isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
    return []


def _conversation_table(lead_source: str) -> Dict[str, str]:
    if lead_source == "staging_leads":
        return {"table": "staging_conversations", "fk": "staging_lead_id", "msg_table": "staging_messages", "msg_fk": "staging_conversation_id", "msg_time": "sent_at"}
    return {"table": "conversations", "fk": "lead_id", "msg_table": "messages", "msg_fk": "conversation_id", "msg_time": "created_at"}


def get_relevant_conversation(
    adapter,
    lead_id: str,
    lead_source: str = "leads",
    selection_criteria: str = "most_recent_inbound",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Select the most relevant conversation for a lead.

    selection_criteria options:
    - most_recent_inbound (default)
    - most_recent_any
    - open_only
    - by_thread_id (requires context.thread_id)
    - by_subject (requires context.subject)
    """
    context = context or {}
    cfg = _conversation_table(lead_source)
    trace = {"steps": [], "criteria": selection_criteria}

    try:
        res = adapter.query(
            table=cfg["table"],
            filters={cfg["fk"]: lead_id},
            limit=50,
            order_by="updated_at",
            descending=True,
        )
        conversations = _as_list(res)
        trace["steps"].append({"table": cfg["table"], "count": len(conversations)})
    except Exception as e:
        logger.error(f"Conversation fetch failed: {e}")
        return {"status": "error", "error": str(e), "query_trace": trace}

    if not conversations:
        return {"status": "not_found", "conversation": None, "selection_reason": "no_conversations", "query_trace": trace}

    # Priority: thread_id
    thread_id = context.get("thread_id")
    if selection_criteria == "by_thread_id" and thread_id:
        for conv in conversations:
            if conv.get("thread_id") == thread_id:
                return {"status": "found", "conversation": conv, "selection_reason": f"matched thread_id={thread_id}", "query_trace": trace}
        # fall back
        selection_criteria = "most_recent_any"

    # Priority: subject
    subject = context.get("subject")
    if selection_criteria == "by_subject" and subject:
        subj_norm = subject.lower().strip()
        for conv in conversations:
            csubj = (conv.get("subject") or "").lower().strip()
            if subj_norm in csubj or csubj in subj_norm:
                return {"status": "found", "conversation": conv, "selection_reason": "matched subject", "query_trace": trace}
        selection_criteria = "most_recent_any"

    if selection_criteria == "open_only":
        open_convs = [c for c in conversations if c.get("status") == "open"]
        if open_convs:
            return {"status": "found", "conversation": open_convs[0], "selection_reason": "most_recent_open", "query_trace": trace}
        selection_criteria = "most_recent_any"

    if selection_criteria == "most_recent_inbound":
        msg_table = cfg["msg_table"]
        msg_fk = cfg["msg_fk"]
        msg_time = cfg["msg_time"]
        inbound_filter = {"direction": "inbound"} if lead_source == "staging_leads" else {"sender_type": "lead"}
        best = None
        best_time = None
        for conv in conversations[:10]:
            try:
                msgs = adapter.query(
                    table=msg_table,
                    filters={msg_fk: conv.get("id"), **inbound_filter},
                    limit=1,
                    order_by=msg_time,
                    descending=True,
                )
                data = _as_list(msgs)
                if data:
                    t = data[0].get(msg_time)
                    if t and (best_time is None or t > best_time):
                        best_time = t
                        best = conv
            except Exception:
                continue
        if best:
            return {"status": "found", "conversation": best, "selection_reason": f"most_recent_inbound_at={best_time}", "query_trace": trace}
        # fall through to most recent any

    # Default: most recent any
    return {"status": "found", "conversation": conversations[0], "selection_reason": "most_recent_by_updated_at", "query_trace": trace}


def get_all_conversations_ranked(
    adapter,
    lead_id: str,
    lead_source: str = "leads",
    ranking: str = "recency",
    limit: int = 10,
) -> Dict[str, Any]:
    """Return conversations ordered by ranking heuristic."""
    cfg = _conversation_table(lead_source)
    try:
        res = adapter.query(
            table=cfg["table"],
            filters={cfg["fk"]: lead_id},
            limit=min(limit, 50),
            order_by="updated_at",
            descending=True,
        )
        convs = _as_list(res)

        if ranking == "message_count":
            convs.sort(key=lambda c: c.get("message_count", 0), reverse=True)
        elif ranking == "open_first":
            convs.sort(key=lambda c: (0 if c.get("status") == "open" else 1, c.get("updated_at", "")))

        return {"status": "success", "conversations": convs, "count": len(convs), "ranking_applied": ranking}
    except Exception as e:
        logger.error(f"Rank conversations failed: {e}")
        return {"status": "error", "error": str(e)}
