# API Gateway

FastAPI-based REST API gateway for the Agentic Portal.

## Overview

This gateway serves as the customer-facing API layer. It:

- Authenticates requests (JWT/Supabase Auth)
- Enforces tenant isolation
- Provides RESTful endpoints for portal functionality
- Delegates internal operations to Redis streams (never exposed directly)

## Endpoints

| Method | Path                          | Description                    |
| ------ | ----------------------------- | ------------------------------ |
| GET    | `/api/v1/health`              | Health check                   |
| POST   | `/api/v1/auth/login`          | User login                     |
| POST   | `/api/v1/auth/signup`         | User registration              |
| GET    | `/api/v1/auth/me`             | Current user info              |
| GET    | `/api/v1/drafts`              | List pending drafts            |
| GET    | `/api/v1/drafts/{id}`         | Get draft details              |
| POST   | `/api/v1/drafts/{id}/approve` | Approve and send draft         |
| POST   | `/api/v1/drafts/{id}/reject`  | Reject draft                   |
| GET    | `/api/v1/leads`               | List leads                     |
| GET    | `/api/v1/leads/stats`         | Lead statistics                |
| GET    | `/api/v1/leads/{id}`          | Get lead details               |
| GET    | `/api/v1/mailboxes`           | List connected mailboxes       |
| POST   | `/api/v1/mailboxes`           | Connect new mailbox            |
| DELETE | `/api/v1/mailboxes/{id}`      | Disconnect mailbox             |
| GET    | `/api/v1/conversations`       | List conversations             |
| GET    | `/api/v1/conversations/{id}`  | Get conversation with messages |

## Running

### Development

```bash
cd api/gateway
pip install -e .
uvicorn main:app --reload --port 8000
```

### With the Portal

The portal proxies API requests to this gateway. Configure `API_GATEWAY_URL` in the portal's environment.

## Architecture

```
Portal (Next.js)
    │
    │ HTTP /api/v1/*
    ▼
┌─────────────────────────────────┐
│  API Gateway (FastAPI)          │
│  - Auth middleware              │
│  - Tenant isolation             │
│  - Rate limiting                │
└────────────┬────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
Supabase          Redis Streams
(Data)            (Internal ops)
```

## Redis Stream Delegation (Drafts)

The gateway enqueues draft approvals and rewrites to the **Outreach Orchestrator** stream:

- Stream: `{tenant}:orchestrators:outbound:tasks`
- Envelope: typed envelope from `core.envelope.task()` serialized via `to_redis_fields()`

Payload format:

```json
{
  "goal": "Send approved draft",
  "data": {
    "action": "approve_draft",
    "draft_id": "draft_123",
    "approved_content": "...optional...",
    "draft": { "id": "draft_123", "subject": "..." }
  }
}
```

Rewrite requests use:

```json
{
  "goal": "Rewrite draft",
  "data": {
    "action": "rewrite_draft",
    "draft_id": "draft_123",
    "draft": { "id": "draft_123", "subject": "..." }
  }
}
```

## TODO

- [ ] Integrate Supabase Auth for JWT validation
- [ ] Add rate limiting middleware
- [ ] Connect to real Supabase database
- [x] Implement Redis stream delegation for approvals/rewrite
- [ ] Add WebSocket/SSE for real-time updates
