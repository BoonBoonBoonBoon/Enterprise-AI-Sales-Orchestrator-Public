# Quick Setup: Copywriter LLM Integration

## Install Dependencies

```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install new LLM packages
pip install openai>=1.0.0
pip install anthropic>=0.7.0

# Or install all requirements
pip install -r requirements.txt
```

## Configure API Keys

### Option 1: Environment Variables (Recommended)

**Windows PowerShell:**
```powershell
# For OpenAI
$env:OPENAI_API_KEY = "sk-..."
$env:LLM_PROVIDER = "openai"

# For Anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:LLM_PROVIDER = "anthropic"

# For placeholder (testing)
$env:LLM_PROVIDER = "placeholder"
```

**Windows CMD:**
```cmd
set OPENAI_API_KEY=sk-...
set LLM_PROVIDER=openai
```

### Option 2: .env File

Create/update `.env` file in project root:
```bash
# Choose one provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# OR
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Lead context enrichment
ENABLE_LEAD_CONTEXT_ENRICHMENT=1
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJh...
PERSIST_ALLOWED_TABLES=leads,lead_interactions
```

## Test the Integration

### 1. Run Demo Script

```powershell
# Start Redis (if not running)
docker run -d -p 6379:6379 redis:latest

# Test with OpenAI
python examples/copywriter_llm_demo.py --provider openai

# Test with Anthropic
python examples/copywriter_llm_demo.py --provider anthropic

# Test placeholder (no API calls)
python examples/copywriter_llm_demo.py --provider placeholder
```

### 2. Start Worker

```powershell
# Start copywriter worker
python -m agent.operational_agents.copywriter.worker

# Should see:
# [CopyWorker 12345] OpenAI client initialized
# [CopyWorker 12345] Lead context enrichment enabled
# [CopyWorker 12345] listening on stream copy:tasks in group copy-workers...
```

### 3. Send Test Task

```python
# Send a test task (Python script or Jupyter notebook)
from agent.tools.redis.client import RedisPubSub
from agent.utils.typed_envelope import task
import json

envelope = task(
    payload={
        "lead_data": {
            "id": "test-lead",
            "first_name": "John",
            "email": "john@example.com",
            "company_name": "Acme Corp"
        },
        "campaign_context": {
            "campaign_id": "test-campaign",
            "sequence_step": 1,
            "product_name": "AI Platform"
        },
        "instructions": {
            "template": "cold_email",
            "tone": "professional",
            "word_count": 150
        }
    },
    source="test",
    campaign_id="test-campaign",
    lead_id="test-lead"
)

redis = RedisPubSub()
redis.xadd("copy:tasks", {
    "metadata": json.dumps(envelope.metadata.model_dump()),
    "payload": json.dumps(envelope.payload),
    "status": envelope.status.value
})

print("✓ Task sent! Check copy:results stream for output")
```

## Verify Results

```python
# Check results stream
redis = RedisPubSub()
results = redis.xread({"copy:results": "0"}, count=1)

for stream, messages in results:
    for msg_id, fields in messages:
        print(json.loads(fields[b"payload"]))
```

Expected output:
```json
{
  "content": {
    "subject": "Quick question about Acme Corp",
    "body": "Hi John,\n\n...",
    "metadata": {
      "model": "gpt-4o-mini",
      "tokens": 547,
      "prompt_tokens": 412,
      "completion_tokens": 135
    }
  },
  "lead_id": "test-lead",
  "campaign_id": "test-campaign"
}
```

## Troubleshooting

### "ImportError: No module named openai"
```bash
pip install openai>=1.0.0
```

### "WARNING: OPENAI_API_KEY not set"
```powershell
$env:OPENAI_API_KEY = "sk-..."
```

### "Rate limit exceeded"
- Wait a few seconds between requests
- Upgrade your OpenAI/Anthropic plan
- Use multiple API keys with round-robin

### Worker not processing tasks
1. Check Redis is running: `docker ps`
2. Check worker logs for errors
3. Verify stream exists: `redis-cli XINFO STREAM copy:tasks`

## Next Steps

1. ✅ Install dependencies
2. ✅ Configure API keys
3. ✅ Test with demo script
4. ✅ Start worker
5. ✅ Send test task
6. ✅ Verify results

**Full Documentation:** See `docs/COPYWRITER_LLM_INTEGRATION.md`
