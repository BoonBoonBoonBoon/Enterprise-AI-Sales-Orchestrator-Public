# Secrets Management Integration Guide

## Overview

This system supports three secrets management strategies:

1. **Environment Variables** (`.env` file) - Local development
2. **Azure Key Vault** - Production (Azure deployments)
3. **AWS Secrets Manager** - Production (AWS deployments)

The secrets manager automatically loads credentials at startup and injects them into the application environment.

---

## Quick Start (Local Development)

### 1. Use Environment Variables (Default)

```bash
# Copy example file
cp .env.example .env

# Edit .env with your credentials
# SECRETS_PROVIDER=env (default)
# OPENAI_API_KEY=your-openai-api-key
# REDIS_URL=redis://...
```

No code changes needed! The system automatically loads from `.env` when `SECRETS_PROVIDER=env` (or unset).

---

## Production Setup

### Option 1: Azure Key Vault

#### Prerequisites

```bash
pip install azure-keyvault-secrets azure-identity
```

#### Configuration

**1. Create Azure Key Vault:**

```bash
# Using Azure CLI
az keyvault create \
  --name agentic-system-prod \
  --resource-group agentic-rg \
  --location eastus
```

**2. Add Secrets:**

```bash
# Azure Key Vault uses hyphens instead of underscores
az keyvault secret set --vault-name agentic-system-prod --name OPENAI-API-KEY --value "your-openai-api-key"
az keyvault secret set --vault-name agentic-system-prod --name REDIS-URL --value "redis://..."
az keyvault secret set --vault-name agentic-system-prod --name SUPABASE-URL --value "https://..."
az keyvault secret set --vault-name agentic-system-prod --name SUPABASE-KEY --value "eyJ..."
```

**3. Grant Access:**

**Option A: Managed Identity (Recommended)**

```bash
# Enable managed identity on your App Service/VM
az webapp identity assign --name agentic-app --resource-group agentic-rg

# Get the principal ID
PRINCIPAL_ID=$(az webapp identity show --name agentic-app --resource-group agentic-rg --query principalId -o tsv)

# Grant Key Vault access
az keyvault set-policy \
  --name agentic-system-prod \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

**Option B: Service Principal**

```bash
# Create service principal
az ad sp create-for-rbac --name agentic-system-sp

# Note: Save client ID, tenant ID, and client secret

# Grant access
az keyvault set-policy \
  --name agentic-system-prod \
  --spn <client-id> \
  --secret-permissions get list
```

**4. Set Environment Variables:**

```bash
# Managed Identity (no credentials needed)
export SECRETS_PROVIDER=azure
export AZURE_KEY_VAULT_NAME=agentic-system-prod

# OR Service Principal
export SECRETS_PROVIDER=azure
export AZURE_KEY_VAULT_NAME=agentic-system-prod
export AZURE_TENANT_ID=<tenant-id>
export AZURE_CLIENT_ID=<client-id>
export AZURE_CLIENT_SECRET=<client-secret>
```

---

### Option 2: AWS Secrets Manager

#### Prerequisites

```bash
pip install boto3
```

#### Configuration

**1. Create Secret in AWS Secrets Manager:**

```bash
# Store all secrets as JSON
aws secretsmanager create-secret \
  --name agentic-system/prod \
  --secret-string '{
    "OPENAI_API_KEY": "sk-...",
    "REDIS_URL": "redis://...",
    "SUPABASE_URL": "https://...",
    "SUPABASE_KEY": "eyJ..."
  }' \
  --region us-east-1
```

**2. Grant Access:**

**Option A: IAM Role (Recommended for EC2/ECS)**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:agentic-system/prod-*"
    }
  ]
}
```

**Option B: IAM User**

```bash
# Create IAM user and attach policy above
# Note: Access key ID and secret access key
```

**3. Set Environment Variables:**

```bash
# IAM Role (no credentials needed on EC2/ECS)
export SECRETS_PROVIDER=aws
export AWS_REGION=us-east-1
export AWS_SECRET_NAME=agentic-system/prod

# OR IAM User
export SECRETS_PROVIDER=aws
export AWS_REGION=us-east-1
export AWS_SECRET_NAME=agentic-system/prod
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
```

---

## Application Integration

### Automatic Initialization (Recommended)

The secrets manager auto-initializes when `SECRETS_PROVIDER` is set:

```python
# No code changes needed!
# Secrets are automatically loaded and injected into os.environ
import os

api_key = os.getenv("OPENAI_API_KEY")  # Works seamlessly
```

### Manual Initialization

```python
from agent.utils.secrets import init_secrets_manager, get_secret

# Initialize at app startup
init_secrets_manager(provider="azure")  # or "aws" or "env"

# Get secrets anywhere
api_key = get_secret("OPENAI_API_KEY")
redis_url = get_secret("REDIS_URL")
```

