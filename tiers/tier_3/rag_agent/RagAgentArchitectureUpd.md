I'll help you design a comprehensive plan for the RAG agent's database engagement strategy. Let me first understand what retrieval patterns you need and then we'll build a modular, extensible architecture.

---

## RAG Agent Database Engagement Plan

### Current State Analysis

**What you have:**

- 2 context tools: `get_lead_context` (cascading) and `get_unified_lead_context` (parallel)
- 12 schema-specific tools (staging_leads, leads, conversations, messages)
- Deep Agent that _can_ choose tools but lacks clear decision rules

**What's missing:**

- **Query Strategies** as first-class concepts (not buried in tool code)
- **Retrieval Goals** that map business intents to query patterns
- **Conversation Selection Logic** (which thread to reference for replies)
- **Cross-table Joins** (e.g., "get all messages where lead.company = X")
- **Recency/Relevance Scoring** for conversations and messages

---

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAG AGENT                                │
│  (Deep Agent - decides WHAT to retrieve based on goal)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RETRIEVAL ROUTER                             │
│  Maps goal → retrieval_strategy → query_plan                    │
│  (Deterministic rules + LLM fallback for ambiguous goals)      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   QUERY STRATEGIES                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ lead_lookup  │ │ conversation │ │ message_     │            │
│  │ _strategy    │ │ _strategy    │ │ history      │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ reply_context│ │ enrichment_  │ │ analytics_   │            │
│  │ _strategy    │ │ check        │ │ strategy     │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SUPABASE ADAPTER                              │
│  (Read-only, deterministic SQL generation)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 1: Query Strategies Module

Create a dedicated module for retrieval strategies that the RAG agent tools call.

```python
"""
RAG Query Strategies

Deterministic retrieval patterns that tools invoke.
Each strategy:
1. Has a clear PURPOSE (when to use it)
2. Defines the QUERY PLAN (which tables, in what order)
3. Returns STRUCTURED output (consistent shape)
4. Includes DIAGNOSTICS (what was queried, what hit/missed)
"""

from .lead_lookup import (
    cascading_lead_lookup,
    unified_lead_lookup,
    lead_by_identifier,
)
from .conversation_selection import (
    get_relevant_conversation,
    get_all_conversations_ranked,
    get_conversation_by_recency,
    get_conversation_by_status,
)
from .message_history import (
    get_conversation_messages,
    get_recent_inbound_messages,
    get_thread_summary,
)
from .reply_context import (
    build_reply_context,
    get_full_thread_for_reply,
)
from .enrichment import (
    check_enrichment_status,
    get_enrichment_candidates,
)

__all__ = [
    # Lead lookup
    "cascading_lead_lookup",
    "unified_lead_lookup",
    "lead_by_identifier",
    # Conversation selection
    "get_relevant_conversation",
    "get_all_conversations_ranked",
    "get_conversation_by_recency",
    "get_conversation_by_status",
    # Message history
    "get_conversation_messages",
    "get_recent_inbound_messages",
    "get_thread_summary",
    # Reply context
    "build_reply_context",
    "get_full_thread_for_reply",
    # Enrichment
    "check_enrichment_status",
    "get_enrichment_candidates",
]
```

---

### Phase 2: Conversation Selection Strategy

This is the **key missing piece** — deciding which conversation is relevant.

