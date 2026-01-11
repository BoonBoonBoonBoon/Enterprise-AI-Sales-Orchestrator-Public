from agent.tools.persistence.adapters.in_memory_adapter import InMemoryAdapter
from agent.tools.persistence.service import PersistenceService, ReadOnlyPersistenceFacade
from agent.tools.persistence.exceptions import PersistencePermissionError, TableNotAllowedError
from agent.config.persistence_config import get_write_allowlist, get_read_allowlist


def build_service(allowed=None):
	adapter = InMemoryAdapter()
	# Backward-compatible single allowlist path (acts for both read & write)
	return PersistenceService(adapter, allowed_tables=allowed or {"leads", "messages"})


def test_write_and_read_round_trip():
	svc = build_service()
	row = svc.write("leads", {"email": "a@example.com", "status": "new"})
	fetched = svc.read("leads", row["id"])
	assert fetched == row


def test_query_with_filters_and_projection_and_order():
	svc = build_service()
	svc.batch_write(
		"messages",
		[
			{"body": "first", "seq": 1},
			{"body": "second", "seq": 2},
			{"body": "third", "seq": 3},
		],
	)
	rows = svc.query(
		"messages",
		filters={"body": "second"},
		select=["body", "seq"],
		order_by="seq",
		limit=1,
	)
	assert len(rows) == 1
	assert rows[0]["body"] == "second"
	assert set(rows[0].keys()) == {"body", "seq"}


def test_upsert_on_conflict():
	svc = build_service()
	first = svc.upsert("leads", {"email": "dup@example.com", "status": "new"}, on_conflict=["email"])
	second = svc.upsert(
		"leads", {"email": "dup@example.com", "status": "qualified"}, on_conflict=["email"]
	)
	assert first["id"] == second["id"]
	assert second["status"] == "qualified"


def test_disallowed_table_raises():
	svc = build_service(allowed={"leads"})
	try:
		svc.write("messages", {"body": "x"})
	except TableNotAllowedError:
		pass
	else:  # pragma: no cover - ensure failure clear
		raise AssertionError("Expected PermissionError for disallowed table")


def test_read_only_facade_blocks_writes_and_allows_reads():
	svc = build_service(allowed={"leads"})
	row = svc.write("leads", {"email": "ro@example.com"})
	ro = ReadOnlyPersistenceFacade(svc)
	# read works
	fetched = ro.read("leads", row["id"])
	assert fetched["email"] == "ro@example.com"
	# write blocked
	try:
		ro.write("leads", {"email": "blocked@example.com"})
	except PersistencePermissionError:
		pass
	else:  # pragma: no cover
		raise AssertionError("Expected PersistencePermissionError from read-only facade")


def test_write_restrictions_clients_campaigns():
	"""Ensure policy forbids writes to governance tables but allows reads."""
	# Simulate a full policy service with computed write allowlist
	adapter = InMemoryAdapter()
	write_allow = get_write_allowlist()
	read_allow = get_read_allowlist()
	# Use dual-allowlist constructor
	svc = PersistenceService(
		adapter,
		read_allowlist=read_allow,
		write_allowlist=write_allow,
	)
	assert "clients" in read_allow and "campaigns" in read_allow  # readable
	assert "clients" not in write_allow and "campaigns" not in write_allow  # not writable
	# Attempting to write should raise
	for table in ["clients", "campaigns"]:
		try:
			svc.write(table, {"dummy": True})
		except TableNotAllowedError:
			pass
		else:  # pragma: no cover
			raise AssertionError(f"Expected TableNotAllowedError for write to {table}")
	# Reading should work (will create a row via direct adapter bypass to simulate existing data)
	# Insert via adapter to avoid policy violation
	adapter.write("clients", {"name": "Acme"})
	rows = svc.query("clients")
	assert rows and rows[0]["name"] == "Acme"


def test_readonly_facade_hardening():
	"""Even if underlying service has write rights, facade must block writes."""
	adapter = InMemoryAdapter()
	svc = PersistenceService(
		adapter,
		read_allowlist=["leads"],
		write_allowlist=["leads"],
	)
	# underlying write works
	svc.write("leads", {"email": "x@example.com"})
	ro = ReadOnlyPersistenceFacade(svc)
	# facade write blocked
	try:
		ro.write("leads", {"email": "blocked@example.com"})
	except PersistencePermissionError:
		pass
	else:  # pragma: no cover
		raise AssertionError("Facade allowed a write unexpectedly")

