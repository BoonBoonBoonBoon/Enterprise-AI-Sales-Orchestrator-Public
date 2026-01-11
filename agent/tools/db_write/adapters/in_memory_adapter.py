from typing import Dict, Any, List, Optional
from agent.tools.db_write.interface import DBWriteAdapter


class InMemoryDBAdapter:
    """Very small in-memory DB adapter for tests.

    Stores tables in a dict of list-of-records and assigns simple integer ids.
    """

    def __init__(self):
        self._tables: Dict[str, List[Dict[str, Any]]] = {}
        self._counters: Dict[str, int] = {}

    def _ensure_table(self, table: str):
        if table not in self._tables:
            self._tables[table] = []
            self._counters[table] = 1

    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_table(table)
        rid = str(self._counters[table])
        self._counters[table] += 1
        stored = {**record, "id": rid}
        self._tables[table].append(stored)
        return stored

    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for r in records:
            out.append(self.write(table, r))
        return out

    def get_table(self, table: str) -> List[Dict[str, Any]]:
        return list(self._tables.get(table, []))

    def upsert(self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None) -> Dict[str, Any]:
        """Upsert a record into the in-memory table using `on_conflict` keys for dedupe.

        If `on_conflict` is None, behaves like `write` (always inserts).
        Stores rows: Keeps tables as lists and assigns incremental id strings.
        Upsert logic: Finds a row matching all on_conflict keys, merges and updates it, or inserts if none match.
        """
        self._ensure_table(table)
        if not on_conflict:
            return self.write(table, record)

        # find existing row matching all conflict keys
        for idx, row in enumerate(self._tables[table]):
            matched = True
            for key in on_conflict:
                if row.get(key) != record.get(key):
                    matched = False
                    break
            if matched:
                # update existing record
                updated = {**row, **record}
                # keep id if present
                if 'id' not in updated:
                    updated['id'] = row.get('id')
                self._tables[table][idx] = updated
                return updated

        # not found -> insert
        return self.write(table, record)


__all__ = ["InMemoryDBAdapter"]
