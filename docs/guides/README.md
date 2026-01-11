# Guides

This directory contains how-to guides for development, deployment, operations, and testing.

## 📚 Guide Categories

### 💻 [Development](./development/)

Guides for developing the Agentic System:

- **[Type Safety](./development/type-safety.md)** - Type checking and Pydantic models
- **[LLM Integration](./development/llm-integration.md)** - Integrating LLM providers

### 🚀 [Deployment](./deployment/)

Guides for deploying the system:

- **[Deployment Overview](./deployment/overview.md)** - Deployment strategies
- **[Monitoring](./deployment/monitoring.md)** - Monitoring setup (Prometheus, Grafana)
- **[Monitoring Setup](./deployment/monitoring-setup.md)** - Detailed monitoring configuration
- **[CI/CD Setup](./deployment/ci-cd-setup.md)** - Continuous integration/deployment
- **[CI/CD Summary](./deployment/ci-cd-summary.md)** - CI/CD implementation summary
- **[Secrets Management](./deployment/secrets.md)** - Managing secrets and credentials

### ⚙️ [Operations](./operations/)

Guides for operating the system:

- **[Incident Playbooks](./operations/incident-playbooks.md)** - Incident response procedures

### 🧪 [Testing](./testing/)

Guides for testing the system:

- **[Testing Overview](./testing/overview.md)** - Testing strategy and quick start
- **[E2E Tests](./testing/e2e-tests.md)** - End-to-end testing guide

## 🎯 Quick Links by Use Case

### I want to develop features

1. Set up development environment: [Getting Started](../getting-started/developer-guide.md)
2. Understand architecture: [Architecture Overview](../architecture/overview.md)
3. Follow type safety guidelines: [Type Safety](./development/type-safety.md)
4. Integrate LLMs: [LLM Integration](./development/llm-integration.md)
5. Write tests: [Testing Overview](./testing/overview.md)

### I want to deploy the system

1. Review deployment options: [Deployment Overview](./deployment/overview.md)
2. Set up Docker: [Docker Setup](../getting-started/docker-setup.md)
3. Configure monitoring: [Monitoring Setup](./deployment/monitoring-setup.md)
4. Set up CI/CD: [CI/CD Setup](./deployment/ci-cd-setup.md)
5. Manage secrets: [Secrets Management](./deployment/secrets.md)

### I want to operate the system

1. Set up monitoring: [Monitoring](./deployment/monitoring.md)
2. Learn incident response: [Incident Playbooks](./operations/incident-playbooks.md)
3. Check system health: [API Reference](../api/reference.md)

### I want to test the system

1. Quick start: [Testing Overview](./testing/overview.md)
2. Run E2E tests: [E2E Tests](./testing/e2e-tests.md)
3. Understand test structure: [Developer Guide](../getting-started/developer-guide.md)

## 📖 Guide Conventions

### Guide Structure

Each guide follows a consistent structure:

- **Overview**: What the guide covers
- **Prerequisites**: What you need before starting
- **Step-by-step Instructions**: Detailed walkthrough
- **Examples**: Practical examples
- **Troubleshooting**: Common issues and solutions
- **Next Steps**: Related guides and further reading

### Code Examples

All code examples are:

- ✅ Tested and verified
- ✅ Properly formatted
- ✅ Include comments for clarity
- ✅ Show best practices

### Commands

Commands are shown with:

- Platform-specific variations when needed
- Expected output
- Explanation of what they do

## 🔗 Related Documentation

- **[Getting Started](../getting-started/)** - Initial setup
- **[Architecture](../architecture/)** - System design
- **[API Reference](../api/)** - API documentation
- **[Migration](../migration/)** - System evolution
- **[Reference](../reference/)** - Quick references

## 💡 Tips

### Development

- Use type hints and Pydantic models for type safety
- Write tests alongside code
- Follow the existing code structure
- Use the harness framework for agents

### Deployment

- Start with Docker for simplicity
- Monitor from day one
- Use CI/CD for consistency
- Secure secrets properly

### Operations

- Have incident playbooks ready
- Monitor key metrics
- Set up alerts proactively
- Document incident responses

### Testing

- Run smoke tests frequently
- Write integration tests for workflows
- Use E2E tests for critical paths
- Test error handling

## 🆘 Need Help?

Can't find what you're looking for?

- Check [Quick Reference](../reference/quick-reference.md) for common commands
- Review [Architecture Overview](../architecture/overview.md) for context
- See [Developer Guide](../getting-started/developer-guide.md) for development setup
- Check [Updates](../updates/index.md) for recent changes

---

**Choose a guide category above to get started!**
