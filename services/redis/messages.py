"""Message schemas for Redis pub/sub communication."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class QueryTask:
	"""Task envelope for RAG queries."""
	task_id: str
	table: str
	filters: Optional[Dict[str, Any]] = None
	columns: Optional[List[str]] = None
	limit: Optional[int] = None
	offset: Optional[int] = None
	order_by: Optional[str] = None
	descending: bool = True

	@classmethod
	def create(cls, table: str, **kwargs) -> "QueryTask":
		return cls(task_id=str(uuid.uuid4()), table=table, **kwargs)

	def to_dict(self) -> Dict[str, Any]:
		return asdict(self)


@dataclass
class QueryResponse:
	"""Response envelope from RAG agent."""
	task_id: str
	success: bool
	records: List[Dict[str, Any]]
	metadata: Dict[str, Any]
	error: Optional[str] = None

	def to_dict(self) -> Dict[str, Any]:
		return asdict(self)


__all__ = ["QueryTask", "QueryResponse"]
