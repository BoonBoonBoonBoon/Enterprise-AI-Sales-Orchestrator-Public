"""Persistence-related tools (migrated from agent.tools).

This package groups together low-level persistence helpers such as
db-write adapters and (legacy) Supabase utilities. New code should
prefer the higher-level `PersistenceService` and facades in
`services.persistence` where possible.
"""

from typing import TYPE_CHECKING

try:
	from services.persistence.service import PersistenceService  # type: ignore
except Exception:  # pragma: no cover - optional convenience import
	PersistenceService = None  # type: ignore

if TYPE_CHECKING:  # for IDEs/type checkers
	from .supabase_tools import SupabaseClient  # noqa: F401

__all__ = [
	"PersistenceService",
]
