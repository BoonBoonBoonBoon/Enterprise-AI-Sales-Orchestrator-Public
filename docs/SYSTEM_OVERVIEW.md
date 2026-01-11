# Agentic System — Technical Product Overview

> **An enterprise-grade, AI-powered autonomous agent orchestration platform for intelligent lead generation and multi-channel outreach.**

---

## Executive Summary

The Agentic System is a **multi-agent AI orchestration platform** that autonomously manages the complete lifecycle of B2B sales outreach—from lead discovery and qualification through personalized engagement and meeting booking. Built on a fault-tolerant, horizontally scalable architecture, it demonstrates advanced software engineering principles including event-driven design, distributed systems patterns, and production-grade AI integration.

### What Makes It Different

| Traditional Automation     | Agentic System                                                        |
| -------------------------- | --------------------------------------------------------------------- |
| Rule-based workflows       | **Autonomous decision-making** with LLM reasoning                     |
| Single-threaded processing | **Massively parallel** via Redis Streams consumer groups              |
| Monolithic architecture    | **Three-tier separation** of strategic, business, and execution logic |
| Hard-coded sequences       | **Context-aware adaptation** using RAG and conversation memory        |
| Manual error handling      | **Self-healing** with retries, DLQ, and checkpointing                 |

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TIER 1: STRATEGIC LAYER                         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        MANAGER AGENT                             │   │
│  │  • Campaign-level decision making                                │   │
│  │  • Policy-driven routing (JSON/LLM fallback)                    │   │
│  │  • Cross-orchestrator coordination                              │   │
│  │  • Goal decomposition and delegation                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                   │                                     │
│                    ┌──────────────┴──────────────┐                     │
└────────────────────│─────────────────────────────│─────────────────────┘
                     ▼                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       TIER 2: BUSINESS LOGIC LAYER                      │
│                                                                         │
│  ┌──────────────────────┐         ┌───────────────────────────────┐   │
│  │  LEADS ORCHESTRATOR  │         │   OUTREACH ORCHESTRATOR       │   │
│  │  ─────────────────── │         │   ────────────────────────    │   │
│  │  • Lead discovery    │         │   • Email personalization     │   │
│  │  • Qualification     │         │   • Multi-channel sequencing  │   │
│  │  • Enrichment flows  │         │   • Reply classification      │   │
│  │  • Staging → Promote │         │   • Sentiment-aware responses │   │
│  └──────────┬───────────┘         └───────────────┬───────────────┘   │
│             │                                     │                     │
└─────────────│─────────────────────────────────────│─────────────────────┘
              │                                     │
              ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        TIER 3: EXECUTION LAYER                          │
│                                                                         │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │   RAG AGENT    │  │ PERSISTENCE AGENT │  │  COPYWRITER AGENT    │   │
│  │ ───────────────│  │ ────────────────  │  │ ──────────────────── │   │
│  │ Vector search  │  │ CRUD operations   │  │ LLM content gen      │   │
│  │ Lead context   │  │ Supabase adapter  │  │ Tone matching        │   │
│  │ Enrichment     │  │ RLS enforcement   │  │ Personalization      │   │
│  └────────────────┘  └──────────────────┘  └──────────────────────┘   │
│                                                                         │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │ SCHEDULER AGENT│  │ SEQUENCER AGENT  │  │  BOOKING AGENT       │   │
│  │ ───────────────│  │ ────────────────  │  │ ──────────────────── │   │
│  │ Time-aware     │  │ ML send-time opt │  │ Calendar integration │   │
│  │ Queue mgmt     │  │ Channel selection│  │ Meeting coordination │   │
│  └────────────────┘  └──────────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## How the System "Thinks"

### 1. Event-Driven Intelligence

The system operates on an **event-driven paradigm**. Every action—whether an inbound email, a new lead discovered, or a reply received—becomes an event that flows through Redis Streams.

```
[Event Occurs] → [Manager Evaluates] → [Delegates to Orchestrator] → [Agents Execute]
                        │
                        ▼
              ┌─────────────────────┐
              │   Decision Engine   │
              │  ─────────────────  │
              │  1. Policy lookup   │
              │  2. LLM fallback    │
              │  3. Route selection │
              └─────────────────────┘
```

**Example Flow: Inbound Email**

