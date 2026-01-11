"""
Quota Management: Rate limiting and quota enforcement

All quota managers implement IQuotaManager interface.
Choose based on deployment:
- RedisTokenBucket: Distributed, production (multiple workers)
- InMemoryQuota: Simple, development (single process)
"""

from .redis_token_bucket import RedisTokenBucket
from .in_memory_quota import InMemoryQuota

__all__ = [
    "RedisTokenBucket",
    "InMemoryQuota",
]
