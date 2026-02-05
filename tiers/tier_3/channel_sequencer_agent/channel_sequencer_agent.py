"""Core ChannelSequencerAgent logic placeholder.

Decides channel order and dispatch metadata for outbound messages.
"""
from __future__ import annotations

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import redis

from services.email.gmail_sender import GmailConfigError, send_email_via_gmail

from tiers.tier_3.channel_sequencer_agent.validators import (
    SequenceRequest,
    SequenceResult,
    SequenceStep,
)


class ChannelSequencerAgent:
    """Builds and emits channel sequence decisions."""

    def __init__(self) -> None:
        self._redis: Optional[redis.Redis] = None
        self.use_langgraph = os.getenv("LANGGRAPH_WORKFLOWS_ENABLED", "1").lower() in ("1", "true", "yes")
        self._graph_runner = None

    def _get_graph_runner(self):
        if self._graph_runner is not None:
            return self._graph_runner
        from core.langgraph import LangGraphRunner

        async def _execute_graph(state):
            payload = state.get("payload") or {}
            return self.build_sequence(payload)

        async def _guardrails(state):
            output = state.get("output") or {}
            if not output:
                return {"status": "error", "error": "empty_sequence"}
            return output

        self._graph_runner = LangGraphRunner(
            name="channel_sequencer",
            execute_fn=_execute_graph,
            required_input_keys=["payload"],
            guardrails_fn=_guardrails,
        )
        return self._graph_runner

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.use_langgraph:
            runner = self._get_graph_runner()
            try:
                asyncio.get_running_loop()
                return self.build_sequence(payload)
            except RuntimeError:
                graph_result = asyncio.run(
                    runner.run(
                        state_input={
                            "payload": payload,
                            "task_id": payload.get("task_id"),
                            "correlation_id": payload.get("correlation_id"),
                        },
                        execution_id=str(payload.get("task_id") or payload.get("correlation_id") or ""),
                    )
                )
            if graph_result.get("status") == "success":
                return graph_result.get("output", {})
            return {
                "status": "error",
                "error": graph_result.get("error", "langgraph_failed"),
                "trace": graph_result.get("trace", []),
            }
        return self.build_sequence(payload)

    def _get_redis(self) -> Optional[redis.Redis]:
        if self._redis is not None:
            return self._redis
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return None
        try:
            self._redis = redis.from_url(redis_url, decode_responses=True)
        except Exception:
            self._redis = None
        return self._redis

    def _hard_stop_reason(self, step: SequenceStep, request: SequenceRequest) -> Optional[str]:
        metadata = step.metadata or {}
        context = request.context or {}

        flag_keys = {
            "do_not_contact",
            "unsubscribe",
            "stop",
            "legal_threat",
            "abusive",
            "sensitive",
            "angry",
        }
        for key in flag_keys:
            if metadata.get(key) or context.get(key):
                return f"hard_stop:{key}"

        reasons = metadata.get("hard_stop_reasons") or context.get("hard_stop_reasons")
        if isinstance(reasons, list) and reasons:
            return f"hard_stop:{reasons[0]}"

        snippet = metadata.get("last_inbound_snippet") or context.get("last_inbound_snippet")
        keywords_env = os.getenv(
            "OUTBOUND_HARD_STOP_KEYWORDS",
            "unsubscribe,stop,do not contact,legal threat,abuse,abusive,harass,harassment,do not email",
        )
        if isinstance(snippet, str) and snippet:
            lowered = snippet.lower()
            for kw in [k.strip().lower() for k in keywords_env.split(",") if k.strip()]:
                if kw in lowered:
                    return f"hard_stop:keyword:{kw}"

        return None

    def _throttle_check(self, tenant_id: str, *, is_new_thread: bool) -> Optional[str]:
        redis_client = self._get_redis()
        if not redis_client:
            return None

        try:
            max_per_hour = int(os.getenv("OUTBOUND_MAX_PER_HOUR", "0") or 0)
        except ValueError:
            max_per_hour = 0
        try:
            max_new_threads = int(os.getenv("OUTBOUND_MAX_NEW_THREADS_PER_DAY", "0") or 0)
        except ValueError:
            max_new_threads = 0

        now = datetime.utcnow()

        if max_per_hour > 0:
            hour_key = f"{tenant_id}:throttle:outbound:hour:{now:%Y%m%d%H}"
            count = redis_client.incr(hour_key)
            if count == 1:
                redis_client.expire(hour_key, 3700)
            if count > max_per_hour:
                return "throttle:hour_limit"

        if is_new_thread and max_new_threads > 0:
            day_key = f"{tenant_id}:throttle:outbound:new_threads:{now:%Y%m%d}"
            count = redis_client.incr(day_key)
            if count == 1:
                redis_client.expire(day_key, 90000)
            if count > max_new_threads:
                return "throttle:new_thread_limit"

        return None

    def build_sequence(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = SequenceRequest(**payload)

        deliveries: List[Dict[str, Any]] = []

        for step in request.steps:
            if step.delay_minutes and step.delay_minutes > 0:
                deliveries.append(
                    {
                        "channel": step.channel,
                        "status": "scheduled",
                        "scheduled_for": (
                            datetime.utcnow() + timedelta(minutes=step.delay_minutes)
                        ).isoformat(),
                        "reason": "delay_minutes",
                    }
                )
                continue

            if step.channel.lower() == "email":
                deliveries.append(self._send_email_step(step, request))
            else:
                deliveries.append(self._dispatch_webhook_step(step, request))

        dispatched = [d["channel"] for d in deliveries if d.get("status") == "sent"]
        any_error = any(d.get("status") == "error" for d in deliveries)
        status = "error" if any_error else ("sent" if dispatched else "scheduled")

        error_message = None
        if any_error:
            for d in deliveries:
                if d.get("status") == "error":
                    error_message = d.get("error") or "channel_sequencer_error"
                    break

        result = SequenceResult(
            status=status,
            dispatched_channels=dispatched,
            deliveries=deliveries,
            error=error_message,
        )
        return result.model_dump()

    def _send_email_step(self, step: SequenceStep, request: SequenceRequest) -> Dict[str, Any]:
        """Send a single email step via Gmail SMTP."""
        if not step.to_email or not step.subject or not step.body:
            raise ValueError("Email step requires to_email, subject, and body")

        hard_stop = self._hard_stop_reason(step, request)
        if hard_stop:
            return {
                "channel": "email",
                "status": "blocked",
                "to": step.to_email,
                "from": step.from_email or os.getenv("GMAIL_SENDER_EMAIL"),
                "reason": hard_stop,
            }

        metadata = step.metadata or {}
        is_new_thread = not (metadata.get("thread_id") or metadata.get("conversation_id"))
        throttle_reason = self._throttle_check(request.tenant_id, is_new_thread=is_new_thread)
        if throttle_reason:
            return {
                "channel": "email",
                "status": "throttled",
                "to": step.to_email,
                "from": step.from_email or os.getenv("GMAIL_SENDER_EMAIL"),
                "reason": throttle_reason,
            }

        if os.getenv("OUTBOUND_APPROVAL_MODE", "0").lower() in ("1", "true", "yes"):
            return {
                "channel": "email",
                "status": "draft",
                "to": step.to_email,
                "from": step.from_email or os.getenv("GMAIL_SENDER_EMAIL"),
                "reason": "approval_required",
            }

        # Allow overrides via metadata
        reply_to = None
        if isinstance(step.metadata, dict):
            reply_to = step.metadata.get("reply_to")

        try:
            message_id = send_email_via_gmail(
                to_email=step.to_email,
                subject=step.subject,
                body=step.body,
                from_email=step.from_email,
                reply_to=reply_to,
                app_password=os.getenv("GMAIL_APP_PASSWORD"),
            )
            return {
                "channel": "email",
                "status": "sent",
                "to": step.to_email,
                "from": step.from_email or os.getenv("GMAIL_SENDER_EMAIL"),
                "message_id": message_id,
            }
        except GmailConfigError as exc:
            return {
                "channel": "email",
                "status": "error",
                "error": str(exc),
            }
        except Exception as exc:  # pragma: no cover - runtime send path
            return {
                "channel": "email",
                "status": "error",
                "error": str(exc),
            }

    def _dispatch_webhook_step(self, step: SequenceStep, request: SequenceRequest) -> Dict[str, Any]:
        channel = step.channel.lower()
        webhook = self._channel_webhook(channel)
        if not webhook:
            return {
                "channel": step.channel,
                "status": "skipped",
                "reason": "webhook_missing",
            }

        payload = {
            "tenant_id": request.tenant_id,
            "lead_id": request.lead_id,
            "channel": channel,
            "template_id": step.template_id,
            "metadata": step.metadata or {},
            "context": request.context or {},
        }

        try:
            response = self._post_webhook(webhook, payload)
            if response.get("status") in ("success", "ok"):
                return {
                    "channel": step.channel,
                    "status": "sent",
                    "provider_response": response,
                }
            return {
                "channel": step.channel,
                "status": "error",
                "error": response.get("error") or "channel_webhook_failed",
                "provider_response": response,
            }
        except Exception as exc:
            return {
                "channel": step.channel,
                "status": "error",
                "error": str(exc),
            }

    def _channel_webhook(self, channel: str) -> str:
        env_key = f"CHANNEL_DISPATCH_{channel.upper()}_WEBHOOK_URL"
        return os.getenv(env_key) or os.getenv("CHANNEL_DISPATCH_WEBHOOK_URL", "")

    def _post_webhook(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        import requests  # type: ignore

        timeout = float(os.getenv("CHANNEL_DISPATCH_TIMEOUT_S", "15"))
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code >= 200 and response.status_code < 300:
            try:
                return response.json() if response.content else {"status": "success"}
            except Exception:
                return {"status": "success"}
        return {
            "status": "error",
            "error": f"webhook_http_{response.status_code}",
            "body": response.text[:500],
        }
            return {
                "channel": "email",
                "status": "error",
                "error": str(exc),
            }
