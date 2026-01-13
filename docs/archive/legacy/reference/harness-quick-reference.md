# Agent Harness: Quick Reference Card

## File Locations
- **README.md** - Comprehensive guide (500+ lines)
- **config.py** - Configuration management
- **agent_harness.py** - Core wrapper
- **interfaces.py** - Component contracts

## Quick Start

```python
from agent.harness import AgentHarness, HarnessConfig

# Development
harness = AgentHarness(
    orchestrator,
    config=HarnessConfig.for_development()
)

# Production
harness = AgentHarness(
    orchestrator,
    config=HarnessConfig.for_production()
)

# Execute
result = await harness.execute(task_data)
```

## Component Interfaces

| Component | Interface | Purpose |
|-----------|-----------|---------|
| Retry | IRetryStrategy | Automatic retries with backoff |
| Observability | IObservability | Distributed tracing & metrics |
| Checkpointing | ICheckpointer | State persistence for resumption |
| Quota | IQuotaManager | Rate limiting & quota enforcement |

## Configuration Presets

| Preset | Retries | Backend | Timeout | Checkpointing |
|--------|---------|---------|---------|---------------|
| Development | 1 | Simple | 60s | ❌ None |
| Staging | 3 | OpenTel | 120s | ✅ Redis |
| Production | 5 | Datadog | 300s | ✅ S3 |

## Execution Flow

1. Check quota
2. Load checkpoint (resume)
3. Start tracing
4. Execute with retries
5. Save checkpoint
6. Record metrics
7. Return result

## Retry Strategies (Coming Week 5)

- **Exponential**: 1s, 2s, 4s, 8s... (LLM APIs)
- **Linear**: 2s, 4s, 6s, 8s... (Database)
- **Jittered**: Randomized (Production, multi-worker)

## Observability Backends (Coming Week 5)

- **OpenTelemetry**: CNCF standard (Jaeger, Zipkin, Honeycomb)
- **Datadog**: Datadog APM (existing infrastructure)
- **Simple**: Plain logging (development)

## Checkpointing Backends (Coming Week 5-6)

- **Redis**: Fast temporary (24h TTL)
- **S3**: Persistent audit trail (30d+)
- **PostgreSQL**: Queryable analytics (forever)

## Quota Managers (Coming Week 6)

- **Redis Token Bucket**: Distributed multi-worker
- **In-Memory**: Single process development

## Load Configuration

```python
# From environment
config = HarnessConfig.from_env()  # Uses ENVIRONMENT var

# From file
config = HarnessConfig.from_file("prod.json")

# Programmatic
config = HarnessConfig(
    max_retries=5,
    retry_strategy="jittered",
    observability_backend="datadog"
)

# Custom preset
config = HarnessConfig.for_production()
```

## Health Check

```python
health = await harness.health_check()
# Returns:
# {
#   "status": "healthy",
#   "harness": {...},
#   "components": {
#       "agent": {...},
#       "retry_strategy": {...},
#       "observability": {...},
#       "checkpointer": {...},
#       "quota_manager": {...}
#   }
# }
```

## Orchestrator-Specific Configs

**Leads Orchestrator** (Fast DB ops)
```python
HarnessConfig(
    max_retries=3,
    timeout_seconds=60,
    enable_checkpointing=False,
    requests_per_hour=1000
)
```

**Copywriter Orchestrator** (Slow LLM)
```python
HarnessConfig(
    max_retries=5,
    timeout_seconds=300,
    enable_checkpointing=True,
    checkpoint_backend="s3",
    requests_per_hour=500
)
```

**Coding Orchestrator** (Code gen)
```python
HarnessConfig(
    max_retries=4,
    timeout_seconds=180,
    enable_checkpointing=True,
    checkpoint_backend="postgres",
    requests_per_hour=300
)
```

**Manager Agent** (Strategic)
```python
HarnessConfig(
    max_retries=2,
    timeout_seconds=120,
    enable_checkpointing=True,
    checkpoint_backend="redis",
    requests_per_hour=2000
)
```

## Key Concepts

**Plugin Architecture**
- All components implement interfaces
- Swap any implementation without touching orchestrators

**Configuration-Driven**
- One config object controls everything
- Environment presets for dev/staging/prod

**Dependency Injection**
- Components injected, not hardcoded
- Easy to test and mock

**Production-Ready**
- Automatic retries with configurable backoff
- Distributed tracing support
- State checkpointing for resumption
- Rate limiting and quota enforcement

## Phase Timeline

- ✅ Week 4: Foundation (interfaces, config, core)
- ⏳ Week 5: Retry strategies & observability
- ⏳ Week 5-6: Checkpointing & quota managers
- ⏳ Week 6: Orchestrator wrappers
- ⏳ Week 7: Testing, docs, production

## Environment Variables

```bash
# Configuration
ENVIRONMENT=production  # development, staging, production
HARNESS_MAX_RETRIES=5
HARNESS_RETRY_STRATEGY=jittered
HARNESS_BASE_DELAY=1.0
HARNESS_OBSERVABILITY_BACKEND=datadog
HARNESS_SERVICE_NAME=agentic-system
HARNESS_ENABLE_CHECKPOINTING=true
HARNESS_CHECKPOINT_BACKEND=s3
HARNESS_CHECKPOINT_BUCKET=prod-checkpoints
HARNESS_ENABLE_QUOTA=true
HARNESS_QUOTA_BACKEND=redis
HARNESS_REQUESTS_PER_HOUR=1000
HARNESS_TIMEOUT_SECONDS=300
```

## Exception Handling

```python
from agent.harness.interfaces import QuotaExceededError

try:
    result = await harness.execute(task)
except QuotaExceededError:
    # Handle quota exceeded
    pass
except Exception as e:
    # Handle other errors (retries exhausted, etc.)
    pass
```

## Testing

All components are mockable via dependency injection:

```python
class MockRetryStrategy(IRetryStrategy):
    async def execute_with_retry(self, func, args, execution_id):
        return await func(*args)

mock_retry = MockRetryStrategy()
harness = AgentHarness(orchestrator, retry_strategy=mock_retry)
```

## Performance Tips

1. **Development**: Minimal retries (1), simple logging
2. **Staging**: Moderate retries (3), OpenTelemetry
3. **Production**: More retries (5), jittered backoff
4. **Cost**: Use 10% trace sampling in production
5. **Storage**: Use Redis for short-lived, S3 for long-term

## Debugging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("agentic-system")
```

Watch for:
- Retry attempts in logs
- Checkpoint saves/loads
- Quota checks
- Execution metrics

## Resources

- README.md - Full architecture guide
- interfaces.py - Component contracts
- config.py - Configuration options
- agent_harness.py - Core wrapper implementation

## Questions?

1. Check README.md for comprehensive explanations
2. Review interfaces.py for component contracts
3. Look at config.py for configuration options
4. Examine agent_harness.py for execution flow
5. See HARNESS_IMPLEMENTATION_ROADMAP.md for phases

---
Last updated: November 5, 2025
