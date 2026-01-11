# Email Service

Email sending service with Gmail API integration.

## Components

| File              | Purpose                             |
| ----------------- | ----------------------------------- |
| `gmail_sender.py` | Gmail API client for sending emails |

## Usage

```python
from services.email.gmail_sender import GmailSender

sender = GmailSender(credentials_path="credentials.json")
sender.send(
    to="lead@example.com",
    subject="Following up on our conversation",
    body="Hi John,\n\nThanks for your time yesterday..."
)
```

## Configuration

Requires Gmail API credentials:

1. Create a Google Cloud project
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Download `credentials.json`

```bash
GMAIL_CREDENTIALS_PATH=path/to/credentials.json
```

## Rate Limits

Gmail API has daily sending limits:

- Free accounts: 500 emails/day
- Google Workspace: 2,000 emails/day

## See Also

- [Copywriter Agent](../../tiers/tier_3/copywriter_agent/README.md) — Generates email content
- [Outreach Orchestrator](../../tiers/tier_2/outreach_orchestrator/README.md) — Coordinates email campaigns