```python
"""
Conversation Selection Strategy

Business rules for selecting which conversation(s) to use.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def get_relevant_conversation(
    adapter,
    lead_id: str,
    lead_source: str,  # "leads" or "staging_leads"
    selection_criteria: str = "most_recent_inbound",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Select the MOST RELEVANT conversation for a given lead.

    Selection Criteria Options:
    - "most_recent_inbound": Last conversation where lead sent a message (DEFAULT)
    - "most_recent_any": Last conversation by timestamp
    - "open_only": Most recent conversation with status='open'
    - "by_subject": Match conversation by subject line (requires context.subject)
    - "by_thread_id": Exact match on thread_id (requires context.thread_id)

    Args:
        adapter: Read-only Supabase adapter
        lead_id: The lead's UUID
        lead_source: Which table the lead came from
        selection_criteria: How to pick the conversation
        context: Additional context (subject, thread_id, etc.)

    Returns:
        {
            "status": "found" | "not_found",
            "conversation": {...} or None,
            "selection_reason": str,
            "alternatives_count": int,
            "query_trace": {...}
        }
    """
    context = context or {}
    query_trace = {"criteria": selection_criteria, "steps": []}

    # Determine conversation table based on lead source
    conv_table = "staging_conversations" if lead_source == "staging_leads" else "conversations"
    fk_column = "staging_lead_id" if lead_source == "staging_leads" else "lead_id"

    # Step 1: Get all conversations for this lead
    try:
        all_convos = adapter.query(
            table=conv_table,
            filters={fk_column: lead_id},
            limit=50,
            order_by="updated_at",
            descending=True,
        )
        conversations = all_convos.get("data", [])
        query_trace["steps"].append({
            "table": conv_table,
            "filter": {fk_column: lead_id},
            "count": len(conversations)
        })
    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}")
        return {
            "status": "error",
            "error": str(e),
            "query_trace": query_trace
        }

    if not conversations:
        return {
            "status": "not_found",
            "conversation": None,
            "selection_reason": "no_conversations_exist",
            "alternatives_count": 0,
            "query_trace": query_trace,
        }

    # Step 2: Apply selection criteria
    selected = None
    reason = ""

    if selection_criteria == "by_thread_id" and context.get("thread_id"):
        # Exact match on thread_id
        thread_id = context["thread_id"]
        for conv in conversations:
            if conv.get("thread_id") == thread_id:
                selected = conv
                reason = f"matched thread_id={thread_id}"
                break
        if not selected:
            reason = f"thread_id={thread_id} not found, falling back to most_recent"
            selected = conversations[0]
            reason += f", used conversation {selected.get('id')}"

    elif selection_criteria == "by_subject" and context.get("subject"):
        # Fuzzy match on subject
        target_subject = context["subject"].lower().strip()
        for conv in conversations:
            conv_subject = (conv.get("subject") or "").lower().strip()
            if target_subject in conv_subject or conv_subject in target_subject:
                selected = conv
                reason = f"matched subject containing '{target_subject[:30]}'"
                break
        if not selected:
            selected = conversations[0]
            reason = f"subject not matched, used most recent"

    elif selection_criteria == "open_only":
        # Only open conversations
        open_convos = [c for c in conversations if c.get("status") == "open"]
        if open_convos:
            selected = open_convos[0]
            reason = "most recent open conversation"
        else:
            selected = conversations[0]
            reason = "no open conversations, used most recent"

    elif selection_criteria == "most_recent_inbound":
        # Find conversation with most recent inbound message
        msg_table = "staging_messages" if lead_source == "staging_leads" else "messages"
        conv_fk = "staging_conversation_id" if lead_source == "staging_leads" else "conversation_id"

        best_conv = None
        best_time = None

        for conv in conversations[:10]:  # Check top 10 by recency
            try:
                msgs = adapter.query(
                    table=msg_table,
                    filters={conv_fk: conv.get("id"), "direction": "inbound"},
                    limit=1,
                    order_by="sent_at",
                    descending=True,
                )
                msg_list = msgs.get("data", [])
                if msg_list:
                    msg_time = msg_list[0].get("sent_at")
                    if msg_time and (best_time is None or msg_time > best_time):
                        best_time = msg_time
                        best_conv = conv
            except Exception as e:
                logger.warning(f"Failed to check messages for conv {conv.get('id')}: {e}")

        if best_conv:
            selected = best_conv
            reason = f"most recent inbound message at {best_time}"
        else:
            selected = conversations[0]
            reason = "no inbound messages found, used most recent conversation"

    else:  # "most_recent_any" or default
        selected = conversations[0]
        reason = "most recent by updated_at"

    return {
        "status": "found",
        "conversation": selected,
        "selection_reason": reason,
        "alternatives_count": len(conversations) - 1,
        "query_trace": query_trace,
    }


def get_all_conversations_ranked(
    adapter,
    lead_id: str,
    lead_source: str,
    ranking: str = "recency",
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Get all conversations for a lead, ranked by specified criteria.

    Ranking Options:
    - "recency": Most recently updated first
    - "message_count": Most messages first
    - "last_inbound": Most recent inbound message first
    - "open_first": Open conversations before closed

    Returns:
        {
            "status": "success",
            "conversations": [...],
            "count": int,
            "ranking_applied": str
        }
    """
    conv_table = "staging_conversations" if lead_source == "staging_leads" else "conversations"
    fk_column = "staging_lead_id" if lead_source == "staging_leads" else "lead_id"

    try:
        result = adapter.query(
            table=conv_table,
            filters={fk_column: lead_id},
            limit=min(limit, 50),
            order_by="updated_at",
            descending=True,
        )
        conversations = result.get("data", [])

        # Apply ranking
        if ranking == "message_count":
            conversations.sort(
                key=lambda c: c.get("message_count", 0),
                reverse=True
            )
        elif ranking == "open_first":
            conversations.sort(
                key=lambda c: (0 if c.get("status") == "open" else 1, c.get("updated_at", "")),
            )
        # "recency" is default from query

        return {
            "status": "success",
            "conversations": conversations,
            "count": len(conversations),
            "ranking_applied": ranking,
        }
    except Exception as e:
        logger.error(f"Failed to get ranked conversations: {e}")
        return {"status": "error", "error": str(e)}
```

