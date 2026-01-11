# Agentic System Documentation

Welcome to the **Agentic System** documentation—a comprehensive guide to understanding, deploying, and extending this enterprise-grade AI agent orchestration platform.

---

## What is the Agentic System?

The Agentic System is a **multi-agent AI platform** that autonomously manages B2B sales outreach from lead discovery through meeting booking. It demonstrates production-grade distributed systems design, AI/ML integration, and modern DevOps practices.

<div class="grid cards" markdown>

- :material-layers-triple:{ .lg .middle } **Three-Tier Architecture**

  ***

  Strategic, business logic, and execution layers with clear separation of concerns.

  [:octicons-arrow-right-24: Architecture](COMPLETE_ARCHITECTURE_REFERENCE.md)

- :material-message-flash:{ .lg .middle } **Event-Driven Design**

  ***

  Redis Streams power async communication with horizontal scalability via consumer groups.

  [:octicons-arrow-right-24: Redis Architecture](architecture/redis/overview.md)

- :material-robot:{ .lg .middle } **Autonomous Agents**

  ***

  Specialized agents for RAG, persistence, copywriting, scheduling, and more.

  [:octicons-arrow-right-24: Agent Documentation](https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/tiers/tier_3/README.md)

- :material-security:{ .lg .middle } **Production-Ready**

  ***

  Multi-tenant isolation, RLS, observability, and self-healing reliability patterns.

  [:octicons-arrow-right-24: Deployment Guide](guides/deployment/overview.md)

</div>

---

## Quick Navigation

### By Role

| I want to...              | Start here                                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Understand the system** | [System Overview](SYSTEM_OVERVIEW.md)                                                                  |
| **Run it locally**        | [Quick Start](getting-started/RUNDOWN_AND_FRONTEND_ACCESS.md)                                          |
| **Extend an agent**       | [Tier 3 Agents](https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/tiers/tier_3/README.md) |
| **Deploy to production**  | [Deployment Guide](guides/deployment/overview.md)                                                      |
| **Write tests**           | [Testing Protocols](TESTING_PROTOCOLS.md)                                                              |

### By Topic

| Topic                | Documentation                                                                                                                                        |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Redis Streams**    | [Overview](architecture/redis/overview.md) · [Implementation](architecture/redis/implementation.md) · [Operations](architecture/redis/operations.md) |
| **RAG Pipeline**     | [RAG Architecture](RAG_ARCHITECTURE.md)                                                                                                              |
| **Orchestrators**    | [Tier 2 README](https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/tiers/tier_2/README.md)                                               |
| **Message Envelope** | [Reference](reference/quick-reference.md)                                                                                                            |

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
│ Leads Orch.     │  │ Outreach Orch.  │  │ Control Orch.       │
│ Discovery/Qual  │  │ Personalization │  │ Campaign Management │
└────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 3: Specialized Agents                                     │
│  RAG · Persistence · Copywriter · Scheduler · Sequencer · ...   │
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
    cd deployment
    docker compose up -d redis postgres
    docker compose up -d
    ```

=== "Production"

See the full [Deployment Guide](guides/deployment/overview.md) for Kubernetes setup.

---

## Documentation Status

| Section                | Status         |
| ---------------------- | -------------- |
| Architecture           | ✅ Complete    |
| Tier 1 (Manager)       | ✅ Complete    |
| Tier 2 (Orchestrators) | ✅ Complete    |
| Tier 3 (Agents)        | ✅ Complete    |
| Services               | ✅ Complete    |
| API Reference          | 🔄 In Progress |
| Deployment             | 🔄 In Progress |

---

!!! tip "Contributing to Docs"

    Documentation lives in the `docs/` folder. Edit any `.md` file and run `mkdocs serve` to preview changes locally.
