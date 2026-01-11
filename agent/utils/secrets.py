"""Compatibility wrapper for legacy imports.

Re-exports the public API from core.utils.secrets so legacy scripts/tests using
`agent.utils.secrets` continue to work without path changes.
"""
from core.utils.secrets import *  # noqa: F401,F403
