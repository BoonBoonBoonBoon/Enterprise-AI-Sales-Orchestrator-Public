# External APIs Service

Third-party API integrations for data enrichment and CRM sync.

## Status

🚧 **Skeleton** — Implementation pending

## Planned Components

| Directory   | Purpose                                         |
| ----------- | ----------------------------------------------- |
| `adapters/` | API client adapters (HubSpot, Salesforce, etc.) |
| `models/`   | Pydantic response models                        |
| `tools/`    | LangChain tool wrappers for agent use           |

## Planned Integrations

| Service    | Type       | Status     |
| ---------- | ---------- | ---------- |
| HubSpot    | CRM        | 🚧 Planned |
| Salesforce | CRM        | 🚧 Planned |
| Apollo     | Enrichment | 🚧 Planned |
| Clearbit   | Enrichment | 🚧 Planned |
| LinkedIn   | Social     | 🚧 Planned |

## Planned Usage

```python
from services.external_apis.adapters import HubSpotAdapter

hubspot = HubSpotAdapter(api_key="...")

# Sync lead to CRM
hubspot.create_contact({
    "email": "lead@example.com",
    "firstname": "John",
    "lastname": "Doe"
})

# Enrichment
from services.external_apis.adapters import ApolloAdapter

apollo = ApolloAdapter()
enriched = apollo.enrich_person("john@acme.com")
```

## Roadmap

1. Implement CRM adapters (HubSpot, Salesforce)
2. Build enrichment integrations
3. Create LangChain tool wrappers
4. Add rate limiting and caching

## See Also

- [RAG Agent](../../tiers/tier_3/rag_agent/README.md) — Uses enrichment data
- [Leads Orchestrator](../../tiers/tier_2/leads_orchestrator/README.md) — Triggers enrichment
