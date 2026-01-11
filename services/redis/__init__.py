"""Redis service layer for pub/sub and streams communication.

This service layer provides:
- **Pub/Sub Communication**: Publish-subscribe pattern for agent communication
- **Streams Support**: Redis Streams for task/result message flow with consumer groups
- **Configuration Management**: Centralized configuration for all Redis operations
- **Message Schemas**: Type-safe dataclasses for common message patterns

Exported Components
-------------------
- RedisPubSub: Lightweight pub/sub wrapper supporting streams, channels, and consumer groups
- config/streams: Configuration module with environment-based settings
- messages: Message schema dataclasses (QueryTask, QueryResponse)
- QueryTask: Task envelope for RAG queries
- QueryResponse: Response envelope from agents

Design Principles
-----------------
- **Unified Interface**: Single RedisPubSub class for all Redis operations
- **Namespace Support**: Automatic namespacing of all channels/streams
- **Consumer Groups**: Support for scalable consumer groups (XREADGROUP)
- **JSON Serialization**: Automatic JSON encoding/decoding of payloads
- **Fallback Handling**: REST fallback for SDK failures (SupabaseAdapter pattern)
- **Configuration**: Environment-based settings with sensible defaults

Configuration
--------------
Redis connection settings (via environment variables):
- REDIS_URL: Full connection URL (preferred, supports TLS via rediss://)
- REDIS_HOST: Host (default: localhost)
- REDIS_PORT: Port (default: 6379)
- REDIS_DB: Database number (default: 0)
- REDIS_PASSWORD: Optional password
- REDIS_NAMESPACE: Namespace prefix (default: agentic)

Stream configuration:
- REDIS_STREAM_TASKS: RAG task stream name (default: rag:tasks)
- REDIS_STREAM_RESULTS: RAG result stream name (default: rag:results)
- REDIS_STREAM_TASKS_WRITE: Persistence task stream (default: persist:tasks)
- REDIS_STREAM_RESULTS_WRITE: Persistence result stream (default: persist:results)
- REDIS_STREAM_TASKS_COPY: Copywriter task stream (default: copy:tasks)
- REDIS_STREAM_RESULTS_COPY: Copywriter result stream (default: copy:results)

Consumer groups:
- REDIS_GROUP: RAG worker group name (default: rag-workers)
- REDIS_GROUP_WRITERS: Persistence worker group (default: persist-writers)
- REDIS_GROUP_COPY_WRITERS: Copywriter worker group (default: copy-writers)

Examples
--------
```python
from services.redis import RedisPubSub, QueryTask
from services.redis import config

# Create Redis client
redis_client = RedisPubSub()

# Streams: Add task
task = QueryTask.create(table="clients", filters={"domain": "%acme%"})
msg_id = redis_client.xadd(config.STREAM_TASKS, {"task": task.to_dict()})

# Streams: Read with consumer group
redis_client.xreadgroup(
    group=config.GROUP_WORKERS,
    consumer="worker_1",
    streams={config.STREAM_TASKS: ">"}
)

# Pub/Sub: Publish
redis_client.publish("status", {"worker": "ready"})

# Cleanup
redis_client.close()
```
"""

from services.redis.client import RedisStreamsClient
# Backward compatibility alias used by older consumers/tests
RedisPubSub = RedisStreamsClient
from services.redis import messages
from services.redis import streams as config
from services.redis.messages import QueryTask, QueryResponse

__all__ = [
    # Client
    "RedisPubSub",
    # Config/Streams
    "config",
    # Messages
    "messages",
    "QueryTask",
    "QueryResponse",
]
