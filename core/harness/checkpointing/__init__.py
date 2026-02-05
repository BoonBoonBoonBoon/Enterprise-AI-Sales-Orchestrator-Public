"""
Checkpointing Backends: Pluggable state persistence implementations

All checkpointers implement ICheckpointer interface.
Choose based on use case:
- RedisCheckpointer: Fast, temporary (24h TTL) - staging/short-lived tasks
- S3Checkpointer: Persistent, audit trail (30d+) - production/long-term
- PostgreSQLCheckpointer: Queryable, analytics - reporting/analysis

Imports are lazy to avoid pulling in optional heavy dependencies (boto3, psycopg2)
at module load time. Use the helper or import directly from the submodule.
"""

from typing import TYPE_CHECKING

# Lazy imports - only resolve when actually accessed
if TYPE_CHECKING:
    from .redis_checkpointer import RedisCheckpointer
    from .s3_checkpointer import S3Checkpointer
    from .postgres_checkpointer import PostgreSQLCheckpointer


def __getattr__(name: str):
    """Lazy loader for checkpointer classes."""
    if name == "RedisCheckpointer":
        from .redis_checkpointer import RedisCheckpointer
        return RedisCheckpointer
    if name == "S3Checkpointer":
        from .s3_checkpointer import S3Checkpointer
        return S3Checkpointer
    if name == "PostgreSQLCheckpointer":
        from .postgres_checkpointer import PostgreSQLCheckpointer
        return PostgreSQLCheckpointer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "RedisCheckpointer",
    "S3Checkpointer",
    "PostgreSQLCheckpointer",
]
