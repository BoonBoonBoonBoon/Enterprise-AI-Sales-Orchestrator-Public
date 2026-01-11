"""
Checkpointing Backends: Pluggable state persistence implementations

All checkpointers implement ICheckpointer interface.
Choose based on use case:
- RedisCheckpointer: Fast, temporary (24h TTL) - staging/short-lived tasks
- S3Checkpointer: Persistent, audit trail (30d+) - production/long-term
- PostgreSQLCheckpointer: Queryable, analytics - reporting/analysis
"""

from .redis_checkpointer import RedisCheckpointer
from .s3_checkpointer import S3Checkpointer
from .postgres_checkpointer import PostgreSQLCheckpointer

__all__ = [
    "RedisCheckpointer",
    "S3Checkpointer",
    "PostgreSQLCheckpointer",
]
