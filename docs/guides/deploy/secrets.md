# Secrets Management

This guide covers managing secrets securely for the Agentic System.

## Overview

Secrets include:

- API keys (OpenAI, Anthropic)
- Database credentials (Supabase)
- OAuth tokens (Gmail)
- JWT secrets

## Local Development

### .env File

```bash
# .env (never commit!)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-here
OPENAI_API_KEY=sk-your-openai-api-key
GMAIL_REFRESH_TOKEN=your-refresh-token
```

### .gitignore

```gitignore
# Secrets
.env
.env.local
.env.*.local
*.pem
*.key
secrets/
```

### Loading Secrets

```python
from dotenv import load_dotenv
import os

load_dotenv()  # Load .env file

supabase_url = os.environ["SUPABASE_URL"]
```

## Production: AWS

### AWS Secrets Manager

Store secrets:

```bash
aws secretsmanager create-secret \
  --name agentic/production \
  --secret-string '{
    "SUPABASE_URL": "https://...",
    "SUPABASE_ANON_KEY": "eyJ...",
    "OPENAI_API_KEY": "sk-..."
  }'
```

### External Secrets Operator

```yaml
# k8s/aws-secrets-manager/external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: agentic-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: agentic-secrets
    creationPolicy: Owner
  data:
    - secretKey: SUPABASE_URL
      remoteRef:
        key: agentic/production
        property: SUPABASE_URL
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: agentic/production
        property: OPENAI_API_KEY
```

## Production: Azure

### Azure Key Vault

Store secrets:

```bash
az keyvault secret set \
  --vault-name agentic-vault \
  --name supabase-url \
  --value "https://..."

az keyvault secret set \
  --vault-name agentic-vault \
  --name openai-api-key \
  --value "sk-..."
```

### External Secrets Operator

```yaml
# k8s/azure-keyvault/external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: agentic-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: azure-keyvault
    kind: SecretStore
  target:
    name: agentic-secrets
  data:
    - secretKey: SUPABASE_URL
      remoteRef:
        key: supabase-url
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: openai-api-key
```

## GitHub Actions

### Repository Secrets

```bash
# Set via GitHub CLI
gh secret set SUPABASE_URL --body "https://..."
gh secret set OPENAI_API_KEY --body "sk-..."
```

### Using in Workflows

```yaml
jobs:
  deploy:
    steps:
      - name: Deploy
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          ./deploy.sh
```

### Environment-Specific Secrets

```yaml
jobs:
  deploy:
    environment: production # Uses production secrets
    steps:
      - name: Deploy
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
```

## Rotation

### API Key Rotation

1. Generate new key in provider dashboard
2. Update secret in storage (Secrets Manager, Key Vault)
3. Restart services to pick up new secret
4. Verify functionality
5. Revoke old key

### Automated Rotation

```yaml
# AWS Secrets Manager rotation
aws secretsmanager rotate-secret \
--secret-id agentic/production \
--rotation-lambda-arn arn:aws:lambda:...
```

## Best Practices

### Do

- ✅ Use secret managers in production
- ✅ Rotate secrets regularly
- ✅ Use different secrets per environment
- ✅ Audit secret access
- ✅ Encrypt secrets at rest

### Don't

- ❌ Commit secrets to git
- ❌ Log secrets
- ❌ Share secrets via chat/email
- ❌ Use production secrets in development
- ❌ Hardcode secrets in code

## Validation

### Check Secrets Loaded

```python
import os

required = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_JWT_SECRET",
    "OPENAI_API_KEY"
]

missing = [k for k in required if not os.environ.get(k)]
if missing:
    raise ValueError(f"Missing secrets: {missing}")
```

### Test Connections

```python
# Validate at startup
from services.persistence.supabase_adapter import SupabaseAdapter
from services.redis.client import get_redis_client

def validate_connections():
    # Test Redis
    redis = get_redis_client()
    assert redis.ping()

    # Test Supabase
    adapter = SupabaseAdapter(role="agent_reader")
    adapter.query("clients", {}, limit=1)

    print("All connections valid")
```

## Related

- [Environment Variables](../../reference/config/env-vars.md)
- [Docker Deployment](docker.md)
- [Kubernetes Deployment](kubernetes.md)