1. Email arrives → Event published to `{tenant}:manager:tasks`
2. Manager classifies intent (new lead? reply? spam?)
3. If new lead: delegates to Leads Orchestrator for qualification
4. If reply: delegates to Outreach Orchestrator for response generation
5. Orchestrator coordinates specialized agents (RAG for context, Copywriter for response)
6. Final output delivered through appropriate channel

### 2. Hierarchical Reasoning

The three-tier architecture mirrors how organizations make decisions:

| Tier              | Analogy          | Responsibility                               |
| ----------------- | ---------------- | -------------------------------------------- |
| **Manager**       | C-Suite          | Strategic goals, resource allocation, policy |
| **Orchestrators** | Department Heads | Workflow coordination, business rules        |
| **Agents**        | Specialists      | Atomic task execution, domain expertise      |

**Key Principle:** Each tier only communicates with adjacent tiers. Orchestrators never talk to each other directly—all cross-functional coordination flows through the Manager. This prevents tangled dependencies and enables independent scaling.

### 3. Context-Aware Personalization

The **RAG Agent** maintains rich context for every lead:

```python
# Context Cascade (searches in priority order)
1. leads table           → Company info, ICP match, deal stage
2. staging_leads         → Pre-qualification data
3. conversations         → Thread history, relationship state
4. messages              → Actual message content, timestamps

# Output: Unified lead context for personalization
{
    "company": "Acme Corp",
    "contacts": [...],
    "conversation_history": [...],
    "sentiment_trend": "warming",
    "last_interaction": "2 days ago",
    "key_topics": ["pricing", "integration"]
}
```

The **Copywriter Agent** uses this context to generate responses that feel human—matching tone, referencing previous discussions, and adapting to sentiment shifts.

### 4. Self-Healing & Reliability

