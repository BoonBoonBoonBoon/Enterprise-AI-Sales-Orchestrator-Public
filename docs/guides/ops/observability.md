# Observability (Grafana Stack)

This system uses a self-hosted Grafana stack:

- **Prometheus** for metrics
- **Loki** for logs
- **Tempo** for traces
- **Grafana** for dashboards and exploration

For the full deployment and configuration walkthrough, see:

- [deployment/OBSERVABILITY.md](https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/deployment/OBSERVABILITY.md)

## Quick Start

From the repo root:

```powershell
# Start the observability stack
docker compose -f deployment/docker-compose.observability.yml up -d
```

Endpoints:

- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Loki: http://localhost:3100
- Tempo: http://localhost:3200

## Metrics Endpoints

Each process exposes `/metrics` and `/health` on a component-specific port.

| Tier   | Component             | Port |
| ------ | --------------------- | ---- |
| Tier 1 | Manager               | 8000 |
| Tier 2 | Leads Orchestrator    | 8010 |
| Tier 2 | Outreach Orchestrator | 8011 |
| Tier 2 | Inbound Orchestrator  | 8012 |
| Tier 2 | Control Orchestrator  | 8013 |
| Tier 2 | Audit Orchestrator    | 8014 |
| Tier 3 | Persistence Agent     | 8020 |
| Tier 3 | RAG Agent             | 8021 |
| Tier 3 | Copywriter Agent      | 8022 |
| Tier 3 | Channel Sequencer     | 8023 |
| Tier 3 | Classifier Agent      | 8024 |
| Tier 3 | Scheduler Agent       | 8025 |

Override ports with environment variables:

```powershell
# Component-specific override
$env:METRICS_PORT_LEADS_ORCHESTRATOR = "9010"

# Global fallback
$env:METRICS_PORT = "8080"
```

## Related

- [Monitoring](monitoring.md)
- [deployment/OBSERVABILITY.md](https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/deployment/OBSERVABILITY.md)
