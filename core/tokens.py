"""Token counting utilities for context window management.

Provides lightweight token estimation to prevent context overflow
when building prompts for LLM calls.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Default context limits (conservative estimates for GPT-4)
DEFAULT_MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
DEFAULT_TOKENS_PER_MESSAGE = int(os.getenv("TOKENS_PER_MESSAGE", "4"))  # Overhead per message
DEFAULT_CHARS_PER_TOKEN = float(os.getenv("CHARS_PER_TOKEN", "4.0"))  # Rough estimate


def estimate_tokens(text: str, chars_per_token: float = DEFAULT_CHARS_PER_TOKEN) -> int:
    """
    Estimate token count for a string.
    
    Uses character-based estimation (roughly 4 chars per token for English).
    For exact counts, use tiktoken, but this is faster for rough limits.
    
    Args:
        text: Text to estimate tokens for
        chars_per_token: Characters per token ratio (default: 4.0)
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return max(1, int(len(text) / chars_per_token))


def estimate_json_tokens(data: Any, chars_per_token: float = DEFAULT_CHARS_PER_TOKEN) -> int:
    """
    Estimate token count for JSON-serializable data.
    
    Args:
        data: Data to serialize and count
        chars_per_token: Characters per token ratio
        
    Returns:
        Estimated token count
    """
    try:
        text = json.dumps(data, default=str)
        return estimate_tokens(text, chars_per_token)
    except (TypeError, ValueError):
        return 100  # Fallback estimate


def estimate_message_tokens(message: Dict[str, Any]) -> int:
    """
    Estimate tokens for a message dict.
    
    Accounts for:
    - Body text
    - Subject (if present)
    - Metadata overhead
    
    Args:
        message: Message dict with body, subject, etc.
        
    Returns:
        Estimated token count
    """
    tokens = DEFAULT_TOKENS_PER_MESSAGE  # Base overhead
    
    body = message.get("body") or message.get("content") or ""
    if isinstance(body, str):
        tokens += estimate_tokens(body)
    
    subject = message.get("subject") or ""
    if isinstance(subject, str):
        tokens += estimate_tokens(subject)
    
    # Add small overhead for other fields
    tokens += 10
    
    return tokens


def truncate_messages_by_tokens(
    messages: List[Dict[str, Any]],
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    preserve_recent: bool = True,
) -> List[Dict[str, Any]]:
    """
    Truncate a list of messages to fit within token budget.
    
    By default, preserves most recent messages (most relevant for replies).
    
    Args:
        messages: List of message dicts
        max_tokens: Maximum total tokens allowed
        preserve_recent: If True, keep recent messages; if False, keep oldest
        
    Returns:
        Truncated list of messages
    """
    if not messages:
        return []
    
    # Estimate tokens for each message
    message_tokens = [(msg, estimate_message_tokens(msg)) for msg in messages]
    
    # If preserving recent, reverse to iterate from newest
    if preserve_recent:
        message_tokens = list(reversed(message_tokens))
    
    result = []
    total_tokens = 0
    
    for msg, tokens in message_tokens:
        if total_tokens + tokens > max_tokens:
            logger.debug(
                "Token limit reached: %d + %d > %d, truncating at %d messages",
                total_tokens,
                tokens,
                max_tokens,
                len(result),
            )
            break
        result.append(msg)
        total_tokens += tokens
    
    # Restore chronological order if we reversed
    if preserve_recent:
        result = list(reversed(result))
    
    logger.debug(
        "Truncated messages: %d -> %d messages, ~%d tokens",
        len(messages),
        len(result),
        total_tokens,
    )
    
    return result


def truncate_text_by_tokens(
    text: str,
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    suffix: str = "\n\n[...truncated...]",
) -> str:
    """
    Truncate text to fit within token budget.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        suffix: Suffix to append when truncated
        
    Returns:
        Truncated text with suffix if needed
    """
    if not text:
        return text
    
    current_tokens = estimate_tokens(text)
    if current_tokens <= max_tokens:
        return text
    
    # Estimate character limit
    max_chars = int(max_tokens * DEFAULT_CHARS_PER_TOKEN)
    suffix_chars = len(suffix)
    
    truncated = text[:max_chars - suffix_chars] + suffix
    
    logger.debug(
        "Truncated text: %d -> %d tokens (%d -> %d chars)",
        current_tokens,
        estimate_tokens(truncated),
        len(text),
        len(truncated),
    )
    
    return truncated


class TokenBudget:
    """
    Helper class to track token usage while building context.
    
    Usage:
        budget = TokenBudget(max_tokens=8000)
        
        budget.add("system_prompt", system_prompt)
        budget.add("lead_info", lead_data)
        
        # Check remaining before adding messages
        remaining = budget.remaining
        messages = truncate_messages_by_tokens(messages, max_tokens=remaining)
        budget.add("messages", messages)
        
        print(f"Total tokens: {budget.total}")
    """
    
    def __init__(self, max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS):
        self.max_tokens = max_tokens
        self._items: Dict[str, int] = {}
    
    @property
    def total(self) -> int:
        """Current total token usage."""
        return sum(self._items.values())
    
    @property
    def remaining(self) -> int:
        """Remaining token budget."""
        return max(0, self.max_tokens - self.total)
    
    @property
    def is_exceeded(self) -> bool:
        """Check if budget is exceeded."""
        return self.total > self.max_tokens
    
    def add(self, name: str, content: Union[str, Dict, List]) -> int:
        """
        Add content and track its token usage.
        
        Args:
            name: Name for this content (for debugging)
            content: String, dict, or list to add
            
        Returns:
            Token count for this content
        """
        if isinstance(content, str):
            tokens = estimate_tokens(content)
        elif isinstance(content, list):
            tokens = sum(
                estimate_message_tokens(m) if isinstance(m, dict) else estimate_tokens(str(m))
                for m in content
            )
        else:
            tokens = estimate_json_tokens(content)
        
        self._items[name] = tokens
        return tokens
    
    def breakdown(self) -> Dict[str, int]:
        """Get breakdown of token usage by item."""
        return dict(self._items)


__all__ = [
    "estimate_tokens",
    "estimate_json_tokens",
    "estimate_message_tokens",
    "truncate_messages_by_tokens",
    "truncate_text_by_tokens",
    "TokenBudget",
    "DEFAULT_MAX_CONTEXT_TOKENS",
]
