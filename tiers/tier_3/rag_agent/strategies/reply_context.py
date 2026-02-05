"""Reply context strategy.

Assembles lead + conversation + messages for reply generation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# Token limits for context window management
MAX_CONTEXT_TOKENS = int(os.getenv("RAG_MAX_CONTEXT_TOKENS", "8000"))
CHARS_PER_TOKEN = float(os.getenv("RAG_CHARS_PER_TOKEN", "4.0"))


def _estimate_tokens(text: str) -> int:
    """Estimate token count for text."""
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def _estimate_message_tokens(message: Dict[str, Any]) -> int:
    """Estimate tokens for a message dict."""
    tokens = 4  # Base overhead
    body = message.get("body") or message.get("content") or ""
    if isinstance(body, str):
        tokens += _estimate_tokens(body)
    subject = message.get("subject") or ""
    if isinstance(subject, str):
        tokens += _estimate_tokens(subject)
    return tokens + 10  # Metadata overhead


def _truncate_messages_by_tokens(
    messages: List[Dict[str, Any]],
    max_tokens: int,
) -> List[Dict[str, Any]]:
    """
    Truncate messages to fit within token budget.
    
    Preserves most recent messages (most relevant for replies).
    """
    if not messages:
        return []
    
    # Process from newest to oldest (most relevant first)
    reversed_messages = list(reversed(messages))
    result = []
    total_tokens = 0
    
    for msg in reversed_messages:
        tokens = _estimate_message_tokens(msg)
        if total_tokens + tokens > max_tokens:
            logger.debug(
                "Token limit reached: %d + %d > %d, keeping %d messages",
                total_tokens, tokens, max_tokens, len(result),
            )
            break
        result.append(msg)
        total_tokens += tokens
    
    # Restore chronological order
    return list(reversed(result))


def _as_list(result: Any) -> List[Dict[str, Any]]:
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    if isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
    return []


def _as_record(result: Any) -> Optional[Dict[str, Any]]:
    if isinstance(result, dict) and result.get("id"):
        return result
    if isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, dict) and data.get("id"):
            return data
    return None


def build_reply_context(
    adapter,
    *,
    email: Optional[str] = None,
    lead_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    subject: Optional[str] = None,
    max_messages: int = 20,
    max_tokens: Optional[int] = None,
    include_lead_profile: bool = True,
    include_all_threads: bool = True,
) -> Dict[str, Any]:
    """
    Primary retrieval path for reply generation.

    Steps:
    1) Find lead in leads or staging_leads
    2) Select relevant conversation (thread_id > subject > recency)
    3) Fetch message history (chronological)
    4) Optionally include other thread summaries
    5) Truncate to fit within token budget (if max_tokens specified)
    
    Args:
        adapter: Database adapter for queries
        email: Lead email to search for
        lead_id: Lead ID to search for
        thread_id: Specific thread to retrieve
        subject: Subject to match
        max_messages: Maximum messages to retrieve (default: 20)
        max_tokens: Optional token limit for context window
        include_lead_profile: Include full lead profile in result
        include_all_threads: Include summaries of other threads
    """
    trace = {"steps": [], "errors": []}
    result: Dict[str, Any] = {
        "status": "success",
        "retrieved_at": datetime.utcnow().isoformat(),
    }

    # Find lead
    lead_data = _find_lead(adapter, email=email, lead_id=lead_id, trace=trace)
    if not lead_data.get("lead"):
        return {
            "status": "lead_not_found",
            "query_trace": trace,
            "retrieved_at": result["retrieved_at"],
            "error": f"No lead found for email={email} lead_id={lead_id}",
        }
    lead_source = lead_data["source"]
    result["lead"] = lead_data["lead"] if include_lead_profile else None
    result["lead_source"] = lead_source
    resolved_lead_id = lead_data["lead"].get("id")

    # Pick conversation
    conv_data = _select_conversation(
        adapter,
        lead_id=resolved_lead_id,
        lead_source=lead_source,
        thread_id=thread_id,
        subject=subject,
        trace=trace,
    )
    if not conv_data.get("conversation"):
        return {
            "status": "no_conversations",
            "lead": result.get("lead"),
            "lead_source": lead_source,
            "query_trace": trace,
            "retrieved_at": result["retrieved_at"],
            "error": conv_data.get("reason", "no conversations"),
        }
    result["conversation"] = conv_data["conversation"]
    result["conversation_source"] = conv_data["source"]
    result["selection_reason"] = conv_data["reason"]

    # Messages
    messages = _get_messages(
        adapter,
        conversation_id=conv_data["conversation"].get("id"),
        conv_source=conv_data["source"],
        limit=max_messages,
        trace=trace,
    )
    
    # Apply token limit if specified
    if max_tokens and messages:
        messages = _truncate_messages_by_tokens(messages, max_tokens)
        trace["steps"].append({
            "action": "token_truncation",
            "original_count": len(messages),
            "max_tokens": max_tokens,
        })
    
    result["messages"] = messages
    result["message_count"] = len(messages)

    # Other threads (summaries only)
    if include_all_threads:
        other_threads = _get_other_threads(
            adapter,
            lead_id=resolved_lead_id,
            lead_source=lead_source,
            exclude_conversation_id=conv_data["conversation"].get("id"),
            trace=trace,
        )
        result["other_threads"] = other_threads

    result["query_trace"] = trace
    return result


def _find_lead(adapter, email: Optional[str], lead_id: Optional[str], trace: Dict[str, Any]) -> Dict[str, Any]:
    # Prefer email then id across both tables
    def _query(table: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            res = adapter.query(table=table, filters=filters, limit=1)
            data = _as_list(res)
            trace["steps"].append({"table": table, "filter": filters, "found": bool(data)})
            return data[0] if data else None
        except Exception as e:
            trace["errors"].append(f"{table} lookup error: {e}")
            return None

    if email:
        lead = _query("leads", {"email": email})
        if lead:
            return {"lead": lead, "source": "leads"}
    if lead_id:
        try:
            res = adapter.read(table="leads", id_value=lead_id)
            data = _as_record(res)
            trace["steps"].append({"table": "leads", "filter": {"id": lead_id}, "found": bool(data)})
            if data:
                return {"lead": data, "source": "leads"}
        except Exception as e:
            trace["errors"].append(f"leads id error: {e}")

    if email:
        lead = _query("staging_leads", {"email": email})
        if lead:
            return {"lead": lead, "source": "staging_leads"}
    if lead_id:
        try:
            res = adapter.read(table="staging_leads", id_value=lead_id)
            data = _as_record(res)
            trace["steps"].append({"table": "staging_leads", "filter": {"id": lead_id}, "found": bool(data)})
            if data:
                return {"lead": data, "source": "staging_leads"}
        except Exception as e:
            trace["errors"].append(f"staging_leads id error: {e}")

    return {"lead": None, "source": None}


def _select_conversation(
    adapter,
    *,
    lead_id: str,
    lead_source: str,
    thread_id: Optional[str],
    subject: Optional[str],
    trace: Dict[str, Any],
) -> Dict[str, Any]:
    table = "staging_conversations" if lead_source == "staging_leads" else "conversations"
    fk = "staging_lead_id" if lead_source == "staging_leads" else "lead_id"
    try:
        res = adapter.query(
            table=table,
            filters={fk: lead_id},
            limit=50,
            order_by="updated_at",
            descending=True,
        )
        convs = _as_list(res)
        trace["steps"].append({"table": table, "count": len(convs)})
    except Exception as e:
        trace["errors"].append(f"conversation fetch error: {e}")
        return {"conversation": None, "source": None, "reason": str(e)}

    if not convs:
        return {"conversation": None, "source": None, "reason": "no_conversations"}

    # thread_id priority
    if thread_id:
        for conv in convs:
            if conv.get("thread_id") == thread_id:
                return {"conversation": conv, "source": table, "reason": f"matched thread_id={thread_id}"}

    # subject priority
    if subject:
        s = subject.lower().strip()
        for conv in convs:
            csub = (conv.get("subject") or "").lower().strip()
            if s in csub or csub in s:
                return {"conversation": conv, "source": table, "reason": "matched subject"}

    return {"conversation": convs[0], "source": table, "reason": "most_recent_by_updated_at"}


def _get_messages(
    adapter,
    *,
    conversation_id: str,
    conv_source: str,
    limit: int,
    trace: Dict[str, Any],
) -> List[Dict[str, Any]]:
    msg_table = "staging_messages" if "staging" in conv_source else "messages"
    msg_fk = "staging_conversation_id" if "staging" in conv_source else "conversation_id"
    msg_time = "sent_at" if "staging" in conv_source else "created_at"
    try:
        res = adapter.query(
            table=msg_table,
            filters={msg_fk: conversation_id},
            limit=limit,
            order_by=msg_time,
            descending=False,
        )
        msgs = _as_list(res)
        trace["steps"].append({"table": msg_table, "count": len(msgs)})
        return msgs
    except Exception as e:
        trace["errors"].append(f"messages fetch error: {e}")
        return []


def _get_other_threads(
    adapter,
    *,
    lead_id: str,
    lead_source: str,
    exclude_conversation_id: str,
    trace: Dict[str, Any],
) -> List[Dict[str, Any]]:
    table = "staging_conversations" if lead_source == "staging_leads" else "conversations"
    fk = "staging_lead_id" if lead_source == "staging_leads" else "lead_id"
    try:
        res = adapter.query(
            table=table,
            filters={fk: lead_id},
            limit=20,
            order_by="updated_at",
            descending=True,
        )
        convs = _as_list(res)
    except Exception as e:
        trace["errors"].append(f"other threads error: {e}")
        return []

    summaries = []
    for conv in convs:
        if conv.get("id") == exclude_conversation_id:
            continue
        summaries.append(
            {
                "id": conv.get("id"),
                "subject": conv.get("subject"),
                "status": conv.get("status"),
                "last_message_at": conv.get("last_message_at") or conv.get("updated_at"),
                "message_count": conv.get("message_count", 0),
            }
        )
    return summaries
