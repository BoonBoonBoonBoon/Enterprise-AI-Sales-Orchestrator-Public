"""Secrets Management Integration for Azure Key Vault and AWS Secrets Manager.

This module provides a unified interface for loading secrets from various providers:
- Azure Key Vault
- AWS Secrets Manager
- Environment variables (fallback for local dev)

Usage:
    from agent.utils.secrets import get_secret, init_secrets_manager
    
    # Initialize the secrets manager (call once at app startup)
    init_secrets_manager(provider="azure")  # or "aws" or "env"
    
    # Get secrets anywhere in your application
    api_key = get_secret("OPENAI_API_KEY")
    redis_url = get_secret("REDIS_URL")

Environment Variables:
    SECRETS_PROVIDER: azure | aws | env (default: env)
    
    For Azure Key Vault:
        AZURE_KEY_VAULT_NAME: Name of the Key Vault
        AZURE_TENANT_ID: Azure AD tenant ID (optional, uses DefaultAzureCredential)
        AZURE_CLIENT_ID: Service principal client ID (optional)
        AZURE_CLIENT_SECRET: Service principal secret (optional)
    
    For AWS Secrets Manager:
        AWS_REGION: AWS region (e.g., us-east-1)
        AWS_SECRET_NAME: Name of the secret containing all app secrets as JSON
        AWS_ACCESS_KEY_ID: AWS access key (optional, uses IAM role if on EC2/ECS)
        AWS_SECRET_ACCESS_KEY: AWS secret key (optional)

Security Notes:
    - Never log raw secrets
    - Rotate credentials every 90 days
    - Use managed identities (Azure) or IAM roles (AWS) in production
    - Keep fallback .env file for local development only
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


class SecretsProvider(ABC):
    """Abstract base class for secrets providers."""
    
    @abstractmethod
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret by key."""
        pass
    
    @abstractmethod
    def get_all_secrets(self) -> Dict[str, str]:
        """Retrieve all secrets as a dictionary."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is accessible."""
        pass


class EnvSecretsProvider(SecretsProvider):
    """Environment variable secrets provider (fallback for local dev)."""
    
    def __init__(self):
        self.name = "Environment Variables"
        # Try to load .env file if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from environment variables."""
        return os.getenv(key, default)
    
    def get_all_secrets(self) -> Dict[str, str]:
        """Return all environment variables (filtered for known secrets)."""
        secret_keys = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "REDIS_URL",
            "REDIS_PASSWORD",
            "DATABASE_URL",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
        ]
        return {k: v for k, v in os.environ.items() if k in secret_keys}
    
    def health_check(self) -> bool:
        """Always returns True for env provider."""
        return True


