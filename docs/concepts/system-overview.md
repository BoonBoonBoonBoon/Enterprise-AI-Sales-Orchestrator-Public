# System Overview

The Agentic System is an enterprise-grade AI agent orchestration platform designed for automated lead management and outreach.

## What It Does

The system automates the entire lead lifecycle:

```
Inbound Email → Lead Extraction → Enrichment → Qualification → Reply Generation → Outreach
```

## Core Capabilities

### Lead Management

- Ingest leads from multiple sources
- Enrich with external data (Crunchbase, LinkedIn)
- Score and qualify leads
- Track conversation history

### Intelligent Outreach

- Generate personalized email content
- Draft context-aware replies
- Execute multi-step campaigns
- Respect rate limits and best practices

### AI-Powered Decisions

- Intent classification for routing
- Context retrieval for personalization
- LLM-based content generation
- Smart workflow orchestration

## Architecture at a Glance

The system uses a **three-tier architecture**:

```
┌─────────────────────────────────────────┐
│           TIER 1: MANAGER               │
│       Strategic decisions & routing     │
└─────────────────────┬───────────────────┘
                      │
┌─────────────────────┴───────────────────┐
│         TIER 2: ORCHESTRATORS           │
│   Leads | Outreach | Inbound workflows  │
└─────────────────────┬───────────────────┘
                      │
┌─────────────────────┴───────────────────┐
│           TIER 3: AGENTS                │
│    RAG | Persistence | Copywriter       │
└─────────────────────────────────────────┘
```

- **Tier 1:** High-level decision making
- **Tier 2:** Business logic and workflow coordination
- **Tier 3:** Atomic task execution

## Key Technologies

| Layer           | Technology            |
| --------------- | --------------------- |
| Messaging       | Redis Streams         |
| Database        | Supabase (PostgreSQL) |
| Agent Framework | LangGraph             |
| LLM             | OpenAI / Anthropic    |
| Security        | JWT + RLS             |

## Design Principles

### Vertical Communication

Agents only communicate up/down the tier hierarchy, never horizontally. This prevents coupling and enables scaling.

### Message Envelopes

All communication uses standardized JSON envelopes with task IDs, tenant IDs, and metadata for traceability.

### Agent Harness Pattern

Every agent is wrapped in a harness that handles Redis, error handling, and lifecycle management.

### Multi-Tenancy

Complete data isolation via Redis stream prefixes and Supabase Row-Level Security.

## Next Steps

- [Quick Start](../getting-started/quickstart.md) — Get running in 10 minutes
- [Three-Tier Architecture](three-tier-architecture.md) — Deep dive
- [Components](../components/index.md) — Explore each component
