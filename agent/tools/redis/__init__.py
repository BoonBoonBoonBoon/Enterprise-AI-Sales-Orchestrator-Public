"""Redis tooling package: pub/sub client and message schemas.

Modules
-------
- client: RedisPubSub wrapper (URL or host/port envs, namespaced channels)
- messages: QueryTask / QueryResponse dataclasses

Intended use
------------
- Orchestrators publish query tasks to a channel and wait for responses.
- RAG workers subscribe to requests and publish responses after executing.
"""

from .client import RedisPubSub  # noqa: F401
