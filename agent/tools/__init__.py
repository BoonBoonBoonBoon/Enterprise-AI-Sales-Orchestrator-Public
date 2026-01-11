"""Minimal tools package init.

Avoid importing legacy helpers that pull in deprecated modules (e.g.,
`supabase_tools` which expects `config.settings`). Keep this file light so
`import agent.tools.persistence.service` does not trigger unrelated imports.
"""

try:  # optional exposure for convenience; don't fail package import
	from .persistence.service import PersistenceService  # type: ignore
except Exception:
	PersistenceService = None  # type: ignore

__all__ = ["PersistenceService"]

