# Email Service

The Email Service handles sending emails via Gmail API for outreach and reply workflows.

## Overview

| Component    | Description                 |
| ------------ | --------------------------- |
| **Location** | `services/email/`           |
| **Purpose**  | Send emails, manage threads |
| **Used By**  | OutreachOrchestrator        |

## Gmail Integration

### Setup

1. Create Google Cloud project
2. Enable Gmail API
3. Configure OAuth consent screen
4. Create OAuth 2.0 credentials
5. Generate refresh token

### Environment Variables

| Variable              | Required | Description         |
| --------------------- | -------- | ------------------- |
| `GMAIL_CLIENT_ID`     | ✅       | OAuth client ID     |
| `GMAIL_CLIENT_SECRET` | ✅       | OAuth client secret |
| `GMAIL_REFRESH_TOKEN` | ✅       | Refresh token       |
| `GMAIL_SENDER_EMAIL`  | ✅       | Sender address      |

## Usage

### Basic Send

```python
from services.email.gmail_service import GmailService

service = GmailService()

result = await service.send(
    to="recipient@example.com",
    subject="Hello",
    body="This is the email body."
)

print(result["message_id"])
```

### Reply to Thread

```python
result = await service.send(
    to="recipient@example.com",
    subject="Re: Original subject",
    body="Reply content...",
    thread_id="thread-id-from-original",
    in_reply_to="message-id-of-original"
)
```

### With Attachments

```python
result = await service.send(
    to="recipient@example.com",
    subject="Document attached",
    body="Please find attached...",
    attachments=[
        {"filename": "doc.pdf", "content": pdf_bytes, "mime_type": "application/pdf"}
    ]
)
```

## GmailService API

### Constructor

```python
class GmailService:
    def __init__(
        self,
        client_id: str = None,      # From env if None
        client_secret: str = None,  # From env if None
        refresh_token: str = None,  # From env if None
        sender_email: str = None    # From env if None
    ):
```

### Methods

#### send()

```python
async def send(
    self,
    to: str,                        # Recipient email
    subject: str,                   # Email subject
    body: str,                      # Plain text or HTML
    thread_id: str = None,          # For replies
    in_reply_to: str = None,        # Original message ID
    cc: list[str] = None,           # CC recipients
    bcc: list[str] = None,          # BCC recipients
    attachments: list[dict] = None, # File attachments
    html: bool = False              # Body is HTML
) -> dict:
    """
    Returns:
        {
            "message_id": "...",
            "thread_id": "...",
            "sent_at": "2026-01-13T10:00:00Z"
        }
    """
```

#### get_message()

```python
async def get_message(
    self,
    message_id: str
) -> dict:
    """Retrieve message by ID."""
```

#### list_threads()

```python
async def list_threads(
    self,
    query: str = None,
    max_results: int = 10
) -> list[dict]:
    """List email threads."""
```

## Rate Limiting

Gmail API has quotas:

| Quota                  | Limit            |
| ---------------------- | ---------------- |
| Emails per day         | 2,000 (standard) |
| Emails per second      | 1-2              |
| Recipients per message | 500              |

### Handling Rate Limits

```python
from services.email.gmail_service import GmailService, RateLimitError

try:
    await service.send(...)
except RateLimitError:
    # Wait and retry, or queue for later
    await asyncio.sleep(60)
    await service.send(...)
```

## Error Handling

```python
from services.email.exceptions import (
    GmailAuthError,
    RateLimitError,
    InvalidRecipientError,
    SendError
)

try:
    await service.send(to=email, subject=subj, body=content)
except GmailAuthError:
    # Refresh token expired
    logger.error("Need to re-authenticate")
except InvalidRecipientError:
    # Bad email address
    logger.warning(f"Invalid email: {email}")
except SendError as e:
    # General send failure
    logger.error(f"Send failed: {e}")
```

## File Structure

```
services/email/
├── __init__.py
├── gmail_service.py   # Main service
├── exceptions.py      # Custom exceptions
└── README.md
```

## OAuth Token Refresh

The service auto-refreshes tokens:

```python
class GmailService:
    async def _get_access_token(self):
        """Get valid access token, refreshing if needed."""
        if self._access_token and not self._is_expired():
            return self._access_token

        # Refresh using refresh_token
        response = await self._refresh_token()
        self._access_token = response["access_token"]
        self._expires_at = time.time() + response["expires_in"]

        return self._access_token
```

## Testing

### Mock Service

```python
from unittest.mock import AsyncMock

mock_email = AsyncMock()
mock_email.send.return_value = {
    "message_id": "test-123",
    "thread_id": "thread-456"
}

# Inject mock in orchestrator
orchestrator.email_service = mock_email
```

## Related

- [Outreach Orchestrator](../tier-2/outreach.md)
- [Copywriter Agent](../tier-3/copywriter.md)
- [Environment Variables](../../reference/config/env-vars.md)