---

### Phase 3: Reply Context Strategy (The Big One)

This is what you need for generating replies — full context assembly.

```python
"""
Reply Context Strategy

Assembles everything needed to generate a reply to a lead.
This is the PRIMARY retrieval path for reply generation.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def build_reply_context(
    adapter,
    email: Optional[str] = None,
    lead_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    subject: Optional[str] = None,
    max_messages: int = 20,
    include_lead_profile: bool = True,
    include_all_threads: bool = False,
) -> Dict[str, Any]:
    """
    Build complete context for generating a reply.

    This is the MAIN entry point for reply generation context.

    Strategy:
    1. Find the lead (unified search across leads + staging_leads)
    2. Select the relevant conversation (by thread_id > subject > recency)
    3. Fetch message history for that conversation
    4. Optionally include lead profile data
    5. Optionally include other thread summaries

    Args:
        adapter: Read-only Supabase adapter
        email: Lead's email (primary lookup)
        lead_id: Lead's UUID (alternative lookup)
        thread_id: Specific thread to reply to (highest priority)
        subject: Subject line to match (second priority)
        max_messages: Max messages to include (default 20)
        include_lead_profile: Include lead's profile data
        include_all_threads: Include summaries of other conversations

    Returns:
        {
            "status": "success" | "lead_not_found" | "no_conversations" | "error",

            # Lead info
            "lead": {...},
            "lead_source": "leads" | "staging_leads",

            # Selected conversation
            "conversation": {...},
            "conversation_source": "conversations" | "staging_conversations",
            "selection_reason": str,

            # Message history (chronological, oldest first)
            "messages": [...],
            "message_count": int,

            # Optional: other threads
            "other_threads": [
                {"id": ..., "subject": ..., "last_message_at": ..., "message_count": ...}
            ],

            # Diagnostics
            "query_trace": {...},
            "retrieved_at": "ISO timestamp"
        }
    """
    trace = {"steps": [], "errors": []}
    result = {
        "status": "success",
        "retrieved_at": datetime.utcnow().isoformat(),
    }

    # ========== STEP 1: Find the lead ==========
    lead_data = _find_lead_unified(adapter, email, lead_id, trace)

    if not lead_data.get("lead"):
        return {
            "status": "lead_not_found",
            "query_trace": trace,
            "retrieved_at": result["retrieved_at"],
            "error": f"No lead found for email={email}, lead_id={lead_id}"
        }

    result["lead"] = lead_data["lead"]
    result["lead_source"] = lead_data["source"]
    resolved_lead_id = lead_data["lead"].get("id")

    # ========== STEP 2: Select conversation ==========
    conv_data = _select_conversation(
        adapter,
        lead_id=resolved_lead_id,
        lead_source=lead_data["source"],
        thread_id=thread_id,
        subject=subject,
        trace=trace,
    )

    if not conv_data.get("conversation"):
        return {
            "status": "no_conversations",
            "lead": result["lead"],
            "lead_source": result["lead_source"],
            "query_trace": trace,
            "retrieved_at": result["retrieved_at"],
            "error": "Lead exists but has no conversations"
        }

    result["conversation"] = conv_data["conversation"]
    result["conversation_source"] = conv_data["source"]
    result["selection_reason"] = conv_data["reason"]

    # ========== STEP 3: Fetch messages ==========
    messages = _get_messages_for_conversation(
        adapter,
        conversation_id=conv_data["conversation"].get("id"),
        conv_source=conv_data["source"],
        limit=max_messages,
        trace=trace,
    )

    result["messages"] = messages
    result["message_count"] = len(messages)

    # ========== STEP 4: Optional - other threads ==========
    if include_all_threads:
        other_threads = _get_other_thread_summaries(
            adapter,
            lead_id=resolved_lead_id,
            lead_source=lead_data["source"],
            exclude_conversation_id=conv_data["conversation"].get("id"),
            trace=trace,
        )
        result["other_threads"] = other_threads

    result["query_trace"] = trace
    return result


def _find_lead_unified(
    adapter,
    email: Optional[str],
    lead_id: Optional[str],
    trace: Dict,
) -> Dict[str, Any]:
    """Find lead in both tables, return first match with source."""

    # Try production leads first
    if email:
        try:
            res = adapter.query(table="leads", filters={"email": email}, limit=1)
            data = res.get("data", [])
            trace["steps"].append({"table": "leads", "filter": "email", "found": bool(data)})
            if data:
                return {"lead": data[0], "source": "leads"}
        except Exception as e:
            trace["errors"].append(f"leads email lookup: {e}")

    if lead_id:
        try:
            res = adapter.read(table="leads", id_value=lead_id)
            data = res.get("data")
            trace["steps"].append({"table": "leads", "filter": "id", "found": bool(data)})
            if data:
                return {"lead": data, "source": "leads"}
        except Exception as e:
            trace["errors"].append(f"leads id lookup: {e}")

    # Try staging_leads
    if email:
        try:
            res = adapter.query(table="staging_leads", filters={"email": email}, limit=1)
            data = res.get("data", [])
            trace["steps"].append({"table": "staging_leads", "filter": "email", "found": bool(data)})
            if data:
                return {"lead": data[0], "source": "staging_leads"}
        except Exception as e:
            trace["errors"].append(f"staging_leads email lookup: {e}")

    if lead_id:
        try:
            res = adapter.read(table="staging_leads", id_value=lead_id)
            data = res.get("data")
            trace["steps"].append({"table": "staging_leads", "filter": "id", "found": bool(data)})
            if data:
                return {"lead": data, "source": "staging_leads"}
        except Exception as e:
            trace["errors"].append(f"staging_leads id lookup: {e}")

    return {"lead": None, "source": None}


def _select_conversation(
    adapter,
    lead_id: str,
    lead_source: str,
    thread_id: Optional[str],
    subject: Optional[str],
    trace: Dict,
) -> Dict[str, Any]:
    """Select the most relevant conversation."""

    conv_table = "staging_conversations" if lead_source == "staging_leads" else "conversations"
    fk_col = "staging_lead_id" if lead_source == "staging_leads" else "lead_id"

    try:
        res = adapter.query(
            table=conv_table,
            filters={fk_col: lead_id},
            limit=50,
            order_by="updated_at",
            descending=True,
        )
        conversations = res.get("data", [])
        trace["steps"].append({
            "table": conv_table,
            "filter": fk_col,
            "count": len(conversations)
        })
    except Exception as e:
        trace["errors"].append(f"conversation fetch: {e}")
        return {"conversation": None, "source": None, "reason": str(e)}

    if not conversations:
        return {"conversation": None, "source": None, "reason": "no_conversations"}

    # Priority 1: thread_id match
    if thread_id:
        for conv in conversations:
            if conv.get("thread_id") == thread_id:
                return {
                    "conversation": conv,
                    "source": conv_table,
                    "reason": f"matched thread_id={thread_id}"
                }

    # Priority 2: subject match
    if subject:
        subject_lower = subject.lower().strip()
        for conv in conversations:
            conv_subj = (conv.get("subject") or "").lower().strip()
            if subject_lower in conv_subj or conv_subj in subject_lower:
                return {
                    "conversation": conv,
                    "source": conv_table,
                    "reason": f"matched subject"
                }

    # Priority 3: most recent
    return {
        "conversation": conversations[0],
        "source": conv_table,
        "reason": "most_recent_by_updated_at"
    }


def _get_messages_for_conversation(
    adapter,
    conversation_id: str,
    conv_source: str,
    limit: int,
    trace: Dict,
) -> List[Dict[str, Any]]:
    """Get messages for a conversation, chronological order."""

    msg_table = "staging_messages" if "staging" in conv_source else "messages"
    fk_col = "staging_conversation_id" if "staging" in conv_source else "conversation_id"

    try:
        res = adapter.query(
            table=msg_table,
            filters={fk_col: conversation_id},
            limit=limit,
            order_by="sent_at",
            descending=False,  # Chronological: oldest first
        )
        messages = res.get("data", [])
        trace["steps"].append({
            "table": msg_table,
            "filter": fk_col,
            "count": len(messages)
        })
        return messages
    except Exception as e:
        trace["errors"].append(f"message fetch: {e}")
        return []


def _get_other_thread_summaries(
    adapter,
    lead_id: str,
    lead_source: str,
    exclude_conversation_id: str,
    trace: Dict,
) -> List[Dict[str, Any]]:
    """Get summaries of other conversations (not the selected one)."""

    conv_table = "staging_conversations" if lead_source == "staging_leads" else "conversations"
    fk_col = "staging_lead_id" if lead_source == "staging_leads" else "lead_id"

    try:
        res = adapter.query(
            table=conv_table,
            filters={fk_col: lead_id},
            limit=20,
            order_by="updated_at",
            descending=True,
        )
        conversations = res.get("data", [])

        summaries = []
        for conv in conversations:
            if conv.get("id") == exclude_conversation_id:
                continue
            summaries.append({
                "id": conv.get("id"),
                "subject": conv.get("subject"),
                "status": conv.get("status"),
                "last_message_at": conv.get("last_message_at") or conv.get("updated_at"),
                "message_count": conv.get("message_count", 0),
            })

        return summaries
    except Exception as e:
        trace["errors"].append(f"other threads fetch: {e}")
        return []
```

