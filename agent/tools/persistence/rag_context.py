"""RAG context assembly utilities.

Builds a structured retrieval augmented generation (RAG) context by pulling
recent / relevant rows from multiple operational tables via a PersistenceService-
compatible object (must expose `query`).

This module intentionally keeps logic simple and relies on upstream allowlists
to ensure only permitted tables are accessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


class SupportsQuery(Protocol):  # Minimal protocol to avoid import cycles
	def query(
		self,
		table: str,
		filters: Optional[Dict[str, Any]] = None,
		limit: Optional[int] = None,
		order_by: Optional[str] = None,
		descending: bool = False,
		select: Optional[List[str]] = None,
	) -> List[Dict[str, Any]]: ...  # noqa: E704


@dataclass
class RAGContext:
	clients: List[Dict[str, Any]] = field(default_factory=list)
	leads: List[Dict[str, Any]] = field(default_factory=list)
	campaigns: List[Dict[str, Any]] = field(default_factory=list)
	conversations: List[Dict[str, Any]] = field(default_factory=list)
	messages: List[Dict[str, Any]] = field(default_factory=list)

	def to_prompt(self, include_empty: bool = False) -> str:
		sections = []
		def block(title: str, rows: List[Dict[str, Any]]):
			if not rows and not include_empty:
				return
			sections.append(f"### {title}\n")
			if not rows:
				sections.append("(none)\n\n")
				return
			for r in rows:
				# simple key=val pairs sorted by key for stability
				kv = " | ".join(f"{k}={r[k]!r}" for k in sorted(r.keys()))
				sections.append(f"- {kv}\n")
			sections.append("\n")

		block("Clients", self.clients)
		block("Leads", self.leads)
		block("Campaigns", self.campaigns)
		block("Conversations", self.conversations)
		block("Messages", self.messages)
		return "".join(sections).strip()


def build_rag_context(
	persistence: SupportsQuery,
	*,
	client_filters: Optional[Dict[str, Any]] = None,
	lead_filters: Optional[Dict[str, Any]] = None,
	campaign_filters: Optional[Dict[str, Any]] = None,
	conversation_filters: Optional[Dict[str, Any]] = None,
	message_filters: Optional[Dict[str, Any]] = None,
	limits: Optional[Dict[str, int]] = None,
	order_by: Optional[str] = None,
	descending: bool = True,
) -> RAGContext:
	"""Collect multi-entity context for downstream LLM prompting.

	limits: per-table limit overrides, e.g. {"messages": 25}
	order_by: if provided, applied to each table (commonly a timestamp column)
	"""
	limits = limits or {}

	def fetch(table: str, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
		return persistence.query(
			table,
			filters=filters,
			limit=limits.get(table),
			order_by=order_by,
			descending=descending,
		)

	ctx = RAGContext(
		clients=fetch("clients", client_filters),
		leads=fetch("leads", lead_filters),
		campaigns=fetch("campaigns", campaign_filters),
		conversations=fetch("conversations", conversation_filters),
		messages=fetch("messages", message_filters),
	)
	return ctx


__all__ = ["RAGContext", "build_rag_context"]

