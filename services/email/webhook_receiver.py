"""FastAPI webhook receiver for inbound email events.

Accepts normalized `inbound_email_event` payloads and publishes to
`{tenant}:manager:tasks`, sharing the same dedup key pattern as the poller.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from services.redis import RedisStreamsClient
from services.email.inbox_poller import make_dedup_key, should_process, publish_event
from services.email.providers import InboundEmailEvent
from services.email.pre_filter import PreFilterResult, pre_filter_email

app = FastAPI(title="Inbox Webhook Receiver", version="0.1.0")

WEBHOOK_SECRET = os.getenv("INBOX_WEBHOOK_SECRET")


def get_redis_client() -> RedisStreamsClient:
    return RedisStreamsClient()


class InboundEmailEventModel(BaseModel):
    provider: str = Field(..., description="Email provider identifier")
    message_id: str
    thread_id: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    # Accept either {from,to} or {from_email,to_email}
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None
    received_at: Optional[str] = None
    from_name: Optional[str] = None

    # Optional headers that improve deterministic triage/classification
    list_unsubscribe: Optional[str] = None
    precedence: Optional[str] = None
    auto_response_suppress: Optional[str] = None
    x_mailer: Optional[str] = None
    reply_to: Optional[str] = None

    def to_event(self) -> InboundEmailEvent:
        data = self.model_dump(by_alias=True)
        sender = data.get("from") or data.get("from_email")
        recipient = data.get("to") or data.get("to_email")
        if not sender or not recipient:
            raise ValueError("Webhook payload must include from/to (or from_email/to_email)")
        return InboundEmailEvent(
            provider=data["provider"],
            message_id=data["message_id"],
            thread_id=data.get("thread_id"),
            subject=data.get("subject"),
            body=data.get("body"),
            from_email=sender,
            to_email=recipient,
            received_at=data.get("received_at"),
            from_name=data.get("from_name"),
            list_unsubscribe=data.get("list_unsubscribe"),
            precedence=data.get("precedence"),
            auto_response_suppress=data.get("auto_response_suppress"),
            x_mailer=data.get("x_mailer"),
            reply_to=data.get("reply_to"),
        )

    class Config:
        populate_by_name = True


@app.post("/webhook/email/{tenant_id}")
async def ingest_email(
    tenant_id: str,
    payload: InboundEmailEventModel,
    x_webhook_secret: Optional[str] = Header(default=None, convert_underscores=False),
    redis_client: RedisStreamsClient = Depends(get_redis_client),
):
    if WEBHOOK_SECRET and x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    event = payload.to_event()
    dedup_key = make_dedup_key(tenant_id, event.provider, event.message_id)
    if not should_process(redis_client, dedup_key):
        return {"status": "duplicate", "message_id": event.message_id}

    pre_filter_result = pre_filter_email(
        from_email=event.from_email,
        subject=event.subject,
        body=event.body,
        list_unsubscribe=event.list_unsubscribe,
        precedence=event.precedence,
        auto_response_suppress=event.auto_response_suppress,
        x_mailer=event.x_mailer,
        from_name=event.from_name,
    )
    event.pre_filter_category = pre_filter_result.category

    publish_event(redis_client, tenant_id, event, pre_filter_result)
    return {"status": "accepted", "message_id": event.message_id}


# Optional local runner
if __name__ == "__main__":
    try:
        import uvicorn

        uvicorn.run(app, host=os.getenv("INBOX_WEBHOOK_HOST", "0.0.0.0"), port=int(os.getenv("INBOX_WEBHOOK_PORT", "8080")))
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit("uvicorn is not installed; install uvicorn to run the webhook server") from exc
