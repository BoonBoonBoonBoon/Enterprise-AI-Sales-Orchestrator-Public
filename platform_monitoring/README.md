platform_monitoring
===================

Purpose
-------
Small, central package that exposes lightweight observability helpers used by
orchestrators and agents. Keep instrumentation here so the rest of the codebase
imports a single stable API (`platform_monitoring.log_event`,
`platform_monitoring.prometheus_metric`). Replace or extend these helpers with
real exporters (structured logging, telemetry backend, Prometheus client) as
needed.

Public API
----------
- log_event(event: Dict[str, Any]) -> None
	- Log a generic monitoring event. Prefer structured dicts with keys like
		`run_id`, `flow`, `status`, `error`.
- prometheus_metric(name: str, value: float, labels: Dict[str, str] | None)
	- Lightweight placeholder for exporting numeric metrics. Swap with a
		Prometheus client when you deploy metrics.

Usage examples
--------------
1) Basic import:

	 from platform_monitoring import log_event, prometheus_metric

	 log_event({"run_id": "lead-sync-20250909T...", "status": "started"})
	 prometheus_metric("lead_sync_duration_seconds", 1.23, {"flow": "lead_sync"})

2) Wire into an orchestrator (CampaignManager example):

	 # at run start
	 log_event({"run_id": run_id, "flow": flow, "status": "started"})

	 # on success
	 log_event({"run_id": run_id, "flow": flow, "status": "finished", "records": len(records)})

	 # on failure
	 log_event({"run_id": run_id, "flow": flow, "status": "failed", "error": str(exc)})

Configuration and extension
---------------------------
- The package currently uses the standard Python logging logger named
	`platform_monitoring`. Configure it via logging handlers in your application
	(file, console, or structured JSON handlers) or replace `prometheus_metric`
	with an implementation that uses the Prometheus client library.
- To add tracing or export to a telemetry backend, add new helper functions
	here (e.g., `trace_span`, `export_trace`) and re-export them from the
	package `__init__.py`.

Testing
-------
- Unit tests should import the functions from `platform_monitoring` and can
	assert that calls do not raise. If you replace the implementation with a
	client-backed exporter, consider adding simple integration tests that mock
	the exporter.

Troubleshooting
---------------
- If imports fail after moving this package, search for references to
	`agent.high_level_agents.platform_monitoring` and update them to import from
	`platform_monitoring` instead (the high-level re-export already forwards the
	helpers).
- Configure the `platform_monitoring` logger to see emitted events. Example:

	import logging
	logging.basicConfig(level=logging.INFO)

Contributing
------------
- Keep this package minimal. Add adapters for your telemetry platform rather
	than adding platform-specific logic in orchestrators.

License / Attribution
---------------------
This repository's existing license applies.
