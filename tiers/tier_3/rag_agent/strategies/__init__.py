"""Deterministic retrieval strategies for RAG agent.

These helpers encapsulate business rules for database access so tools stay thin
and repeatable. Each strategy returns structured data plus trace info.
"""
from .conversation_selection import get_relevant_conversation, get_all_conversations_ranked
from .reply_context import build_reply_context

__all__ = [
    "get_relevant_conversation",
    "get_all_conversations_ranked",
    "build_reply_context",
]