```
┌─────────────────────────────────────────────────────────────┐
│                    RELIABILITY LAYER                         │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │   Retries   │ → │   Backoff   │ → │  Dead Letter Q  │ │
│  │  (3 max)    │    │ (exp 2^n)   │    │  (manual fix)   │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │Checkpointing│    │  Idempotent │    │  Provenance     │ │
│  │  (state)    │    │   Tasks     │    │  Tracking       │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

Every message carries a **standardized envelope** with:

- `task_id`: UUID for idempotency
- `tenant_id`: Multi-tenant isolation
- `metadata`: Source, target, timestamps, parent task chain
- `provenance`: Full audit trail of which agents touched the task

---

## Technology Stack

### Core Infrastructure

| Component           | Technology            | Purpose                              |
| ------------------- | --------------------- | ------------------------------------ |
| **Language**        | Python 3.11+          | Primary runtime                      |
| **Message Broker**  | Redis Streams         | Async communication, consumer groups |
| **Database**        | PostgreSQL (Supabase) | Persistent storage with RLS          |
| **Vector Store**    | pgvector / Pinecone   | Semantic search, embeddings          |
| **LLM Integration** | OpenAI GPT-4 / Claude | Reasoning, content generation        |
| **Orchestration**   | LangGraph             | Stateful agent workflows             |

### DevOps & Observability

| Component            | Technology              | Purpose                     |
| -------------------- | ----------------------- | --------------------------- |
| **Containerization** | Docker                  | Reproducible deployments    |
| **Orchestration**    | Kubernetes (target)     | Production scaling          |
| **Tracing**          | OpenTelemetry + Datadog | Distributed tracing         |
| **Metrics**          | Prometheus + Grafana    | Performance monitoring      |
| **Logging**          | Loki + Promtail         | Centralized log aggregation |

### Security

| Feature                | Implementation                                   |
| ---------------------- | ------------------------------------------------ |
| **Multi-tenancy**      | Tenant-prefixed Redis keys, RLS policies         |
| **Row-Level Security** | PostgreSQL RLS with JWT claims                   |
| **Role Separation**    | `agent_reader` (SELECT) vs `agent_writer` (CRUD) |
| **Secrets Management** | Environment variables, no hardcoded credentials  |

---

## Scalability Characteristics

### Horizontal Scaling via Consumer Groups

```
┌──────────────────────────────────────────────────────────────┐
│  Redis Stream: agentic-dev:agents:persistence:tasks          │
│                                                              │
│  Consumer Group: persistence-workers                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │Worker 1 │  │Worker 2 │  │Worker 3 │  │Worker N │       │
│  │ (pod-a) │  │ (pod-b) │  │ (pod-c) │  │ (pod-n) │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│       ↓            ↓            ↓            ↓              │
│   Messages distributed automatically—no coordination needed │
└──────────────────────────────────────────────────────────────┘
```

**Scaling commands:**

```bash
# Scale Tier 3 agents independently
docker compose up -d --scale persistence_agent=5
docker compose up -d --scale rag_agent=3
docker compose up -d --scale copywriter_agent=4
```

### Performance Targets

| Metric                        | Target       | Current     |
| ----------------------------- | ------------ | ----------- |
| Lead processing throughput    | 1,000/hour   | ✅ Achieved |
| Email personalization latency | < 3 seconds  | ✅ Achieved |
| End-to-end message handling   | < 10 seconds | ✅ Achieved |
| System availability           | 99.9%        | 🎯 Target   |

---

## Engineering Principles

### 1. Separation of Concerns

Each agent has a single responsibility. The Copywriter writes; it never decides _when_ to write. The Manager decides; it never writes content.

### 2. Vertical Communication Only

Tier 2 orchestrators cannot communicate horizontally. All coordination flows through Tier 1. This prevents spaghetti dependencies and enables independent testing.

### 3. Envelope-Based Messaging

Every inter-agent message uses a standardized JSON envelope, ensuring consistent logging, tracing, and replay capability.

### 4. Fail-Safe Defaults

Unknown events go to the Manager for classification. Failed tasks go to Dead Letter Queues. Every decision has an audit trail.

### 5. Configuration-Driven Behavior

Business logic lives in policy files and environment variables—not hardcoded in agent code. This enables A/B testing and rapid iteration.

---

## Use Cases Demonstrated

| Use Case                     | Agents Involved      | Key Features                           |
| ---------------------------- | -------------------- | -------------------------------------- |
| **Lead Discovery**           | RAG, Persistence     | Vector search, data enrichment         |
| **Email Personalization**    | Copywriter, RAG      | Context-aware content, tone matching   |
| **Reply Classification**     | Manager, Leads       | Intent detection, sentiment analysis   |
| **Multi-Channel Sequencing** | Sequencer, Scheduler | ML-optimized timing, channel selection |
| **Meeting Booking**          | Booking, Persistence | Calendar sync, availability matching   |

---

## What This Project Demonstrates

### Technical Skills

- **Distributed Systems Design** — Event-driven architecture, message queues, consumer groups
- **AI/ML Integration** — LLM orchestration, RAG pipelines, embedding models
- **Production Engineering** — Docker, Kubernetes, observability, CI/CD
- **Database Design** — PostgreSQL with RLS, multi-tenant architecture
- **API Design** — RESTful patterns, typed envelopes, schema validation

### Software Engineering Practices

- **Clean Architecture** — Three-tier separation, dependency inversion
- **Testing Strategy** — Unit, integration, and E2E test suites
- **Documentation** — Comprehensive README coverage, architectural decision records
- **DevOps Maturity** — Infrastructure as code, monitoring, alerting

### Problem-Solving Approach

- **Systems Thinking** — Understanding how components interact at scale
- **Trade-off Analysis** — Choosing Redis Streams over Kafka (simplicity vs features)
- **Incremental Design** — Building for today's scale with tomorrow's growth in mind

---

## Repository Structure

```
agentic-system/
├── tiers/                      # Three-tier agent architecture
│   ├── tier_1/manager/         # Strategic decision-making
│   ├── tier_2/                 # Business logic orchestrators
│   │   ├── leads_orchestrator/
│   │   └── outreach_orchestrator/
│   └── tier_3/                 # Specialized execution agents
│       ├── rag_agent/
│       ├── persistence_agent/
│       ├── copywriter_agent/
│       └── ...
├── core/                       # Framework components
│   ├── harness/                # Agent lifecycle management
│   ├── envelope/               # Message standardization
│   └── deep_agents/            # LangGraph integration
├── services/                   # Shared infrastructure
│   ├── redis/                  # Stream client
│   ├── persistence/            # Database adapter
│   └── vector_db/              # Embedding store
├── docs/                       # Documentation
├── tests/                      # Test suites
└── deployment/                 # Docker & Kubernetes
```

---

## Contact & Further Discussion

This system represents my approach to building production-grade AI infrastructure. I'm happy to discuss:

- Architectural decisions and trade-offs
- Scaling strategies for high-volume workloads
- AI/ML integration patterns
- Any technical deep-dive into specific components

---

_Built with Python, Redis, PostgreSQL, LangGraph, and OpenAI._
