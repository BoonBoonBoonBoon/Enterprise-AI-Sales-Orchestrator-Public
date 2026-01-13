# Agentic System Documentation

Welcome to the **Agentic System** documentation—a comprehensive guide to understanding, deploying, and extending this enterprise-grade AI agent orchestration platform.

---

## What is the Agentic System?

The Agentic System is a **multi-agent AI platform** that autonomously manages B2B sales outreach from lead discovery through meeting booking. It demonstrates production-grade distributed systems design, AI/ML integration, and modern DevOps practices.

<div class="grid cards" markdown>

- :material-layers-triple:{ .lg .middle } **Three-Tier Architecture**

  ***

  Strategic, business logic, and execution layers with clear separation of concerns.

  [:octicons-arrow-right-24: Architecture](concepts/three-tier-architecture.md)

- :material-message-flash:{ .lg .middle } **Event-Driven Design**

  ***

  Redis Streams power async communication with horizontal scalability via consumer groups.

  [:octicons-arrow-right-24: Redis Streams](concepts/redis-streams.md)

- :material-robot:{ .lg .middle } **Autonomous Agents**

  ***

  Specialized agents for RAG, persistence, copywriting, and orchestration.

  [:octicons-arrow-right-24: Components](components/index.md)

- :material-security:{ .lg .middle } **Production-Ready**

  ***

  Multi-tenant isolation, RLS, observability, and self-healing reliability patterns.

  [:octicons-arrow-right-24: Deployment Guide](guides/deploy/docker.md)

</div>

---

## Quick Navigation

### By Role

| I want to...              | Start here                                     |
| ------------------------- | ---------------------------------------------- |
| **Understand the system** | [System Overview](concepts/system-overview.md) |
| **Run it locally**        | [Quick Start](getting-started/quickstart.md)   |
| **Extend an agent**       | [Adding a New Agent](guides/dev/new-agent.md)  |
| **Deploy to production**  | [Deployment Guide](guides/deploy/docker.md)    |
| **Write tests**           | [Testing Guide](guides/dev/testing.md)         |

### By Topic

| Topic                | Documentation                                                                   |
| -------------------- | ------------------------------------------------------------------------------- |
| **Redis Streams**    | [Concept](concepts/redis-streams.md) · [Stream Keys](reference/api/streams.md)  |
| **RAG Pipeline**     | [RAG Agent](components/tier-3/rag.md)                                           |
| **Orchestrators**    | [Leads](components/tier-2/leads.md) · [Outreach](components/tier-2/outreach.md) |
| **Message Envelope** | [Concept](concepts/envelope.md) · [Schema](reference/api/envelope.md)           |

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│  TIER 1: Manager Agent                                          │
│  Strategic decisions, policy routing, cross-orchestrator coord  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│ Leads Orch.     │  │ Outreach Orch.  │  │ Inbound Orch.       │
│ Discovery/Qual  │  │ Personalization │  │ Reply Processing    │
└────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 3: Specialized Agents                                     │
│  RAG · Persistence · Copywriter                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Getting Started

=== "Development"

    ```bash
    # Clone and setup
    git clone https://github.com/BoonBoonBoonBoon/Agentic-System
    cd Agentic-System
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1  # Windows
    pip install -r requirements.txt

    # Run tests
    pytest tests/unit/ -v
    ```

=== "Docker"

    ```bash
    docker-compose up -d
    ```

=== "Production"

    See the full [Deployment Guide](guides/deploy/kubernetes.md) for Kubernetes setup.

---

## Documentation Status

| Section         | Status      |
| --------------- | ----------- |
| Getting Started | ✅ Complete |
| Concepts        | ✅ Complete |
| Components      | ✅ Complete |
| Guides          | ✅ Complete |
| Reference       | ✅ Complete |
| Architecture    | ✅ Complete |
| ADRs            | ✅ Complete |
| Roadmap         | ✅ Complete |

---

!!! tip "Contributing to Docs"

    Documentation lives in the `docs/` folder. Edit any `.md` file and run `mkdocs serve` to preview changes locally.
