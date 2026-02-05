# Email Service

Email sending and inbox monitoring service with Gmail API / IMAP integration.

## Components

| File                  | Purpose                                                      |
| --------------------- | ------------------------------------------------------------ |
| `gmail_sender.py`     | SMTP sender (plain text, HTML, attachments via App Password) |
| `gmail_reader.py`     | Gmail API reader (OAuth2) for fetching inbox messages        |
| `providers.py`        | Provider abstraction + IMAP fallback                         |
| `inbox_poller.py`     | Tier-0 ingress: polls inbox, publishes to Manager stream     |
| `webhook_receiver.py` | FastAPI backup endpoint for push-based email ingestion       |

---

## Sending Emails (SMTP)

```python
from services.email import send_email_via_gmail, EmailAttachment

# Plain text
send_email_via_gmail(to_email="lead@example.com", subject="Hello", body="Hi there")

# With HTML alternative
send_email_via_gmail(
    to_email="lead@example.com",
    subject="Hello",
    body="Hi there (plain)",
    html_body="<p>Hi there <b>(HTML)</b></p>",
)

# With attachments
send_email_via_gmail(
    to_email="lead@example.com",
    subject="Proposal",
    body="Attached is our proposal.",
    attachments=["proposal.pdf"],  # or EmailAttachment objects
)
```

### Env vars (SMTP)

```
GMAIL_SENDER_EMAIL=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

---

## Reading Inbox (Gmail API)

Uses OAuth2 (requires Google Cloud project with Gmail API enabled).

```python
from services.email.gmail_reader import GmailReader, GmailReaderConfig

cfg = GmailReaderConfig(credentials_json_path="credentials.json")
reader = GmailReader(cfg)

ids = reader.list_message_ids(query="is:unread", max_results=10)
for mid in ids:
    raw = reader.get_message_raw(message_id=mid)
    parsed = reader.parse_raw_message(raw)
    print(parsed["subject"], parsed["from_email"])
    reader.mark_as_read(message_id=mid)
```

### Env vars (Gmail API reader)

```
GMAIL_READ_CREDENTIALS_PATH=path/to/credentials.json
GMAIL_TOKEN_PATH=gmail_token.json   # auto-created after OAuth
```

---

## Inbox Poller (Tier 0 Ingress)

Polls inbox periodically and publishes inbound events to `{tenant}:manager:tasks`.

```powershell
& ".\.venv\Scripts\python.exe" -m services.email.inbox_poller `
    --tenant agentic-dev `
    --provider gmail `
    --poll-interval 60 `
    --credentials-path credentials.json
```

- Dedup via Redis key `{tenant}:inbox:seen:{provider}:{message_id}` (TTL 24h)
- Marks messages as read after successful publish (use `--no-mark-read` to disable)

---

## Webhook Receiver (FastAPI Backup)

Accepts push-based `inbound_email_event` payloads:

```powershell
& ".\.venv\Scripts\python.exe" -m services.email.webhook_receiver
# Runs on 0.0.0.0:8080 by default
```

POST `/webhook/email/{tenant_id}` with JSON body:

```json
{
  "provider": "sendgrid",
  "message_id": "<unique-id>",
  "thread_id": null,
  "subject": "Re: Inquiry",
  "body": "Hello...",
  "from_email": "lead@example.com",
  "to_email": "inbox@agency.com",
  "received_at": "2026-01-18T10:00:00Z"
}
```

### Env vars (webhook)

```
INBOX_WEBHOOK_HOST=0.0.0.0
INBOX_WEBHOOK_PORT=8080
INBOX_WEBHOOK_SECRET=optionalsecret   # checked via X-Webhook-Secret header
```

---

## Rate Limits

Gmail API has daily limits:

- Free accounts: 500 emails/day (sending); generous read quota
- Google Workspace: 2,000 emails/day

---

## See Also

- [Copywriter Agent](../../tiers/tier_3/copywriter_agent/README.md) — Generates email content
- [Outreach Orchestrator](../../tiers/tier_2/outreach_orchestrator/README.md) — Coordinates email campaigns
- [MVP.md](../../MVP.md) — Inbox Monitoring is MVP Priority #1
