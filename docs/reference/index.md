# Reference

Comprehensive reference documentation for APIs, configuration, database schemas, and CLI tools.

## Reference Categories

<div class="grid cards" markdown>

- :material-api:{ .lg .middle } **API**

  ***

  Message formats, stream conventions, and payload schemas.

  - [Envelope Schema](api/envelope.md)
  - [Stream Keys](api/streams.md)
  - [Agent Payloads](api/payloads.md)

- :material-cog:{ .lg .middle } **Configuration**

  ***

  Environment variables, harness options, and settings.

  - [Environment Variables](config/env-vars.md)
  - [Harness Options](config/harness.md)
  - [Settings](config/settings.md)

- :material-database:{ .lg .middle } **Database**

  ***

  Supabase schema, RLS policies, and migrations.

  - [Schema Reference](database/schema.md)
  - [RLS Policies](database/rls.md)
  - [Migrations](database/migrations.md)

- :material-console:{ .lg .middle } **CLI**

  ***

  Scripts, consumer commands, and utilities.

  - [Scripts Reference](cli/scripts.md)
  - [Consumer Commands](cli/consumers.md)

</div>

## Quick Lookup

### Stream Keys

```
{tenant}:manager:tasks           # Manager input
{tenant}:manager:results         # Manager output
{tenant}:orchestrators:{name}:tasks    # Orchestrator input
{tenant}:orchestrators:{name}:results  # Orchestrator output
{tenant}:agents:{name}:tasks     # Agent input
{tenant}:agents:{name}:results   # Agent output
```

### Essential Environment Variables

| Variable              | Required | Purpose                |
| --------------------- | -------- | ---------------------- |
| `SUPABASE_URL`        | ✅       | Supabase project URL   |
| `SUPABASE_ANON_KEY`   | ✅       | Supabase anonymous key |
| `SUPABASE_JWT_SECRET` | ✅       | JWT signing secret     |
| `REDIS_URL`           | ✅       | Redis connection URL   |
| `OPENAI_API_KEY`      | ✅       | OpenAI API key for LLM |

See [Environment Variables](config/env-vars.md) for complete list.

### Database Tables

| Table           | FK Dependencies              | Purpose             |
| --------------- | ---------------------------- | ------------------- |
| `clients`       | —                            | Top-level tenant    |
| `campaigns`     | `clients.id`                 | Marketing campaigns |
| `leads`         | `clients.id`, `campaigns.id` | Qualified leads     |
| `staging_leads` | —                            | Pre-qualified leads |
| `conversations` | `leads.id`                   | Lead conversations  |
| `messages`      | `conversations.id`           | Individual messages |

See [Schema Reference](database/schema.md) for complete schema.

### Common Scripts

```powershell
# Generate mock leads
& ".venv/Scripts/python.exe" -m scripts.startup.generate_mock_leads

# Check stream health
& ".venv/Scripts/python.exe" -m scripts.monitoring.stream_status

# Run diagnostics
& ".venv/Scripts/python.exe" -m scripts.diagnostics.system_check
```

See [Scripts Reference](cli/scripts.md) for all available scripts.
