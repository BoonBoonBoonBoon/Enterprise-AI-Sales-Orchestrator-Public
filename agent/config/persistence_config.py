"""Central configuration for persistence layer allowlists and settings.

Updated Policy (2025-10):
---------------------------------
* READ: All known business tables are readable by default (expands RAG / analytics power).
* WRITE: Restricted — cannot write to read-only governance tables: ``clients`` and ``campaigns``.

Environment Override Precedence:
* PERSIST_WRITE_TABLES  -> full explicit write allowlist (comma separated)
* PERSIST_WRITE_DENY    -> subtractive deny list applied to default (ignored if WRITE_TABLES set)
* PERSIST_READ_TABLES   -> full explicit read allowlist (comma separated)

This file is the single source of truth; services/agents must not hard‑code table lists.
"""

from __future__ import annotations

import os
from typing import List

# Enumerate all known tables (schema-derived + retained legacy 'inquiries')
ALL_TABLES: List[str] = [
    "campaigns",
    "clients",
    "conversations",
    "leads",
    "messages",
    "sequences",
    "staging_leads",
    "inquiries",  # present in earlier design (keep for backward compatibility)
]

# Default deny list for writes (governed / reference tables)
DEFAULT_WRITE_DENY: List[str] = [
    "clients",
    "campaigns",
]

# Default write allowlist is all tables minus the deny list
DEFAULT_WRITE_TABLES: List[str] = [t for t in ALL_TABLES if t not in DEFAULT_WRITE_DENY]

# Reads now cover everything; keep empty list for legacy export compatibility
DEFAULT_READ_ADDITIONS: List[str] = []

def _env_list(var: str) -> List[str] | None:
    raw = os.getenv(var)
    if not raw:
        return None
    return [p.strip() for p in raw.split(",") if p.strip()]


def get_write_allowlist() -> List[str]:
    """Return tables allowed for WRITE operations.

    Precedence:
      1. PERSIST_WRITE_TABLES (explicit full override)
      2. DEFAULT_WRITE_TABLES minus any PERSIST_WRITE_DENY entries
    """
    explicit = _env_list("PERSIST_WRITE_TABLES")
    if explicit:
        return explicit
    deny_extra = set(_env_list("PERSIST_WRITE_DENY") or [])
    return [t for t in DEFAULT_WRITE_TABLES if t not in deny_extra]


def get_read_allowlist() -> List[str]:
    """Return tables allowed for READ operations.

    Defaults to ALL_TABLES unless PERSIST_READ_TABLES is provided.
    """
    explicit = _env_list("PERSIST_READ_TABLES")
    if explicit:
        return explicit
    return list(ALL_TABLES)


__all__ = [
    "ALL_TABLES",
    "get_write_allowlist",
    "get_read_allowlist",
    "DEFAULT_WRITE_TABLES",
    "DEFAULT_WRITE_DENY",
    "DEFAULT_READ_ADDITIONS",
]