class AzureKeyVaultProvider(SecretsProvider):
    """Azure Key Vault secrets provider."""
    
    def __init__(self):
        self.name = "Azure Key Vault"
        self._client = None
        self._cache: Dict[str, str] = {}
        
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
            
            vault_name = os.getenv("AZURE_KEY_VAULT_NAME")
            if not vault_name:
                raise ValueError("AZURE_KEY_VAULT_NAME environment variable not set")
            
            vault_url = f"https://{vault_name}.vault.azure.net"
            
            # Use DefaultAzureCredential (supports managed identity, service principal, CLI, etc.)
            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=vault_url, credential=credential)
            
            print(f"[SecretsManager] Azure Key Vault initialized: {vault_name}")
            
        except ImportError:
            raise ImportError(
                "Azure Key Vault dependencies not installed. "
                "Run: pip install azure-keyvault-secrets azure-identity"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Azure Key Vault: {e}")
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from Azure Key Vault."""
        # Check cache first
        if key in self._cache:
            return self._cache[key]
        
        try:
            # Azure Key Vault doesn't allow underscores in secret names
            # Convert OPENAI_API_KEY -> OPENAI-API-KEY
            vault_key = key.replace("_", "-")
            
            secret = self._client.get_secret(vault_key)
            value = secret.value
            
            # Cache the result
            self._cache[key] = value
            return value
            
        except Exception as e:
            print(f"[SecretsManager] WARNING: Failed to get secret '{key}' from Azure Key Vault: {e}")
            return default
    
    def get_all_secrets(self) -> Dict[str, str]:
        """Retrieve all secrets from Azure Key Vault."""
        secrets = {}
        try:
            for secret_properties in self._client.list_properties_of_secrets():
                if secret_properties.enabled:
                    name = secret_properties.name
                    # Convert back to underscore format
                    key = name.replace("-", "_")
                    value = self.get_secret(key)
                    if value:
                        secrets[key] = value
        except Exception as e:
            print(f"[SecretsManager] WARNING: Failed to list secrets from Azure Key Vault: {e}")
        
        return secrets
    
    def health_check(self) -> bool:
        """Check if Azure Key Vault is accessible."""
        try:
            # Try to list secrets (doesn't retrieve values)
            list(self._client.list_properties_of_secrets(max_results=1))
            return True
        except Exception:
            return False


class AWSSecretsProvider(SecretsProvider):
    """AWS Secrets Manager provider."""
    
    def __init__(self):
        self.name = "AWS Secrets Manager"
        self._client = None
        self._cache: Dict[str, str] = {}
        self._secret_name = os.getenv("AWS_SECRET_NAME", "agentic-system/prod")
        
        try:
            import boto3
            
            region = os.getenv("AWS_REGION", "us-east-1")
            
            # Create Secrets Manager client (uses IAM role if on EC2/ECS)
            self._client = boto3.client(
                service_name='secretsmanager',
                region_name=region
            )
            
            print(f"[SecretsManager] AWS Secrets Manager initialized: {self._secret_name} (region: {region})")
            
        except ImportError:
            raise ImportError(
                "AWS Secrets Manager dependencies not installed. "
                "Run: pip install boto3"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize AWS Secrets Manager: {e}")
    
    def _load_all_secrets(self) -> Dict[str, str]:
        """Load all secrets from AWS Secrets Manager (stored as JSON)."""
        if self._cache:
            return self._cache
        
        try:
            response = self._client.get_secret_value(SecretId=self._secret_name)
            
            # Parse the JSON secret string
            if 'SecretString' in response:
                secrets = json.loads(response['SecretString'])
                self._cache = secrets
                return secrets
            else:
                # Binary secrets not supported in this implementation
                print(f"[SecretsManager] WARNING: Binary secrets not supported")
                return {}
                
        except Exception as e:
            print(f"[SecretsManager] WARNING: Failed to load secrets from AWS: {e}")
            return {}
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from AWS Secrets Manager."""
        secrets = self._load_all_secrets()
        return secrets.get(key, default)
    
    def get_all_secrets(self) -> Dict[str, str]:
        """Retrieve all secrets from AWS Secrets Manager."""
        return self._load_all_secrets()
    
    def health_check(self) -> bool:
        """Check if AWS Secrets Manager is accessible."""
        try:
            self._client.describe_secret(SecretId=self._secret_name)
            return True
        except Exception:
            return False


# Global secrets manager instance
_secrets_manager: Optional[SecretsProvider] = None


def init_secrets_manager(
    provider: Optional[str] = None,
    fallback_to_env: bool = True
) -> SecretsProvider:
    """Initialize the secrets manager with the specified provider.
    
    Args:
        provider: One of "azure", "aws", or "env" (default: from SECRETS_PROVIDER env var)
        fallback_to_env: If True, fall back to environment variables if provider fails
    
    Returns:
        The initialized secrets provider
    
    Raises:
        RuntimeError: If provider initialization fails and fallback_to_env is False
    """
    global _secrets_manager
    
    if provider is None:
        provider = os.getenv("SECRETS_PROVIDER", "env").lower()
    
    print(f"[SecretsManager] Initializing with provider: {provider}")
    
    try:
        if provider == "azure":
            _secrets_manager = AzureKeyVaultProvider()
        elif provider == "aws":
            _secrets_manager = AWSSecretsProvider()
        elif provider == "env":
            _secrets_manager = EnvSecretsProvider()
        else:
            raise ValueError(f"Unknown secrets provider: {provider}")
        
        # Health check
        if not _secrets_manager.health_check():
            raise RuntimeError(f"Health check failed for provider: {provider}")
        
        print(f"[SecretsManager] Successfully initialized: {_secrets_manager.name}")
        return _secrets_manager
        
    except Exception as e:
        print(f"[SecretsManager] ERROR: Failed to initialize {provider}: {e}")
        
        if fallback_to_env and provider != "env":
            print(f"[SecretsManager] Falling back to environment variables")
            _secrets_manager = EnvSecretsProvider()
            return _secrets_manager
        else:
            raise


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret from the configured secrets manager.
    
    Args:
        key: Secret key (e.g., "OPENAI_API_KEY")
        default: Default value if secret not found
    
    Returns:
        Secret value or default
    
    Raises:
        RuntimeError: If secrets manager not initialized
    """
    global _secrets_manager
    
    if _secrets_manager is None:
        # Auto-initialize with default provider on first use
        init_secrets_manager()
    
    value = _secrets_manager.get_secret(key, default)
    
    # Redact in logs (only show first/last 4 chars if long enough)
    if value and len(value) > 8:
        redacted = f"{value[:4]}...{value[-4:]}"
    else:
        redacted = "****" if value else None
    
    print(f"[SecretsManager] Retrieved '{key}': {redacted}")
    return value


def get_all_secrets() -> Dict[str, str]:
    """Get all secrets from the configured secrets manager.
    
    Returns:
        Dictionary of all secrets
    
    Raises:
        RuntimeError: If secrets manager not initialized
    """
    global _secrets_manager
    
    if _secrets_manager is None:
        init_secrets_manager()
    
    return _secrets_manager.get_all_secrets()


def inject_secrets_into_env():
    """Inject secrets from the secrets manager into environment variables.
    
    This is useful for compatibility with code that expects environment variables.
    Call this once at application startup after initializing the secrets manager.
    """
    secrets = get_all_secrets()
    
    for key, value in secrets.items():
        if key not in os.environ:  # Don't override existing env vars
            os.environ[key] = value
    
    print(f"[SecretsManager] Injected {len(secrets)} secrets into environment")


def health_check() -> bool:
    """Check if the secrets manager is healthy and accessible.
    
    Returns:
        True if healthy, False otherwise
    """
    global _secrets_manager
    
    if _secrets_manager is None:
        try:
            init_secrets_manager()
        except Exception:
            return False
    
    return _secrets_manager.health_check()


# Auto-initialize on import if SECRETS_PROVIDER is set
if os.getenv("SECRETS_PROVIDER"):
    try:
        init_secrets_manager(fallback_to_env=True)
        inject_secrets_into_env()
    except Exception as e:
        print(f"[SecretsManager] WARNING: Auto-initialization failed: {e}")
        print(f"[SecretsManager] Call init_secrets_manager() explicitly to retry")


__all__ = [
    "init_secrets_manager",
    "get_secret",
    "get_all_secrets",
    "inject_secrets_into_env",
    "health_check",
    "SecretsProvider",
    "EnvSecretsProvider",
    "AzureKeyVaultProvider",
    "AWSSecretsProvider",
]
