# Secrets (Local / Deployment)

This folder is for local/deployment secrets that should **not** be committed.

## Gmail OAuth (Tier-0 Inbox Poller)

Place your Google OAuth client secrets JSON here:

- `secrets/gmail_credentials.json`

The Docker Compose service `inbox_poller` mounts it into the container at:

- `/data/gmail/credentials.json`

The OAuth token generated after first consent is stored in the named Docker volume `gmail-oauth` as:

- `/data/gmail/gmail_token.json`

## Notes

- Do not commit real secrets.
- Use `.env` to configure paths/URLs.
