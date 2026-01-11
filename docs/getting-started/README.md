# Getting Started with Agentic System

Welcome! This directory contains everything you need to get started with the Agentic System.

## 📋 Quick Navigation

- **[Quick Start](./quick-start.md)** - Get up and running in minutes
- **[Installation](./installation.md)** - Detailed installation instructions
- **[Docker Setup](./docker-setup.md)** - Containerized deployment guide
- **[Docker Reference](./docker-reference.md)** - Docker commands and reference
- **[Developer Guide](./developer-guide.md)** - Development environment setup
- **[Quick LLM Setup](./quick-setup-llm.md)** - LLM integration quick start

## 🚀 Recommended Path for New Users

### 1. First Steps (5-10 minutes)
Read the [Quick Start Guide](./quick-start.md) to understand the system basics and get your environment ready.

### 2. Installation (15-30 minutes)
Follow the [Installation Guide](./installation.md) for complete setup including:
- Prerequisites and dependencies
- Python environment setup
- Redis configuration
- Environment variables

### 3. Choose Your Deployment Method

**Option A: Local Development**
- Follow the [Developer Guide](./developer-guide.md)
- Set up your IDE and development tools

**Option B: Docker Deployment**
- Follow the [Docker Setup](./docker-setup.md)
- Use containerized services for quick deployment

### 4. Configure LLM Integration (10-15 minutes)
Use the [Quick LLM Setup](./quick-setup-llm.md) to configure:
- API keys for LLM providers
- Model selection
- Rate limiting

### 5. Verify Installation
Run the smoke tests to ensure everything is working:
```bash
pytest tests/smoke/ -v
```

## 📚 Additional Resources

After getting started:
- **Architecture**: See [docs/architecture/](../architecture/) to understand system design
- **API Reference**: See [docs/api/](../api/) for API documentation
- **Testing**: See [docs/guides/testing/](../guides/testing/) for testing procedures
- **Deployment**: See [docs/guides/deployment/](../guides/deployment/) for production deployment

## 🛠️ Prerequisites

Before you start, ensure you have:
- Python 3.10 or higher
- Redis 6.0 or higher (local or cloud)
- Docker (optional, for containerized deployment)
- Git (for version control)
- API keys for LLM providers (OpenAI, Anthropic, etc.)

## ⚡ Quick Commands

```bash
# Clone repository
git clone <repository-url>

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run tests
pytest tests/smoke/ -v

# Start the system (example)
python -m tiers.tier_1.manager.manager
```

## 💡 Tips for Success

1. **Read Documentation**: Start with overview docs before diving deep
2. **Use Docker for Quick Start**: Easiest way to get running
3. **Check Logs**: Monitor logs for troubleshooting
4. **Run Tests Early**: Validate your setup with smoke tests
5. **Ask Questions**: Check existing documentation and issues

## 🔗 Related Documentation

- [Architecture Overview](../architecture/overview.md) - Understand the system design
- [API Reference](../api/reference.md) - API documentation
- [Testing Guide](../guides/testing/overview.md) - How to run tests
- [Deployment Guide](../guides/deployment/overview.md) - Production deployment

## 📝 Need Help?

- Check the [Quick Reference](../reference/quick-reference.md) for common commands
- Review [Troubleshooting Guide](../guides/operations/incident-playbooks.md)
- See [Developer Guide](./developer-guide.md) for development tips

---

**Ready to start?** Begin with the [Quick Start Guide](./quick-start.md)!
