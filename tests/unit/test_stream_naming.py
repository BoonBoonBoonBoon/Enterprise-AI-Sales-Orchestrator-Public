"""Unit tests for canonical Redis stream naming.

These tests must NOT connect to external Redis instances.
They validate the single source of truth in services.redis.stream_registry.
"""

from services.redis.stream_registry import get_registry, Tier, StreamType


def test_registry_uses_hierarchical_orchestrator_streams():
    registry = get_registry()
    tenant_id = "test-tenant"

    leads_tasks = registry.get_stream_key(Tier.ORCHESTRATOR, "leads", StreamType.TASKS, tenant_id)
    leads_results = registry.get_stream_key(Tier.ORCHESTRATOR, "leads", StreamType.RESULTS, tenant_id)
    outbound_tasks = registry.get_stream_key(Tier.ORCHESTRATOR, "outbound", StreamType.TASKS, tenant_id)
    outbound_results = registry.get_stream_key(Tier.ORCHESTRATOR, "outbound", StreamType.RESULTS, tenant_id)

    assert leads_tasks == f"{tenant_id}:orchestrators:leads:tasks"
    assert leads_results == f"{tenant_id}:orchestrators:leads:results"
    assert outbound_tasks == f"{tenant_id}:orchestrators:outbound:tasks"
    assert outbound_results == f"{tenant_id}:orchestrators:outbound:results"


def test_manager_downstream_matches_registry_contract():
    registry = get_registry()
    tenant_id = "test-tenant"

    downstream = registry.get_downstream_streams(Tier.MANAGER, "manager", StreamType.TASKS, tenant_id)
    assert f"{tenant_id}:orchestrators:leads:tasks" in downstream
    assert f"{tenant_id}:orchestrators:outbound:tasks" in downstream


def test_no_flat_tier2_streams_in_registry():
    registry = get_registry()
    tenant_id = "test-tenant"
    all_streams = registry.get_all_streams(tenant_id).values()

    forbidden = {
        f"{tenant_id}:leads:tasks",
        f"{tenant_id}:leads:results",
        f"{tenant_id}:outreach:tasks",
        f"{tenant_id}:outreach:results",
    }

    assert forbidden.isdisjoint(set(all_streams))
