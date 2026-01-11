"""Core ChannelSequencerAgent logic placeholder.

Decides channel order and dispatch metadata for outbound messages.
"""
from __future__ import annotations

import os
from typing import Dict, Any, List

from services.email.gmail_sender import GmailConfigError, send_email_via_gmail

from tiers.tier_3.channel_sequencer_agent.validators import (
    SequenceRequest,
    SequenceResult,
    SequenceStep,
)


class ChannelSequencerAgent:
    """Builds and emits channel sequence decisions."""

    def build_sequence(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = SequenceRequest(**payload)

        deliveries: List[Dict[str, Any]] = []

        for step in request.steps:
            if step.channel.lower() == "email":
                deliveries.append(self._send_email_step(step))
            else:
                deliveries.append(
                    {
                        "channel": step.channel,
                        "status": "skipped",
                        "reason": "unsupported_channel",
                    }
                )

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

    def _send_email_step(self, step: SequenceStep) -> Dict[str, Any]:
        """Send a single email step via Gmail SMTP."""
        if not step.to_email or not step.subject or not step.body:
            raise ValueError("Email step requires to_email, subject, and body")

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