---

### Phase 4: New RAG Tools Using Strategies

Now update the RAG agent to use these strategies via cleaner tools.

```python
    def _create_build_reply_context_tool(self):
        """
        PRIMARY tool for reply generation.
        Combines lead lookup + conversation selection + message history.
        """
        supabase = self.supabase

        @tool
        def build_reply_context(
            email: Optional[str] = None,
            lead_id: Optional[str] = None,
            thread_id: Optional[str] = None,
            subject: Optional[str] = None,
            max_messages: int = 20,
        ) -> Dict[str, Any]:
            """
            Build complete context for generating a reply to a lead.

            THIS IS THE RECOMMENDED TOOL FOR REPLY GENERATION.

            It automatically:
            1. Finds the lead (checks both leads and staging_leads)
            2. Selects the right conversation (by thread_id > subject > recency)
            3. Fetches message history (chronological order)
            4. Includes other thread summaries

            Args:
                email: Lead's email address (primary lookup key)
                lead_id: Lead's UUID (alternative lookup)
                thread_id: Specific thread to reply to (highest priority)
                subject: Subject line to match (if no thread_id)
                max_messages: Max messages to include (default 20)

            Returns:
                {
                    "status": "success" | "lead_not_found" | "no_conversations",
                    "lead": {...},
                    "lead_source": "leads" | "staging_leads",
                    "conversation": {...},
                    "selection_reason": str,
                    "messages": [...],  # Chronological, oldest first
                    "other_threads": [...],  # Summaries of other conversations
                    "query_trace": {...}
                }
            """
            if not supabase:
                return {"status": "error", "error": "supabase adapter unavailable"}

            try:
                from .strategies.reply_context import build_reply_context as _build

                return _build(
                    adapter=supabase,
                    email=email,
                    lead_id=lead_id,
                    thread_id=thread_id,
                    subject=subject,
                    max_messages=max_messages,
                    include_lead_profile=True,
                    include_all_threads=True,
                )
            except ImportError as e:
                logger.error(f"reply_context strategy import failed: {e}")
                return {"status": "error", "error": str(e)}
            except Exception as e:
                logger.error(f"build_reply_context failed: {e}")
                return {"status": "error", "error": str(e)}

        return build_reply_context

    def _create_select_conversation_tool(self):
        """
        Tool to select a specific conversation based on criteria.
        Use when you already know the lead but need to pick the right thread.
        """
        supabase = self.supabase

        @tool
        def select_conversation(
            lead_id: str,
            lead_source: str = "leads",
            criteria: str = "most_recent_inbound",
            thread_id: Optional[str] = None,
            subject: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            Select the most relevant conversation for a known lead.

            Use this when you already have the lead but need to pick which
            conversation to reference.

            Criteria Options:
            - "most_recent_inbound": Last conv where lead sent a message (DEFAULT)
            - "most_recent_any": Last conv by timestamp
            - "open_only": Most recent open conversation
            - "by_thread_id": Match exact thread_id (requires thread_id arg)
            - "by_subject": Match subject line (requires subject arg)

            Args:
                lead_id: The lead's UUID
                lead_source: "leads" or "staging_leads"
                criteria: Selection strategy
                thread_id: For "by_thread_id" criteria
                subject: For "by_subject" criteria

            Returns:
                {
                    "status": "found" | "not_found",
                    "conversation": {...},
                    "selection_reason": str,
                    "alternatives_count": int
                }
            """
            if not supabase:
                return {"status": "error", "error": "supabase adapter unavailable"}

            try:
                from .strategies.conversation_selection import get_relevant_conversation

                return get_relevant_conversation(
                    adapter=supabase,
                    lead_id=lead_id,
                    lead_source=lead_source,
                    selection_criteria=criteria,
                    context={"thread_id": thread_id, "subject": subject},
                )
            except ImportError as e:
                return {"status": "error", "error": str(e)}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        return select_conversation
```

