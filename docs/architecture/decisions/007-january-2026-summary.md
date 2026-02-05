# ADR-007: January 2026 Platform + Website Integration Summary

**Status:** ✅ Accepted  
**Date:** 2026-01-31

## Context

January 2026 included a concentrated push to reduce operational risk and improve integration consistency across:

- **Core message contracts** (envelope format)
- **Failure handling** (DLQ routing + retry behavior)
- **Website / portal development** (Next.js portals, Supabase Auth, and Gateway proxy patterns)

We needed a single, durable place to record what became “the standard” so future work doesn’t re-introduce variability.

## Decision

We treat the following as the January 2026 accepted baseline.

### 1) Canonical typed envelope

- The **typed Pydantic envelope** is the canonical message format used across tiers.
- Legacy envelope shapes are accepted only via **normalization into the typed envelope**, so downstream code can assume a consistent schema.

### 2) Consistent DLQ wiring across consumers

- All consumers use a consistent max-retry policy driven by Redis delivery counts.
- When max retries is reached, consumers:
  1. publish a DLQ record (stream suffix `:dlq`)
  2. ACK the original message (to avoid infinite pending loops)
- Consumers re-read pending messages when idle so retries actually occur.

### 3) Website development baseline (portals + Supabase)

- The repo includes multiple web surfaces:
  - **Internal Portal** (`apps/portal`): Next.js app used for internal/admin workflows.
  - **Customer Portal** (`apps/portal-customer`): Next.js app using Supabase Auth with SSR cookie-based auth.
- The portals use Supabase public credentials (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`) and follow documented local dev patterns.
- The Internal Portal is commonly configured to proxy API calls under `/api/v1/*` to the Gateway and attach `Authorization: Bearer <token>`.

## Consequences

### Positive

- Less drift: the envelope shape is stable and documented.
- Failures become observable and recoverable via DLQ rather than silently stalling.
- Portal/Gateway/Supabase wiring is documented and repeatable for local and deployed environments.

### Negative

- More discipline required: changes to envelope/DLQ semantics must be treated as compatibility work.
- Portal auth + gateway proxying adds integration surface area that requires ongoing documentation.

### Neutral

- This ADR functions as a “baseline record” in addition to being a decision log.

## Alternatives Considered

### Option A: Keep multiple envelope shapes in circulation

- Pros: less refactor pressure in the short term.
- Cons: integration breaks and validation complexity compound over time.
- Why rejected: variability was already causing docs and code paths to diverge.

### Option B: Best-effort failure handling without DLQ

- Pros: simpler consumer code.
- Cons: messages can pend forever; failures aren’t reviewable.
- Why rejected: we need deterministic handling at max retries.

## References

- Envelope concept: `docs/concepts/envelope.md`
- Envelope API schema: `docs/reference/api/envelope.md`
- DLQ core: `core/dlq.py`
- Portal + Gateway auth setup: `docs/guides/dev/portal-gateway-auth.md`
- Internal Portal: `docs/websites/portal.md`
- Customer Portal: `docs/websites/portal-customer.md`
- Customer portal deploy/auth URLs: `docs/guides/dev/customer-portal.md`
- Supabase auth + RLS decision baseline: `docs/architecture/decisions/004-supabase-rls-3-layer-auth.md`
