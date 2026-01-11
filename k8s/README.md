# Kubernetes Secrets Management Configuration
#
# This directory contains Kubernetes manifests for deploying the agentic system
# with secrets management integration (Azure Key Vault or AWS Secrets Manager)

## Directory Structure

```
k8s/
├── README.md                           # This file
├── azure-keyvault/
│   ├── secret-provider-class.yaml     # Azure Key Vault CSI driver config
│   └── deployment.yaml                # Deployment using Azure secrets
├── aws-secrets-manager/
│   ├── secret-provider-class.yaml     # AWS Secrets Manager CSI driver config
│   └── deployment.yaml                # Deployment using AWS secrets
└── base/
    ├── namespace.yaml                  # Namespace definition
    ├── configmap.yaml                  # Non-secret configuration
    └── service.yaml                    # Service definitions
```

---

## Prerequisites

### For Azure Key Vault

1. **Install CSI Driver:**
```bash
helm repo add csi-secrets-store-provider-azure https://azure.github.io/secrets-store-csi-driver-provider-azure/charts
helm install csi-secrets-store-provider-azure/csi-secrets-store-provider-azure --generate-name
```

2. **Enable Workload Identity (Recommended):**
```bash
az aks update \
  --resource-group agentic-rg \
  --name agentic-cluster \
  --enable-oidc-issuer \
  --enable-workload-identity
```

3. **Create Managed Identity:**
```bash
az identity create \
  --name agentic-workload-identity \
  --resource-group agentic-rg

# Get client ID
CLIENT_ID=$(az identity show --name agentic-workload-identity --resource-group agentic-rg --query clientId -o tsv)
```

4. **Grant Key Vault Access:**
```bash
az keyvault set-policy \
  --name agentic-system-prod \
  --object-id $CLIENT_ID \
  --secret-permissions get list
```

### For AWS Secrets Manager

1. **Install CSI Driver:**
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/secrets-store-csi-driver/main/deploy/rbac-secretproviderclass.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/secrets-store-csi-driver/main/deploy/csidriver.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/secrets-store-csi-driver/main/deploy/secrets-store.csi.x-k8s.io_secretproviderclasses.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/secrets-store-csi-driver/main/deploy/secrets-store.csi.x-k8s.io_secretproviderclasspodstatuses.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/secrets-store-csi-driver/main/deploy/secrets-store-csi-driver.yaml

kubectl apply -f https://raw.githubusercontent.com/aws/secrets-store-csi-driver-provider-aws/main/deployment/aws-provider-installer.yaml
```

2. **Create IAM Role (IRSA):**
```bash
eksctl create iamserviceaccount \
  --name agentic-worker \
  --namespace agentic-system \
  --cluster agentic-cluster \
  --attach-policy-arn arn:aws:iam::ACCOUNT_ID:policy/AgenticSecretsManagerPolicy \
  --approve
```

3. **IAM Policy:**
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

---

## Deployment

### Azure Key Vault

```bash
# 1. Create namespace
kubectl apply -f k8s/base/namespace.yaml

# 2. Update secret-provider-class.yaml with your Key Vault name
# Edit: k8s/azure-keyvault/secret-provider-class.yaml

# 3. Apply Azure configuration
kubectl apply -f k8s/azure-keyvault/

# 4. Verify
kubectl get secretproviderclass -n agentic-system
kubectl get pods -n agentic-system
```

### AWS Secrets Manager

```bash
# 1. Create namespace
kubectl apply -f k8s/base/namespace.yaml

# 2. Update secret-provider-class.yaml with your secret name
# Edit: k8s/aws-secrets-manager/secret-provider-class.yaml

# 3. Apply AWS configuration
kubectl apply -f k8s/aws-secrets-manager/

# 4. Verify
kubectl get secretproviderclass -n agentic-system
kubectl get pods -n agentic-system
```

---

## Verification

### Check Secrets Mounted

```bash
# Get pod name
POD=$(kubectl get pods -n agentic-system -l app=copywriter-worker -o jsonpath='{.items[0].metadata.name}')

# Check mounted secrets
kubectl exec -it $POD -n agentic-system -- ls -la /mnt/secrets-store

# Check logs
kubectl logs $POD -n agentic-system | grep SecretsManager
```

Expected output:
```
[SecretsManager] Initializing with provider: azure
[SecretsManager] Azure Key Vault initialized: agentic-system-prod
[SecretsManager] Successfully initialized: Azure Key Vault
```

### Health Check

```bash
# Port forward to health server
kubectl port-forward -n agentic-system svc/health-server 8080:8080

# Check health
curl http://localhost:8080/health/secrets
```

---

## Troubleshooting

### Azure: "Failed to get secret"

**Check identity:**
```bash
kubectl describe pod <pod-name> -n agentic-system | grep azure.workload.identity
```

**Check Key Vault access:**
```bash
az keyvault secret show --vault-name agentic-system-prod --name OPENAI-API-KEY
```

### AWS: "Permission denied"

**Check service account:**
```bash
kubectl describe serviceaccount agentic-worker -n agentic-system
```

**Check IAM role:**
```bash
aws sts assume-role --role-arn arn:aws:iam::ACCOUNT_ID:role/agentic-worker-role --role-session-name test
```

### Secrets not loading

**Check CSI driver:**
```bash
kubectl get csidriver
kubectl logs -n kube-system -l app=secrets-store-csi-driver
```

**Check provider:**
```bash
# Azure
kubectl logs -n kube-system -l app=csi-secrets-store-provider-azure

# AWS
kubectl logs -n kube-system -l app=csi-secrets-store-provider-aws
```

---

## Security Best Practices

1. **Use Workload Identity (Azure) or IRSA (AWS)**
   - Eliminates need for static credentials
   - Automatic credential rotation
   - Fine-grained IAM policies

2. **Principle of Least Privilege**
   - Grant only `get` and `list` permissions
   - Restrict to specific secrets/Key Vault
   - Use separate identities per workload

3. **Audit Logging**
   - Enable Key Vault diagnostic logs (Azure)
   - Enable CloudTrail (AWS)
   - Monitor access patterns

4. **Network Policies**
   - Restrict egress to Key Vault/Secrets Manager endpoints
   - Use private endpoints when possible

5. **Rotation**
   - Rotate secrets every 90 days
   - Update Key Vault/Secrets Manager
   - Pods automatically pick up new values on restart

---

## Next Steps

1. Review and customize YAML files for your environment
2. Set up monitoring for secrets access
3. Configure audit logging
4. Test secret rotation procedure
5. Document runbooks for common scenarios

---

## Related Documentation

- [Secrets Management Guide](../docs/SECRETS_MANAGEMENT.md)
- [Azure Key Vault CSI Driver](https://azure.github.io/secrets-store-csi-driver-provider-azure/)
- [AWS Secrets Manager CSI Driver](https://github.com/aws/secrets-store-csi-driver-provider-aws)