---

### Phase 5: Updated Tool List

Update `_build_tools()` to include the new tools:

```python
    def _build_tools(self) -> List:
        """Build RAG retrieval tools - organized by use case"""
        tools = [
            # ========== VALIDATION (always available) ==========
            self._create_validate_entity_payload_tool(),
        ]

        if self.supabase:
            # ========== PRIMARY RETRIEVAL (recommended) ==========
            tools.extend([
                # For reply generation - use this first!
                self._create_build_reply_context_tool(),

                # For comprehensive lead lookup
                self._create_get_unified_lead_context_tool(),

                # For quick lead lookup (cascading)
                self._create_get_lead_context_tool(),
            ])

            # ========== CONVERSATION SELECTION ==========
            tools.extend([
                self._create_select_conversation_tool(),
                self._create_get_lead_conversations_tool(),
                self._create_get_conversation_by_id_tool(),
            ])

            # ========== MESSAGE RETRIEVAL ==========
            tools.extend([
                self._create_get_conversation_messages_tool(),
                self._create_get_latest_lead_replies_tool(),
            ])

            # ========== LEAD SEARCH (various criteria) ==========
            tools.extend([
                self._create_search_leads_tool(),
                self._create_search_leads_by_enriched_data_tool(),
                self._create_get_lead_by_id_tool(),
            ])

            # ========== STAGING LEADS ==========
            tools.extend([
                self._create_get_staging_leads_pending_enrichment_tool(),
                self._create_get_staging_leads_promotion_ready_tool(),
                self._create_get_staging_lead_by_id_tool(),
            ])

            # ========== ENRICHMENT CHECKS ==========
            tools.extend([
                self._create_check_lead_enrichment_history_tool(),
            ])
        else:
            logger.warning("Supabase adapter not available - retrieval tools disabled")

        # ========== VECTOR SEARCH (optional) ==========
        if self.embedding_pipeline:
            tools.extend([
                self._create_vector_search_companies_tool(),
                self._create_semantic_search_tool(),
            ])

        return tools
```

