# Guides

Practical, task-oriented guides for developing, operating, and deploying the Agentic System.

## Guide Categories

<div class="grid cards" markdown>

- :material-code-braces:{ .lg .middle } **Development**

  ***

  Build and extend the system with new agents, orchestrators, and features.
  - [Adding a New Agent](dev/new-agent.md)
  - [Adding an Orchestrator](dev/new-orchestrator.md)
  - [Writing Tests](dev/testing.md)
  - [LLM Integration](dev/llm-integration.md)

- :material-console:{ .lg .middle } **Operations**

  ***

  Run, monitor, and troubleshoot the system in development and production.
  - [Running Consumers](ops/consumers.md)
  - [Monitoring](ops/monitoring.md)
  - [Troubleshooting](ops/troubleshooting.md)
  - [Incident Response](ops/incident-response.md)

- :material-rocket-launch:{ .lg .middle } **Deployment**

  ***

  Deploy the system to various environments using Docker, Kubernetes, or cloud platforms.
  - [Docker Compose](deploy/docker.md)
  - [Kubernetes](deploy/kubernetes.md)
  - [CI/CD](deploy/ci-cd.md)
  - [Secrets Management](deploy/secrets.md)

</div>

## Quick Reference

### Most Common Tasks

| Task                        | Guide                                                                 |
| --------------------------- | --------------------------------------------------------------------- |
| Add a new Tier 3 agent      | [Adding a New Agent](dev/new-agent.md)                                |
| Start all consumers locally | [Running Consumers](ops/consumers.md)                                 |
| Debug a failing task        | [Troubleshooting](ops/troubleshooting.md)                             |
| Understand staging → leads  | [Staging & Deduplication](staging-deduplication.md)                   |
| Pricing & competitor notes  | [Pricing & Competitive Research](pricing-and-competitive-research.md) |
| Deploy with Docker          | [Docker Compose](deploy/docker.md)                                    |
| Run the test suite          | [Writing Tests](dev/testing.md)                                       |

### Development Workflow

1. **Setup** — Follow [Getting Started](../getting-started/index.md)
2. **Develop** — Use the [Development Guides](dev/new-agent.md)
3. **Test** — Run tests per [Testing Guide](dev/testing.md)
4. **Deploy** — Follow [Deployment Guides](deploy/docker.md)
5. **Monitor** — Use [Operations Guides](ops/monitoring.md)

## Prerequisites

Before following these guides, ensure you have:

- [ ] Completed [Installation](../getting-started/installation.md)
- [ ] Set up [Environment Variables](../getting-started/environment.md)
- [ ] Run the [Quick Start](../getting-started/quickstart.md) tutorial

## Contributing

Found an issue or want to improve a guide? See our [Contributing Guidelines](../roadmap/index.md).
