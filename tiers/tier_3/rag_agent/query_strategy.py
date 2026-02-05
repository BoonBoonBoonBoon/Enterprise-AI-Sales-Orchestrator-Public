"""
Cascading Query Strategy for RAG Agent

Defines table lookup order, search criteria, and fallback behavior for multi-table
context retrieval. Provides full trace logging for debugging which tables were
queried and what was found.

Key concepts:
- PRIMARY tables are tried first (e.g., `leads` for email lookup)
- FALLBACK tables are tried if primary yields no results (e.g., `staging_leads`)
- ENRICHMENT tables add context after finding the primary record (e.g., `conversations`, `messages`)
- Query trace logs every step for observability
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class SupportsQuery(Protocol):
    """Minimal protocol for a DB adapter that can query/read tables."""

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> Any:
        ...

    def read(
        self,
        table: str,
        id_value: Any,
        id_column: str = "id",
    ) -> Any:
        ...


@dataclass
class QueryStep:
    """Record of a single query attempt."""

    table: str
    search_key: str  # e.g., "email", "lead_id"
    search_value: Any
    found: bool
    record_count: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    note: Optional[str] = None  # e.g., "fallback", "enrichment"


@dataclass
class QueryTrace:
    """Full trace of a cascading query operation."""

    operation: str  # e.g., "get_lead_context"
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    steps: List[QueryStep] = field(default_factory=list)
    total_duration_ms: float = 0.0
    final_status: str = "pending"  # "success", "not_found", "error"
    primary_table_hit: Optional[str] = None
    fallback_used: bool = False
    error_count: int = 0

    def add_step(self, step: QueryStep) -> None:
        self.steps.append(step)
        if step.error:
            self.error_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "started_at": self.started_at,
            "total_duration_ms": self.total_duration_ms,
            "final_status": self.final_status,
            "primary_table_hit": self.primary_table_hit,
            "fallback_used": self.fallback_used,
            "error_count": self.error_count,
            "steps": [
                {
                    "table": s.table,
                    "search_key": s.search_key,
                    "search_value": str(s.search_value)[:50] if s.search_value else None,
                    "found": s.found,
                    "record_count": s.record_count,
                    "duration_ms": round(s.duration_ms, 2),
                    "note": s.note,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }


# ============================================================================
# TABLE LOOKUP CONFIGURATIONS
# ============================================================================

# For email-based lead lookup: try leads first, then staging_leads
EMAIL_LOOKUP_CASCADE = [
    {
        "table": "leads",
        "search_column": "email",
        "role": "primary",
        "description": "Qualified leads table",
    },
    {
        "table": "staging_leads",
        "search_column": "email",
        "role": "fallback",
        "description": "Pre-qualification staging leads",
    },
]

# For domain-based lookup (fallback when exact email not found). Uses ilike pattern search.
DOMAIN_LOOKUP_CASCADE = [
    {
        "table": "leads",
        "search_column": "email",
        "role": "primary",
        "description": "Qualified leads table (domain match)",
    },
    {
        "table": "staging_leads",
        "search_column": "email",
        "role": "fallback",
        "description": "Pre-qualification staging leads (domain match)",
    },
]

# Common freemail providers to ignore when domain-matching
FREEMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}

# For lead_id-based lookup
LEAD_ID_LOOKUP_CASCADE = [
    {
        "table": "leads",
        "search_column": "id",
        "role": "primary",
        "description": "Qualified leads table",
    },
    {
        "table": "staging_leads",
        "search_column": "id",
        "role": "fallback",
        "description": "Staging leads (if not yet promoted)",
    },
]

# Enrichment tables to query after finding the lead
LEAD_ENRICHMENT_TABLES = [
    {
        "table": "conversations",
        "fk_column": "lead_id",
        "order_by": "created_at",
        "descending": True,
        "default_limit": 5,
        "description": "Lead's conversation threads",
    },
    {
        "table": "messages",
        "fk_column": "conversation_id",  # Linked via conversation
        "order_by": "created_at",
        "descending": False,
        "default_limit": 50,
        "description": "Messages from latest conversation",
    },
]

STAGING_ENRICHMENT_TABLES = [
    {
        "table": "staging_conversations",
        "fk_column": "staging_lead_id",
        "order_by": "created_at",
        "descending": True,
        "default_limit": 5,
        "description": "Staging lead conversation threads",
    },
    {
        "table": "staging_messages",
        "fk_column": "staging_conversation_id",  # Linked via staging conversation
        "order_by": "created_at",
        "descending": False,
        "default_limit": 50,
        "description": "Messages from latest staging conversation",
    },
]


# ============================================================================
# CASCADING QUERY EXECUTOR
# ============================================================================


def cascading_lead_lookup(
    adapter: SupportsQuery,
    *,
    email: Optional[str] = None,
    lead_id: Optional[str] = None,
    conversation_limit: int = 5,
    message_limit: int = 50,
) -> Dict[str, Any]:
    """
    Perform cascading lead lookup with full trace.

    Strategy:
    1. If email provided: try leads.email → staging_leads.email
    2. If lead_id provided (and email failed): try leads.id → staging_leads.id
    3. Once lead found: enrich with conversations → messages

    Returns:
        {
            "status": "success" | "not_found" | "error",
            "lead": {...} or None,
            "lead_source": "leads" | "staging_leads" | None,
            "conversations": [...],
            "messages": [...],
            "query_trace": {...}
        }
    """
    import time

    start_time = time.time()
    trace = QueryTrace(operation="get_lead_context")

    # Clamp limits to avoid runaway queries or zero/negative limits
    def _clamp_limit(value: Optional[int], default: int, max_value: int) -> int:
        try:
            iv = int(value) if value is not None else default
        except Exception:
            iv = default
        return max(1, min(iv, max_value))

    conv_limit = _clamp_limit(conversation_limit, default=5, max_value=25)
    msg_limit = _clamp_limit(message_limit, default=50, max_value=200)

    lead_record = None
    lead_source = None
    match_reason: Optional[str] = None
    conversations: List[Dict[str, Any]] = []
    messages: List[Dict[str, Any]] = []

    def _query_table(
        table: str,
        search_key: str,
        search_value: Any,
        note: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Query a single table and log the step."""
        step_start = time.time()
        step = QueryStep(
            table=table,
            search_key=search_key,
            search_value=search_value,
            found=False,
            note=note,
        )
        try:
            if search_key == "id":
                result = adapter.read(table=table, id_value=search_value, id_column="id")
                # adapter.read() returns the record dict directly or None
                data = result if isinstance(result, dict) and "id" in result else (result.get("data") if isinstance(result, dict) else None)
                if data:
                    step.found = True
                    step.record_count = 1
                    step.duration_ms = (time.time() - step_start) * 1000
                    trace.add_step(step)
                    return data
            else:
                result = adapter.query(table=table, filters={search_key: search_value}, limit=1)
                # adapter.query() returns List directly, not {"data": [...]}
                records = result if isinstance(result, list) else (result.get("data", []) if isinstance(result, dict) else [])
                if records:
                    step.found = True
                    step.record_count = len(records)
                    step.duration_ms = (time.time() - step_start) * 1000
                    trace.add_step(step)
                    return records[0]

            step.duration_ms = (time.time() - step_start) * 1000
            trace.add_step(step)
            return None

        except Exception as e:
            step.error = str(e)[:100]
            step.duration_ms = (time.time() - step_start) * 1000
            trace.add_step(step)
            logger.warning(f"Query failed: table={table} key={search_key} error={e}")
            return None

    def _query_list(
        table: str,
        filters: Dict[str, Any],
        limit: int,
        order_by: Optional[str] = None,
        descending: bool = False,
        note: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query table for multiple records."""
        step_start = time.time()
        fk_col = list(filters.keys())[0] if filters else "unknown"
        fk_val = list(filters.values())[0] if filters else None
        step = QueryStep(
            table=table,
            search_key=fk_col,
            search_value=fk_val,
            found=False,
            note=note,
        )
        try:
            result = adapter.query(
                table=table,
                filters=filters,
                limit=limit,
                order_by=order_by,
                descending=descending,
            )
            # adapter.query() returns List directly, not {"data": [...]}
            records = result if isinstance(result, list) else (result.get("data", []) if isinstance(result, dict) else [])
            step.found = bool(records)
            step.record_count = len(records)
            step.duration_ms = (time.time() - step_start) * 1000
            trace.add_step(step)
            return records
        except Exception as e:
            step.error = str(e)[:100]
            step.duration_ms = (time.time() - step_start) * 1000
            trace.add_step(step)
            logger.warning(f"Query failed: table={table} filters={filters} error={e}")
            return []

    # Step 1: Email-based cascade
    if email:
        for cfg in EMAIL_LOOKUP_CASCADE:
            record = _query_table(
                table=cfg["table"],
                search_key=cfg["search_column"],
                search_value=email,
                note=cfg["role"],
            )
            if record:
                lead_record = record
                lead_source = cfg["table"]
                match_reason = "email_exact"
                trace.primary_table_hit = cfg["table"]
                if cfg["role"] == "fallback":
                    trace.fallback_used = True
                break

    # Step 1b: Domain-based cascade (only if email not found and not freemail)
    if lead_record is None and email and "@" in email:
        domain = email.split("@", 1)[1].lower().strip()
        if domain and domain not in FREEMAIL_DOMAINS:
            domain_pattern = f"%@{domain}"
            for cfg in DOMAIN_LOOKUP_CASCADE:
                record = _query_table(
                    table=cfg["table"],
                    search_key=cfg["search_column"],
                    search_value=domain_pattern,
                    note=f"{cfg['role']}:domain",
                )
                if record:
                    lead_record = record
                    lead_source = cfg["table"]
                    match_reason = "domain_match"
                    trace.primary_table_hit = cfg["table"]
                    trace.fallback_used = trace.fallback_used or cfg.get("role") == "fallback"
                    break

    # Step 2: lead_id-based cascade (if email didn't find anything)
    if lead_record is None and lead_id:
        for cfg in LEAD_ID_LOOKUP_CASCADE:
            record = _query_table(
                table=cfg["table"],
                search_key=cfg["search_column"],
                search_value=lead_id,
                note=cfg["role"],
            )
            if record:
                lead_record = record
                lead_source = cfg["table"]
                trace.primary_table_hit = cfg["table"]
                if cfg["role"] == "fallback":
                    trace.fallback_used = True
                break

    # Step 2b: staging message → conversation → staging lead (fallback)
    # If we have no lead yet but the sender email matches a staging_message, recover the lead via that conversation.
    if lead_record is None and email:
        msg_record = _query_table(
            table="staging_messages",
            search_key="sender",
            search_value=email,
            note="fallback:staging_message_sender",
        )
        if msg_record:
            conv_id = msg_record.get("staging_conversation_id")
            conv_record = None
            if conv_id:
                conv_record = _query_table(
                    table="staging_conversations",
                    search_key="id",
                    search_value=conv_id,
                    note="fallback:staging_conversation_by_message",
                )

            staging_lead_id = conv_record.get("staging_lead_id") if isinstance(conv_record, dict) else None
            if staging_lead_id:
                recovered_lead = _query_table(
                    table="staging_leads",
                    search_key="id",
                    search_value=staging_lead_id,
                    note="fallback:staging_lead_by_conversation",
                )
                if recovered_lead:
                    lead_record = recovered_lead
                    lead_source = "staging_leads"
                    match_reason = "message_sender_match"
                    trace.primary_table_hit = "staging_leads"
                    trace.fallback_used = True

                    # Enrich from the same conversation/messages to give context downstream.
                    if conv_record:
                        conversations = [conv_record]
                        messages = _query_list(
                            table="staging_messages",
                            filters={"staging_conversation_id": conv_id},
                            limit=msg_limit,
                            order_by="sent_at",
                            descending=True,
                            note="enrichment",
                        )

    # Step 3: Enrichment (conversations + messages) if lead found
    if lead_record:
        lead_id_val = lead_record.get("id")

        if lead_id_val:
            enrichment_cfg = (
                STAGING_ENRICHMENT_TABLES if lead_source == "staging_leads" else LEAD_ENRICHMENT_TABLES
            )

            # Get conversations (or staging conversations)
            conv_cfg = enrichment_cfg[0]
            conversations = _query_list(
                table=conv_cfg["table"],
                filters={conv_cfg["fk_column"]: lead_id_val},
                limit=conv_limit,
                order_by=conv_cfg.get("order_by"),
                descending=conv_cfg.get("descending", False),
                note="enrichment",
            )

            # Get messages from latest conversation (or staging conversation)
            if conversations:
                latest_conv_id = conversations[0].get("id")
                if latest_conv_id:
                    msg_cfg = enrichment_cfg[1]
                    messages = _query_list(
                        table=msg_cfg["table"],
                        filters={msg_cfg["fk_column"]: latest_conv_id},
                        limit=msg_limit,
                        order_by=msg_cfg.get("order_by"),
                        descending=msg_cfg.get("descending", False),
                        note="enrichment",
                    )

    # Finalize trace
    trace.total_duration_ms = (time.time() - start_time) * 1000

    if lead_record:
        trace.final_status = "success"
    elif trace.error_count and trace.error_count == len(trace.steps):
        trace.final_status = "error"
    else:
        trace.final_status = "not_found"

    # Log summary
    logger.info(
        f"[RAG] cascading_lead_lookup: status={trace.final_status} "
        f"source={lead_source} fallback={trace.fallback_used} "
        f"steps={len(trace.steps)} duration_ms={trace.total_duration_ms:.1f}"
    )

    return {
        "status": trace.final_status,
        "lead": lead_record,
        "lead_source": lead_source,
        "match_reason": match_reason,
        "conversations": conversations,
        "messages": messages,
        "query_trace": trace.to_dict(),
    }


def unified_lead_context(
    adapter: SupportsQuery,
    *,
    email: Optional[str] = None,
    lead_id: Optional[str] = None,
    conversation_limit: int = 10,
    message_limit: int = 50,
) -> Dict[str, Any]:
    """
    Unified lead context retrieval — searches BOTH leads and staging_leads in parallel.

    Unlike cascading_lead_lookup (which stops at first hit), this function:
    1. Searches leads AND staging_leads simultaneously
    2. Returns ALL matching records from both tables
    3. Fetches conversations from ALL sources
    4. Lets the caller (Deep Agent) decide which data is most relevant

    This is better for reply generation where you need full context across
    the entire history, not just the first match.

    Returns:
        {
            "status": "success" | "not_found" | "error",
            "sources": {
                "leads": {
                    "lead": {...} or None,
                    "conversations": [...],
                    "messages_by_conversation": {conv_id: [...], ...}
                },
                "staging_leads": {
                    "lead": {...} or None,
                    "conversations": [...],
                    "messages_by_conversation": {conv_id: [...], ...}
                }
            },
            "summary": {
                "lead_found_in": ["leads", "staging_leads"],  # which tables had a match
                "total_conversations": int,
                "total_messages": int,
                "most_recent_conversation": {...} or None,
                "most_recent_message": {...} or None
            },
            "query_trace": {...}
        }
    """
    import time

    start_time = time.time()
    trace = QueryTrace(operation="unified_lead_context")

    # Clamp limits
    conv_limit = max(1, min(conversation_limit or 10, 50))
    msg_limit = max(1, min(message_limit or 50, 200))

    # Result structure
    sources: Dict[str, Dict[str, Any]] = {
        "leads": {"lead": None, "conversations": [], "messages_by_conversation": {}},
        "staging_leads": {"lead": None, "conversations": [], "messages_by_conversation": {}},
    }
    lead_found_in: List[str] = []

    def _query_single(table: str, key: str, value: Any, note: str) -> Optional[Dict[str, Any]]:
        """Query for a single record."""
        step_start = time.time()
        step = QueryStep(table=table, search_key=key, search_value=value, found=False, note=note)
        try:
            if key == "id":
                result = adapter.read(table=table, id_value=value, id_column="id")
                # adapter.read() returns the record dict directly or None
                data = result if isinstance(result, dict) and "id" in result else (result.get("data") if isinstance(result, dict) else None)
            else:
                result = adapter.query(table=table, filters={key: value}, limit=1)
                # adapter.query() returns List directly, not {"data": [...]}
                records = result if isinstance(result, list) else (result.get("data", []) if isinstance(result, dict) else [])
                data = records[0] if records else None

            step.found = data is not None
            step.record_count = 1 if data else 0
            step.duration_ms = (time.time() - step_start) * 1000
            trace.add_step(step)
            return data
        except Exception as e:
            step.error = str(e)[:100]
            step.duration_ms = (time.time() - step_start) * 1000
            trace.add_step(step)
            return None

    def _query_list(
        table: str, filters: Dict[str, Any], limit: int, order_by: str, desc: bool, note: str
    ) -> List[Dict[str, Any]]:
        """Query for multiple records."""
        step_start = time.time()
        fk = list(filters.keys())[0] if filters else "?"
        fv = list(filters.values())[0] if filters else None
        step = QueryStep(table=table, search_key=fk, search_value=fv, found=False, note=note)
        try:
            result = adapter.query(table=table, filters=filters, limit=limit, order_by=order_by, descending=desc)
            # adapter.query() returns List directly, not {"data": [...]}
            records = result if isinstance(result, list) else (result.get("data", []) if isinstance(result, dict) else [])
            step.found = bool(records)
            step.record_count = len(records)
            step.duration_ms = (time.time() - step_start) * 1000
            trace.add_step(step)
            return records
        except Exception as e:
            step.error = str(e)[:100]
            step.duration_ms = (time.time() - step_start) * 1000
            trace.add_step(step)
            return []

    # ============ PARALLEL SEARCH: LEADS ============
    lead_record = None
    if email:
        lead_record = _query_single("leads", "email", email, "parallel:leads:email")
    if not lead_record and lead_id:
        lead_record = _query_single("leads", "id", lead_id, "parallel:leads:id")

    if lead_record:
        sources["leads"]["lead"] = lead_record
        lead_found_in.append("leads")
        lid = lead_record.get("id")
        if lid:
            convs = _query_list("conversations", {"lead_id": lid}, conv_limit, "created_at", True, "enrich:leads:convs")
            sources["leads"]["conversations"] = convs
            for conv in convs:
                cid = conv.get("id")
                if cid:
                    msgs = _query_list("messages", {"conversation_id": cid}, msg_limit, "created_at", False, "enrich:leads:msgs")
                    sources["leads"]["messages_by_conversation"][cid] = msgs

    # ============ PARALLEL SEARCH: STAGING_LEADS ============
    staging_record = None
    if email:
        staging_record = _query_single("staging_leads", "email", email, "parallel:staging:email")
    if not staging_record and lead_id:
        staging_record = _query_single("staging_leads", "id", lead_id, "parallel:staging:id")

    if staging_record:
        sources["staging_leads"]["lead"] = staging_record
        lead_found_in.append("staging_leads")
        slid = staging_record.get("id")
        if slid:
            sconvs = _query_list("staging_conversations", {"staging_lead_id": slid}, conv_limit, "created_at", True, "enrich:staging:convs")
            sources["staging_leads"]["conversations"] = sconvs
            for sconv in sconvs:
                scid = sconv.get("id")
                if scid:
                    smsgs = _query_list("staging_messages", {"staging_conversation_id": scid}, msg_limit, "sent_at", False, "enrich:staging:msgs")
                    sources["staging_leads"]["messages_by_conversation"][scid] = smsgs

    # ============ SUMMARY STATS ============
    all_convs = sources["leads"]["conversations"] + sources["staging_leads"]["conversations"]
    all_msgs = []
    for mbc in sources["leads"]["messages_by_conversation"].values():
        all_msgs.extend(mbc)
    for mbc in sources["staging_leads"]["messages_by_conversation"].values():
        all_msgs.extend(mbc)

    # Find most recent conversation and message
    most_recent_conv = None
    most_recent_msg = None
    if all_convs:
        # Sort by created_at descending
        sorted_convs = sorted(all_convs, key=lambda c: c.get("created_at") or "", reverse=True)
        most_recent_conv = sorted_convs[0] if sorted_convs else None
    if all_msgs:
        # Sort by created_at or sent_at descending
        sorted_msgs = sorted(all_msgs, key=lambda m: m.get("created_at") or m.get("sent_at") or "", reverse=True)
        most_recent_msg = sorted_msgs[0] if sorted_msgs else None

    summary = {
        "lead_found_in": lead_found_in,
        "total_conversations": len(all_convs),
        "total_messages": len(all_msgs),
        "most_recent_conversation": most_recent_conv,
        "most_recent_message": most_recent_msg,
    }

    # Finalize
    trace.total_duration_ms = (time.time() - start_time) * 1000
    if lead_found_in:
        trace.final_status = "success"
        trace.primary_table_hit = lead_found_in[0]
    elif trace.error_count and trace.error_count == len(trace.steps):
        trace.final_status = "error"
    else:
        trace.final_status = "not_found"

    logger.info(
        f"[RAG] unified_lead_context: status={trace.final_status} "
        f"found_in={lead_found_in} convs={len(all_convs)} msgs={len(all_msgs)} "
        f"duration_ms={trace.total_duration_ms:.1f}"
    )

    return {
        "status": trace.final_status,
        "sources": sources,
        "summary": summary,
        "query_trace": trace.to_dict(),
    }


__all__ = [
    "QueryStep",
    "QueryTrace",
    "cascading_lead_lookup",
    "unified_lead_context",
    "EMAIL_LOOKUP_CASCADE",
    "LEAD_ID_LOOKUP_CASCADE",
    "LEAD_ENRICHMENT_TABLES",
    "STAGING_ENRICHMENT_TABLES",
]