---

### Phase 6: Updated System Prompt

Update the system prompt to clearly guide tool selection:

```python
    def _get_system_prompt(self) -> str:
        return f"""You are the RAG Agent - Database retrieval specialist.

**Your Role:**
Retrieve data from Supabase for leads, conversations, and messages. READ ONLY.

**TOOL SELECTION GUIDE:**

📧 **For Reply Generation:**
   → Use `build_reply_context(email=..., thread_id=..., subject=...)`
   This is your PRIMARY tool. It automatically:
   - Finds the lead (both tables)
   - Selects the right conversation
   - Returns message history in order
   - Includes other thread summaries

🔍 **For Lead Lookup:**
   → Quick check: `get_lead_context(email=...)`
   → Full context: `get_unified_lead_context(email=...)`

💬 **For Conversation Selection:**
   → `select_conversation(lead_id=..., criteria="most_recent_inbound")`
   Criteria: "most_recent_inbound", "open_only", "by_thread_id", "by_subject"

📝 **For Message History:**
   → `get_conversation_messages(conversation_id=...)`
   → `get_latest_lead_replies(lead_id=...)` - for sentiment analysis

**DECISION RULES:**

1. If goal mentions "reply" or "respond" → Use `build_reply_context`
2. If goal mentions "find lead" or "lookup" → Use `get_lead_context` or `get_unified_lead_context`
3. If goal mentions "conversation history" → Use `build_reply_context` with thread_id/subject
4. If goal mentions "all messages" → Use `get_conversation_messages`
5. If goal mentions "recent replies" → Use `get_latest_lead_replies`

**OUTPUT FORMAT:**
Always return structured data with:
- status: "success" | "not_found" | "error"
- The requested data
- query_trace showing what was searched

Tenant: {self.tenant_id}
"""
```

---

### Summary: What This Plan Provides

| Retrieval Need                 | Strategy                                             | Tool                            |
| ------------------------------ | ---------------------------------------------------- | ------------------------------- |
| Generate a reply               | `reply_context.build_reply_context()`                | `build_reply_context`           |
| Find a lead (quick)            | `lead_lookup.cascading_lead_lookup()`                | `get_lead_context`              |
| Find a lead (comprehensive)    | `lead_lookup.unified_lead_lookup()`                  | `get_unified_lead_context`      |
| Pick which conversation to use | `conversation_selection.get_relevant_conversation()` | `select_conversation`           |
| Get message history            | `message_history.get_conversation_messages()`        | `get_conversation_messages`     |
| Check if lead was enriched     | `enrichment.check_enrichment_status()`               | `check_lead_enrichment_history` |

**Key Design Principles:**

1. **Strategies are deterministic** — business rules live in Python, not LLM
2. **Tools are thin wrappers** — they call strategies and format output
3. **Deep Agent decides WHICH tool** — based on goal interpretation
4. **Query traces are always included** — for debugging and auditing

Want me to implement any of these phases now?
