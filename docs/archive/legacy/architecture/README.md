# Architecture Documentation

This directory contains comprehensive architectural documentation for the Agentic System.

## 📋 Contents

### System Architecture

- **[Overview](./overview.md)** - High-level system architecture
- **[Three-Tier System](./three-tier-system.md)** - Detailed three-tier architecture design
- **[Design Principles](./design-principles.md)** - Core design principles and patterns
- **[File Organization](./file-organization.md)** - Project file structure guide
- **[Structure Visual](./structure-visual.md)** - Visual representation of system structure

### Components

Located in [components/](./components/):

- **[Manager](./components/manager.md)** - Tier 1 Manager implementation
- **[Orchestrators](./components/orchestrators.md)** - Tier 2 Orchestrators (Leads, Outreach)
- **[Copywriter](./components/copywriter-summary.md)** - Tier 3 Copywriter agent
- **[Envelope](./components/envelope.md)** - Message envelope system
- **[Harness](./components/harness-roadmap.md)** - Agent harness architecture
- **[DeepAgents Overview](./components/deep-agents-overview.md)** - DeepAgents integration
- **[DeepAgents Integration](./components/deep-agents-integration.md)** - Integration details

### Services

Located in [services/](./services/):

- **[Redis](./redis/overview.md)** - Redis service architecture
- **[Redis Implementation](./redis/implementation.md)** - Redis data structures and stream details
- **[Redis Operations](./redis/operations.md)** - Operational guidance
- **[Persistence](./services/persistence.md)** - Persistence service architecture

## 🏗️ System Overview

The Agentic System follows a **three-tier architecture**:

### Tier 1: Manager

- Central orchestration and delegation
- Request routing and load balancing
- High-level decision making

### Tier 2: Orchestrators

- **Leads Orchestrator**: Lead generation workflow
- **Outreach Orchestrator**: Outreach campaign management
- Task decomposition and coordination

### Tier 3: Specialized Agents

- **RAG Agent**: Retrieval-augmented generation
- **Persistence Agent**: Data persistence operations
- **Copywriter Agent**: Content generation
- Focused, single-purpose functionality

## 🔧 Core Components

### Envelope System

Message wrapper for inter-agent communication with:

- Routing information
- Metadata and context
- Error handling
- Tracing support

### Harness Framework

Agent execution framework providing:

- Retry strategies
- Checkpointing
- Observability
- Error handling

### DeepAgents

Advanced agent capabilities with:

- LangGraph integration
- LangChain tools
- Memory management
- Tool calling

## 🔌 Services Layer

### Redis Service

- Stream-based messaging
- Consumer groups
- Pub/sub patterns
- Health monitoring

### Persistence Service

- Database operations
- Query management
- Data models
- Transaction handling

### Vector DB Service

- Vector search
- Embedding management
- Similarity queries

### External APIs Service

- Third-party integrations
- API adapters
- Rate limiting

## 📐 Design Principles

Key principles guiding the architecture:

1. **Separation of Concerns**: Clear boundaries between tiers and services
2. **Modularity**: Independent, reusable components
3. **Scalability**: Horizontal scaling support
4. **Observability**: Comprehensive logging and tracing
5. **Resilience**: Retry strategies, error handling, fallbacks
6. **Type Safety**: Strong typing with Pydantic models
7. **Testability**: Unit, integration, and E2E test support

## 🗂️ File Organization

The project follows a structured organization:

```
project_root/
├── tiers/
│   ├── tier_1/manager/
│   ├── tier_2/leads_orchestrator/
│   ├── tier_2/outreach_orchestrator/
│   └── tier_3/{rag,persistence,copywriter}_agent/
├── services/
│   ├── persistence/
│   ├── redis/
│   ├── vector_db/
│   └── external_apis/
├── core/
│   ├── harness/
│   ├── envelope/
│   └── deep_agents/
├── config/
├── scripts/
└── tests/
```

## 🔍 Detailed Documentation

### For Component Details

See [components/](./components/) for deep dives into:

- Manager delegation logic
- Orchestrator workflows
- Agent implementations
- Envelope format and usage
- Harness capabilities
- DeepAgents integration

### For Service Details

See [services/](./services/) for comprehensive coverage of:

- Redis architecture and patterns
- Persistence layer design
- Vector DB integration
- External API adapters

### For System Design

See main architecture files for:

- [System Overview](./overview.md) - Big picture
- [Three-Tier System](./three-tier-system.md) - Tier architecture
- [Design Principles](./design-principles.md) - Design philosophy
- [File Organization](./file-organization.md) - Code structure

## 🔗 Related Documentation

- **[API Reference](../api/reference.md)** - API specifications
- **[Migration Docs](../migration/)** - System evolution
- **[Getting Started](../getting-started/)** - Setup and installation
- **[Guides](../guides/)** - Development and operations guides

## 📚 Learning Path

**New to the architecture?**

1. Read [Overview](./overview.md) for high-level understanding
2. Study [Three-Tier System](./three-tier-system.md) for architectural details
3. Review [Design Principles](./design-principles.md) for philosophy
4. Explore [Components](./components/) for component-specific information
5. Dive into [Services](./services/) for service layer details

**Implementing new features?**

1. Review relevant component/service documentation
2. Check [Design Principles](./design-principles.md) for guidance
3. Follow [File Organization](./file-organization.md) for structure
4. See [Developer Guide](../getting-started/developer-guide.md) for workflow

---

**Questions?** Check the [Quick Reference](../reference/quick-reference.md) or component-specific docs.
