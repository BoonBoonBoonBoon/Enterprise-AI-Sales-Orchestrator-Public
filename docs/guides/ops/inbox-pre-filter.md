# Inbox Pre-Filter (Tier-0)

The **Tier-0 inbox pre-filter** runs inside the inbox ingress (poller/webhook) before publishing anything to Manager.
Its goal is to cheaply prevent obvious low-value emails (bounces, promotions, newsletters) from triggering downstream orchestration.

## Categories

The pre-filter emits a `{ category, confidence, reason }` signal. Current categories:

- `bounce` — delivery failures / postmaster mail
- `auto_reply` — out-of-office / auto replies
- `system` — transactional or operational notifications (security, access requests, etc.)
- `marketing` — promotions / ads / webinars / sales mail
- `newsletter` — digests and product updates
- `null` — no match; full inbound classification proceeds

Important: `List-Unsubscribe` is treated as a **weak** signal by itself; many legitimate systems include it.

## Configuration

These env vars are read by `services/email/inbox_poller.py`:

- https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/services/email/inbox_poller.py

- `INBOX_PRE_FILTER_ENABLED` (default `1`)
- `INBOX_PRE_FILTER_SKIP_CATEGORIES` (default `bounce,marketing,newsletter`)
- `INBOX_PRE_FILTER_SKIP_CONFIDENCE` (default `0.8`)

If an email matches one of the skip categories with confidence >= `INBOX_PRE_FILTER_SKIP_CONFIDENCE`, it is **not published to** `{tenant}:manager:tasks`.

### Example

To be more conservative (only skip bounces):

```bash
INBOX_PRE_FILTER_SKIP_CATEGORIES=bounce
INBOX_PRE_FILTER_SKIP_CONFIDENCE=0.9
```

To be more aggressive (skip most bulk mail):

```bash
INBOX_PRE_FILTER_SKIP_CATEGORIES=bounce,marketing,newsletter
INBOX_PRE_FILTER_SKIP_CONFIDENCE=0.7
```

## Debugging

- Poller logs include `Pre-filter SKIP: ...` lines when an email is dropped at Tier-0.
- If you want to review everything (no skipping), set `INBOX_PRE_FILTER_SKIP_CATEGORIES=` or `INBOX_PRE_FILTER_ENABLED=0`.
