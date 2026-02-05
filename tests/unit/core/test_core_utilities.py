"""Unit tests for core utilities: intent, tokens, shutdown, dlq."""
import pytest
from unittest.mock import Mock, patch


class TestIntentEnum:
    """Tests for the Intent enum."""
    
    def test_intent_from_string_valid(self):
        from core.intent import Intent
        
        assert Intent.from_string("inbound") == Intent.INBOUND
        assert Intent.from_string("INBOUND") == Intent.INBOUND
        assert Intent.from_string("reply_email") == Intent.REPLY_EMAIL
        assert Intent.from_string("outreach") == Intent.OUTREACH
    
    def test_intent_from_string_invalid(self):
        from core.intent import Intent
        
        assert Intent.from_string("unknown_intent") == Intent.UNKNOWN
        assert Intent.from_string("") == Intent.UNKNOWN
        assert Intent.from_string(None) == Intent.UNKNOWN
    
    def test_intent_is_valid(self):
        from core.intent import Intent
        
        assert Intent.is_valid("inbound") is True
        assert Intent.is_valid("unknown") is True
        assert Intent.is_valid("not_a_real_intent") is False
    
    def test_intent_string_comparison(self):
        from core.intent import Intent
        
        # Intent should be comparable to strings
        assert Intent.INBOUND == "inbound"
        assert Intent.REPLY_EMAIL == "reply_email"
    
    def test_routing_intents_set(self):
        from core.intent import Intent, ROUTING_INTENTS
        
        assert Intent.INBOUND in ROUTING_INTENTS
        assert Intent.OUTREACH in ROUTING_INTENTS
        assert Intent.REPLY_EMAIL not in ROUTING_INTENTS


class TestTokenUtilities:
    """Tests for token counting utilities."""
    
    def test_estimate_tokens_basic(self):
        from core.tokens import estimate_tokens
        
        # ~4 chars per token
        assert estimate_tokens("hello") >= 1
        assert estimate_tokens("hello world this is a test") >= 5
        assert estimate_tokens("") == 0
    
    def test_truncate_messages_by_tokens(self):
        from core.tokens import truncate_messages_by_tokens
        
        messages = [
            {"body": "short message 1"},
            {"body": "short message 2"},
            {"body": "A" * 1000},  # Long message
        ]
        
        # With low token limit, should drop messages
        truncated = truncate_messages_by_tokens(messages, max_tokens=100)
        assert len(truncated) < len(messages)
    
    def test_truncate_preserves_recent(self):
        from core.tokens import truncate_messages_by_tokens
        
        messages = [
            {"body": "oldest message " + "x" * 100},
            {"body": "middle message " + "x" * 100},
            {"body": "newest message"},
        ]
        
        # With limited tokens, should keep newest
        truncated = truncate_messages_by_tokens(messages, max_tokens=50)
        assert truncated[-1]["body"] == "newest message" if truncated else True
    
    def test_token_budget_tracking(self):
        from core.tokens import TokenBudget
        
        budget = TokenBudget(max_tokens=1000)
        budget.add("prompt", "Hello world")
        budget.add("context", "Some context here")
        
        assert budget.total > 0
        assert budget.remaining < 1000
        assert not budget.is_exceeded


class TestShutdownHandler:
    """Tests for graceful shutdown handling."""
    
    def test_shutdown_handler_creation(self):
        from core.shutdown import ShutdownHandler
        
        handler = ShutdownHandler(name="TestConsumer")
        assert handler.should_stop is False
        assert handler.is_processing is False
    
    def test_shutdown_handler_stop_request(self):
        from core.shutdown import ShutdownHandler
        
        handler = ShutdownHandler(name="TestConsumer")
        handler.request_stop()
        assert handler.should_stop is True
    
    def test_processing_context(self):
        from core.shutdown import ShutdownHandler
        
        handler = ShutdownHandler(name="TestConsumer")
        
        with handler.processing_context("task-123"):
            assert handler.is_processing is True
        
        assert handler.is_processing is False


class TestDeadLetterQueue:
    """Tests for DLQ utilities."""
    
    def test_dlq_message_creation(self):
        from core.dlq import DeadLetterMessage
        
        msg = DeadLetterMessage(
            original_message={"key": "value"},
            original_stream="test:stream",
            original_message_id="123-0",
            failure_reason="max_retries_exceeded",
            failure_count=3,
        )
        
        assert msg.failure_count == 3
        assert msg.original_stream == "test:stream"
    
    def test_dlq_message_serialization(self):
        from core.dlq import DeadLetterMessage
        
        msg = DeadLetterMessage(
            original_message={"key": "value"},
            original_stream="test:stream",
            original_message_id="123-0",
            failure_reason="error",
            failure_count=1,
        )
        
        # Round-trip serialization
        as_dict = msg.to_dict()
        restored = DeadLetterMessage.from_dict(as_dict)
        
        assert restored.failure_reason == msg.failure_reason
        assert restored.original_stream == msg.original_stream
    
    def test_dlq_should_dlq_logic(self):
        from core.dlq import DeadLetterQueue
        
        mock_redis = Mock()
        dlq = DeadLetterQueue(
            redis_client=mock_redis,
            source_stream="test:stream",
            max_retries=3,
            enabled=True,
        )
        
        assert dlq.should_dlq(failure_count=1) is False
        assert dlq.should_dlq(failure_count=3) is True
        assert dlq.should_dlq(failure_count=5) is True
    
    def test_dlq_disabled(self):
        from core.dlq import DeadLetterQueue
        
        mock_redis = Mock()
        dlq = DeadLetterQueue(
            redis_client=mock_redis,
            source_stream="test:stream",
            enabled=False,
        )
        
        # Should never send to DLQ when disabled
        assert dlq.should_dlq(failure_count=100) is False
        result = dlq.send_to_dlq({}, "123-0")
        assert result is None