### Inject Into Environment

```python
from agent.utils.secrets import inject_secrets_into_env

# Load all secrets into os.environ
inject_secrets_into_env()

# Now all code using os.getenv() works
import os
api_key = os.getenv("OPENAI_API_KEY")
```

---

## Docker Configuration

### Environment Variables Method

```yaml
# docker-compose.yml
services:
  worker:
    image: agentic/worker:latest
    environment:
      SECRETS_PROVIDER: env
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      REDIS_URL: ${REDIS_URL}
    env_file:
      - .env # Load from .env file
```

### Azure Key Vault Method

```yaml
# docker-compose.azure.yml
services:
  worker:
    image: agentic/worker:latest
    environment:
      SECRETS_PROVIDER: azure
      AZURE_KEY_VAULT_NAME: agentic-system-prod
      # Use managed identity (no credentials needed)
```

### AWS Secrets Manager Method

```yaml
# docker-compose.aws.yml
services:
  worker:
    image: agentic/worker:latest
    environment:
      SECRETS_PROVIDER: aws
      AWS_REGION: us-east-1
      AWS_SECRET_NAME: agentic-system/prod
      # Use IAM role (no credentials needed on ECS)
```

---

## Kubernetes Deployment

### Using Azure Key Vault CSI Driver

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: agentic-secrets
spec:
  provider: azure
  parameters:
    keyvaultName: "agentic-system-prod"
    tenantId: "YOUR_TENANT_ID"
    objects: |
      array:
        - |
          objectName: OPENAI-API-KEY
          objectType: secret
        - |
          objectName: REDIS-URL
          objectType: secret
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: copywriter-worker
spec:
  template:
    spec:
      containers:
        - name: worker
          image: agentic/worker:latest
          env:
            - name: SECRETS_PROVIDER
              value: "azure"
            - name: AZURE_KEY_VAULT_NAME
              value: "agentic-system-prod"
          volumeMounts:
            - name: secrets-store
              mountPath: "/mnt/secrets-store"
              readOnly: true
      volumes:
        - name: secrets-store
          csi:
            driver: secrets-store.csi.k8s.io
            readOnly: true
            volumeAttributes:
              secretProviderClass: "agentic-secrets"
```

### Using AWS Secrets Manager CSI Driver

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: agentic-secrets
spec:
  provider: aws
  parameters:
    objects: |
      - objectName: "agentic-system/prod"
        objectType: "secretsmanager"
```

---

## Security Best Practices

### 1. Never Commit Secrets

```bash
# Add to .gitignore
echo ".env" >> .gitignore

# Remove if already committed
git rm --cached .env
git commit -m "Remove secrets file"
```

### 2. Rotate Credentials Regularly

```bash
# Azure Key Vault
az keyvault secret set --vault-name agentic-system-prod --name OPENAI-API-KEY --value "sk-new-key"

# AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id agentic-system/prod \
  --secret-string '{"OPENAI_API_KEY": "sk-new-key"}'
```

### 3. Use Managed Identities

- **Azure:** Enable managed identity on App Service, VM, or AKS
- **AWS:** Use IAM roles for EC2, ECS, or EKS
- **Avoids:** Hardcoded credentials in environment variables

### 4. Audit Access

```bash
# Azure: Enable diagnostic logs
az monitor diagnostic-settings create \
  --resource /subscriptions/.../Microsoft.KeyVault/vaults/agentic-system-prod \
  --name audit-logs \
  --logs '[{"category": "AuditEvent", "enabled": true}]'

# AWS: Enable CloudTrail
aws cloudtrail create-trail \
  --name agentic-audit \
  --s3-bucket-name agentic-audit-logs
```

### 5. Principle of Least Privilege

Grant only required permissions:

- **Read-only** access to secrets
- **Specific resources** only (not all Key Vaults/Secrets)
- **Time-limited** credentials when possible

---

## Monitoring & Health Checks

### Health Check Endpoint

```python
from agent.utils.secrets import health_check

@app.get("/health/secrets")
def secrets_health():
    healthy = health_check()
    return {"healthy": healthy, "provider": os.getenv("SECRETS_PROVIDER")}
```

### Logs

The secrets manager logs all operations:

```
[SecretsManager] Initializing with provider: azure
[SecretsManager] Azure Key Vault initialized: agentic-system-prod
[SecretsManager] Successfully initialized: Azure Key Vault
[SecretsManager] Retrieved 'OPENAI_API_KEY': sk-p...y5oA
[SecretsManager] Injected 4 secrets into environment
```

**Note:** Only first/last 4 characters of secrets are logged (redacted).

---

## Troubleshooting

### Issue: "Azure Key Vault not accessible"

**Solution:**

1. Check managed identity is enabled
2. Verify Key Vault access policy
3. Ensure Key Vault name is correct
4. Check network firewall rules

