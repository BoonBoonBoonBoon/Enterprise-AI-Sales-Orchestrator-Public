"""Adapters for the persistence service.

This module exports all available persistence adapters.
"""

from services.persistence.adapters.in_memory_adapter import InMemoryAdapter
from services.persistence.adapters.supabase_adapter import SupabaseAdapter

__all__ = ["InMemoryAdapter", "SupabaseAdapter"]
