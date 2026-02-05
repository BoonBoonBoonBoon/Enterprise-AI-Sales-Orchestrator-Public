"""Dead Letter Queue (DLQ) support for failed messages.

Provides utilities to route messages that have exhausted retries
to a dead letter stream for manual review and reprocessing.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default DLQ stream suffix
DLQ_SUFFIX = os.getenv("DLQ_STREAM_SUFFIX", ":dlq")

# Maximum number of retries before sending to DLQ
DLQ_MAX_RETRIES = int(os.getenv("DLQ_MAX_RETRIES", "3"))

# Whether DLQ is enabled
DLQ_ENABLED = os.getenv("DLQ_ENABLED", "1").lower() in ("1", "true", "yes")


@dataclass
class DeadLetterMessage:
    """
    Represents a failed message routed to the DLQ.
    
    Contains original message data plus failure metadata.
    """
    original_message: Dict[str, Any]
    original_stream: str
    original_message_id: str
    failure_reason: str
    failure_count: int
    failed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_error: Optional[str] = None
    error_type: Optional[str] = None
    consumer_name: Optional[str] = None
    tenant_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for Redis storage."""
        return {
            "original_message": json.dumps(self.original_message),
            "original_stream": self.original_stream,
            "original_message_id": self.original_message_id,
            "failure_reason": self.failure_reason,
            "failure_count": str(self.failure_count),
            "failed_at": self.failed_at,
            "last_error": self.last_error or "",
            "error_type": self.error_type or "",
            "consumer_name": self.consumer_name or "",
            "tenant_id": self.tenant_id or "",
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "DeadLetterMessage":
        """Parse from Redis hash fields."""
        original_msg = data.get("original_message", "{}")
        try:
            parsed = json.loads(original_msg)
        except json.JSONDecodeError:
            parsed = {"raw": original_msg}
        
        return cls(
            original_message=parsed,
            original_stream=data.get("original_stream", ""),
            original_message_id=data.get("original_message_id", ""),
            failure_reason=data.get("failure_reason", "unknown"),
            failure_count=int(data.get("failure_count", "0")),
            failed_at=data.get("failed_at", ""),
            last_error=data.get("last_error") or None,
            error_type=data.get("error_type") or None,
            consumer_name=data.get("consumer_name") or None,
            tenant_id=data.get("tenant_id") or None,
        )


class DeadLetterQueue:
    """
    Manages dead letter queue operations for a stream.
    
    Usage:
        dlq = DeadLetterQueue(redis_client, "agentic-dev:agents:rag:tasks")
        
        try:
            process_message(msg)
        except Exception as e:
            if dlq.should_dlq(failure_count=3):
                dlq.send_to_dlq(msg, msg_id, error=e)
    """
    
    def __init__(
        self,
        redis_client,
        source_stream: str,
        dlq_suffix: str = DLQ_SUFFIX,
        max_retries: int = DLQ_MAX_RETRIES,
        enabled: bool = DLQ_ENABLED,
    ):
        """
        Initialize DLQ for a source stream.
        
        Args:
            redis_client: Redis client with xadd capability
            source_stream: The original stream name (e.g., "agentic-dev:agents:rag:tasks")
            dlq_suffix: Suffix to append for DLQ stream (default: ":dlq")
            max_retries: Number of retries before DLQ (default: 3)
            enabled: Whether DLQ is enabled (default: True)
        """
        self.redis_client = redis_client
        self.source_stream = source_stream
        self.dlq_stream = source_stream + dlq_suffix
        self.max_retries = max_retries
        self.enabled = enabled
        
        logger.info(
            "DLQ initialized: source=%s, dlq=%s, max_retries=%d, enabled=%s",
            source_stream,
            self.dlq_stream,
            max_retries,
            enabled,
        )
    
    def should_dlq(self, failure_count: int) -> bool:
        """
        Check if a message should be sent to DLQ.
        
        Args:
            failure_count: Number of times this message has failed
            
        Returns:
            True if message should go to DLQ
        """
        if not self.enabled:
            return False
        return failure_count >= self.max_retries
    
    def send_to_dlq(
        self,
        message: Dict[str, Any],
        message_id: str,
        *,
        error: Optional[Exception] = None,
        failure_count: int = 0,
        failure_reason: str = "max_retries_exceeded",
        consumer_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send a failed message to the DLQ stream.
        
        Args:
            message: Original message data
            message_id: Original Redis message ID
            error: Exception that caused the failure
            failure_count: Number of failed attempts
            failure_reason: Human-readable reason
            consumer_name: Name of the consumer that failed
            tenant_id: Tenant ID for multi-tenant systems
            
        Returns:
            DLQ message ID if successful, None if DLQ disabled or failed
        """
        if not self.enabled:
            logger.debug("DLQ disabled, not sending message %s", message_id)
            return None
        
        dlq_message = DeadLetterMessage(
            original_message=message,
            original_stream=self.source_stream,
            original_message_id=message_id,
            failure_reason=failure_reason,
            failure_count=failure_count,
            last_error=str(error) if error else None,
            error_type=type(error).__name__ if error else None,
            consumer_name=consumer_name,
            tenant_id=tenant_id,
        )
        
        try:
            # Use raw redis client if available
            client = getattr(self.redis_client, "client", self.redis_client)
            dlq_msg_id = client.xadd(
                self.dlq_stream,
                dlq_message.to_dict(),
            )
            
            logger.warning(
                "Message sent to DLQ: original_id=%s, dlq_id=%s, reason=%s, error_type=%s",
                message_id,
                dlq_msg_id,
                failure_reason,
                dlq_message.error_type,
            )
            return dlq_msg_id
            
        except Exception as e:
            logger.error(
                "Failed to send message to DLQ: message_id=%s, error=%s",
                message_id,
                e,
            )
            return None
    
    def get_dlq_length(self) -> int:
        """Get number of messages in the DLQ."""
        try:
            client = getattr(self.redis_client, "client", self.redis_client)
            return client.xlen(self.dlq_stream)
        except Exception:
            return 0
    
    def peek_dlq(self, count: int = 10) -> list:
        """
        Peek at messages in the DLQ without consuming them.
        
        Args:
            count: Maximum number of messages to return
            
        Returns:
            List of (message_id, DeadLetterMessage) tuples
        """
        try:
            client = getattr(self.redis_client, "client", self.redis_client)
            messages = client.xrange(self.dlq_stream, count=count)
            return [
                (msg_id, DeadLetterMessage.from_dict(fields))
                for msg_id, fields in messages
            ]
        except Exception as e:
            logger.error("Failed to peek DLQ: %s", e)
            return []
    
    def requeue_message(self, dlq_message_id: str) -> Optional[str]:
        """
        Requeue a DLQ message back to the original stream.
        
        Args:
            dlq_message_id: Message ID in the DLQ stream
            
        Returns:
            New message ID in original stream, or None if failed
        """
        try:
            client = getattr(self.redis_client, "client", self.redis_client)
            
            # Read the DLQ message
            messages = client.xrange(
                self.dlq_stream,
                min=dlq_message_id,
                max=dlq_message_id,
                count=1,
            )
            
            if not messages:
                logger.warning("DLQ message not found: %s", dlq_message_id)
                return None
            
            _, fields = messages[0]
            dlq_msg = DeadLetterMessage.from_dict(fields)
            
            # Re-add to original stream
            new_id = client.xadd(
                self.source_stream,
                dlq_msg.original_message,
            )
            
            # Remove from DLQ
            client.xdel(self.dlq_stream, dlq_message_id)
            
            logger.info(
                "Requeued message: dlq_id=%s -> new_id=%s",
                dlq_message_id,
                new_id,
            )
            return new_id
            
        except Exception as e:
            logger.error("Failed to requeue message: %s", e)
            return None


def get_dlq_stream_name(source_stream: str, suffix: str = DLQ_SUFFIX) -> str:
    """Get the DLQ stream name for a source stream."""
    return source_stream + suffix


__all__ = [
    "DeadLetterQueue",
    "DeadLetterMessage",
    "get_dlq_stream_name",
    "DLQ_SUFFIX",
    "DLQ_MAX_RETRIES",
    "DLQ_ENABLED",
]