```bash
# Test access with Azure CLI
az keyvault secret show --vault-name agentic-system-prod --name OPENAI-API-KEY
```

### Issue: "AWS Secrets Manager credentials not found"

**Solution:**

1. Check IAM role is attached to EC2/ECS
2. Verify IAM policy allows `secretsmanager:GetSecretValue`
3. Ensure AWS region is correct
4. Check secret name matches

```bash
# Test access with AWS CLI
aws secretsmanager get-secret-value --secret-id agentic-system/prod --region us-east-1
```

### Issue: "Secrets not loading"

**Solution:**

1. Check `SECRETS_PROVIDER` environment variable
2. Verify required dependencies installed
3. Check logs for initialization errors
4. Test with `SECRETS_PROVIDER=env` first

```python
# Manual diagnostic
from agent.utils.secrets import init_secrets_manager, health_check

try:
    manager = init_secrets_manager(provider="azure")
    print(f"Health check: {health_check()}")
except Exception as e:
    print(f"Error: {e}")
```

---

## Migration Guide

### From .env to Azure Key Vault

```bash
# 1. Read current .env secrets
source .env

# 2. Upload to Azure Key Vault
az keyvault secret set --vault-name agentic-system-prod --name OPENAI-API-KEY --value "$OPENAI_API_KEY"
az keyvault secret set --vault-name agentic-system-prod --name REDIS-URL --value "$REDIS_URL"
az keyvault secret set --vault-name agentic-system-prod --name SUPABASE-URL --value "$SUPABASE_URL"
az keyvault secret set --vault-name agentic-system-prod --name SUPABASE-KEY --value "$SUPABASE_KEY"

# 3. Update environment
export SECRETS_PROVIDER=azure
export AZURE_KEY_VAULT_NAME=agentic-system-prod
unset OPENAI_API_KEY REDIS_URL SUPABASE_URL SUPABASE_KEY

# 4. Test application
python -m agent.operational_agents.copywriter.worker
```

### From .env to AWS Secrets Manager

```bash
# 1. Create JSON from .env
cat .env | grep -v '^#' | jq -R -s 'split("\n") | map(select(length > 0) | split("=")) | map({(.[0]): .[1]}) | add'

# 2. Upload to AWS
aws secretsmanager create-secret \
  --name agentic-system/prod \
  --secret-string "$(cat secrets.json)" \
  --region us-east-1

# 3. Update environment
export SECRETS_PROVIDER=aws
export AWS_REGION=us-east-1
export AWS_SECRET_NAME=agentic-system/prod
unset OPENAI_API_KEY REDIS_URL SUPABASE_URL SUPABASE_KEY

# 4. Test application
python -m agent.operational_agents.copywriter.worker
```

---

## API Reference

### `init_secrets_manager(provider, fallback_to_env=True)`

Initialize the secrets manager.

**Parameters:**

- `provider`: `"azure"` | `"aws"` | `"env"`
- `fallback_to_env`: If True, fall back to .env if provider fails

**Returns:** `SecretsProvider` instance

**Raises:** `RuntimeError` if initialization fails

### `get_secret(key, default=None)`

Get a single secret value.

**Parameters:**

- `key`: Secret name (e.g., `"OPENAI_API_KEY"`)
- `default`: Default value if not found

**Returns:** Secret value (str) or default

### `get_all_secrets()`

Get all secrets as a dictionary.

**Returns:** `Dict[str, str]`

### `inject_secrets_into_env()`

Load all secrets into `os.environ`.

**Returns:** None

### `health_check()`

Check if secrets provider is accessible.

**Returns:** `bool`

---

## Cost Considerations

### Azure Key Vault

- **Standard Tier:** $0.03 per 10,000 operations
- **Premium Tier (HSM):** $1.00/hour per key
- **Typical Cost:** ~$5/month for production workload

### AWS Secrets Manager

- **Storage:** $0.40 per secret per month
- **API Calls:** $0.05 per 10,000 calls
- **Typical Cost:** ~$5/month for 10 secrets

### Environment Variables

- **Cost:** Free
- **Security:** Lower (suitable for dev only)

---

## Next Steps

1. **Development:** Continue using `.env` files
2. **Staging:** Set up Azure Key Vault or AWS Secrets Manager
3. **Production:** Enable managed identities and audit logging
4. **Monitoring:** Add secrets health checks to monitoring dashboard
5. **Compliance:** Document credential rotation schedule (90 days)

---

## Related Documentation

- [Azure Key Vault Documentation](https://docs.microsoft.com/en-us/azure/key-vault/)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Architecture Overview](../../architecture/overview.md) - Security overview
- [Docker Reference](../../getting-started/docker-reference.md) - Production deployment basics

---

**Status:** ✅ Production Ready

**Last Updated:** October 27, 2025
