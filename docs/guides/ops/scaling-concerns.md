# Scaling Concerns (Inbox + Streams)

This document captures practical scaling risks and design considerations for the inbox-ingestion path (Gmail API / IMAP / webhook backup) and its downstream processing via Redis Streams.

## Scope

- **Ingress:** Inbox poller and webhook receiver publishing tasks to `{tenant}:manager:tasks`.
- **Core pipeline:** Manager → Orchestrators → Agents via Redis Streams.
- **Out of scope:** UI, campaign scheduling, multi-inbox UX.

---

## 1) Inbox Ingestion at Scale

### Polling vs Push

- **Polling (current MVP):** Simple and reliable, but scaling increases API calls and latency.
  - Watch for: higher Gmail API quota usage, IMAP server throttling, and increased end-to-end response time.
- **Push (future):** Gmail `watch` → Pub/Sub (or similar) reduces polling load.
  - Watch for: delivery guarantees, Pub/Sub ack deadlines, and replay handling.
  - Rule of thumb: move to push when you have multiple inboxes or higher email volume per inbox.

### Rate Limits / Quotas

- **Gmail API quotas:** High-volume inboxes can hit per-user and per-project limits.
  - Implement: exponential backoff on 429/5xx, and a per-inbox token bucket to smooth bursts.
- **IMAP throttling:** Many providers will slow or ban aggressive polling.
  - Implement: jittered polling interval + a floor/ceiling (e.g., 10s–300s) and adaptive backoff.
- **LLM limits (downstream):** Even if inbox ingestion is fine, reply drafting can bottleneck.
  - Implement: queue depth monitoring and per-tenant concurrency caps.

### Idempotency & Deduplication

- **At-least-once delivery is normal.** Treat it as a feature, not a bug.
- Dedup should be **stable**, based on a provider-specific unique identifier:
  - Gmail: message id + thread id
  - IMAP: UID + mailbox (or Message-ID header if stable)
- Ensure each stage is idempotent:
  - Manager enqueue should tolerate duplicates.
  - Persistence writes should use unique constraints / upserts where appropriate.
  - Reply generation should tolerate repeated context fetches.

### Mark-as-Read Semantics

- Marking messages as read is a **side effect**; it should happen only after a durable enqueue.
- For higher reliability:
  - Mark as read only after publish success.
  - Consider “labeling” (Gmail) or “move to folder” patterns if you need auditability.

### Payload Size & Attachments

- Emails can be large (threads + attachments). Redis Streams are not ideal for huge blobs.
  - Prefer: store raw email/attachments in object storage or DB, and pass references (IDs/URLs) in the envelope.
  - Avoid: pushing base64 attachment blobs into Redis stream messages.

---

## 2) Multi-Inbox / Multi-Tenant Scaling

### Single Inbox (MVP)

- One inbox is operationally simple and avoids multi-credential complexity.
- Scaling risk: you may encode assumptions (single sender identity, single token file) that become painful later.

### Multi-Inbox (Roadmap)

- You will need a data model for:
  - inbox identity (email address)
  - auth material (OAuth refresh tokens or IMAP creds)
  - routing rules (which tenant / campaign / playbook)
- Concurrency model:
  - one poller per inbox, or a single poller multiplexing inboxes with rate limits per inbox.
- Key rule: avoid shared global token files; store tokens per inbox identity.

---

## 3) Google Cloud Console (Gmail API) Ownership Model

### Agency-Owned Project (recommended for MVP)

- Pros: fastest to ship; centralized ops; one set of quota monitoring.
- Cons: agency becomes a dependency; clients may dislike shared infrastructure.
- Plan for later: ability to migrate inbox auth to a client-owned project.

### Client-Owned Project (recommended long-term for enterprise clients)

- Pros: client controls access, compliance posture, and quotas.
- Cons: onboarding cost; each client must configure OAuth consent / verification settings.

### Key scaling concern: verification & consent friction

- If you add many inboxes across organizations, consent and app verification become the bottleneck.
- Design goal: keep the code compatible with both models (agency or client project) by treating credentials as per-inbox configuration.

---

## 4) Redis Streams Throughput & Backpressure

### Backpressure Signals

- Measure lag/pending counts per stream consumer group.
- Alert on sustained growth in:
  - `{tenant}:manager:tasks`
  - orchestrator task streams
  - agent task streams

### Failure Handling

- Ensure retries don’t create storms:
  - bounded retries + jitter
  - DLQ for poison-pill tasks
- Prefer: “retry with delay” at the harness layer vs tight loops.

### Stream Sizing

- Set appropriate maxlen trimming and monitor memory.
- If emails spike, ingestion should slow rather than crash:
  - reduce poll frequency under backlog
  - temporarily stop marking read until backlog clears

---

## 5) Security, Secrets, and Compliance

- **Never commit `.env` secrets** (SMTP app passwords, Supabase keys/JWTs, Redis passwords).
- Webhook security:
  - require a shared secret header/token
  - consider IP allowlisting if deployed behind a known gateway
- Data retention:
  - define how long raw email bodies are stored
  - minimize stored PII where possible
- Auditability:
  - store message ids/thread ids and a processing state timeline

---

## 6) Operational Readiness Checklist

- Metrics: ingestion rate, end-to-end latency, queue lag, error rates, dedup hit rate.
- Logs: include `tenant_id`, `provider`, `message_id`, `thread_id`, `task_id`.
- Runbooks: rate-limit incidents, Gmail auth failures, Redis outages, Supabase outages.
- Capacity: define max inboxes per poller instance and max tasks/min per tenant.
