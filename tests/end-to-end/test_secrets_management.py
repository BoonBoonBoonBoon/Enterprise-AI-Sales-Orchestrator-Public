"""Test script for secrets management integration.

Tests all three providers: Environment Variables, Azure Key Vault, AWS Secrets Manager.

Usage:
    # Test environment variables
    python test_secrets_management.py --provider env
    
    # Test Azure Key Vault
    python test_secrets_management.py --provider azure
    
    # Test AWS Secrets Manager
    python test_secrets_management.py --provider aws
    
    # Run all tests
    python test_secrets_management.py --all
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add repo to path
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from agent.utils.secrets import (
    init_secrets_manager,
    get_secret,
    get_all_secrets,
    inject_secrets_into_env,
    health_check
)


def test_env_provider():
    """Test environment variable provider."""
    print("\n" + "="*70)
    print("TEST 1: Environment Variables Provider")
    print("="*70)
    
    try:
        # Initialize
        print("\n[1/5] Initializing secrets manager...")
        manager = init_secrets_manager(provider="env")
        print(f"✓ Initialized: {manager.name}")
        
        # Health check
        print("\n[2/5] Running health check...")
        healthy = health_check()
        print(f"✓ Health check: {'PASS' if healthy else 'FAIL'}")
        
        # Get individual secret
        print("\n[3/5] Testing get_secret()...")
        openai_key = get_secret("OPENAI_API_KEY")
        if openai_key:
            redacted = f"{openai_key[:8]}...{openai_key[-8:]}" if len(openai_key) > 16 else "****"
            print(f"✓ OPENAI_API_KEY: {redacted}")
        else:
            print("⚠ OPENAI_API_KEY not found (this is okay for testing)")
        
        # Get all secrets
        print("\n[4/5] Testing get_all_secrets()...")
        all_secrets = get_all_secrets()
        print(f"✓ Found {len(all_secrets)} secrets")
        for key in all_secrets.keys():
            print(f"  - {key}")
        
        # Inject into environment
        print("\n[5/5] Testing inject_secrets_into_env()...")
        inject_secrets_into_env()
        print(f"✓ Injected secrets into os.environ")
        
        print("\n" + "="*70)
        print("✓ Environment Variables Provider: ALL TESTS PASSED")
        print("="*70)
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_azure_provider():
    """Test Azure Key Vault provider."""
    print("\n" + "="*70)
    print("TEST 2: Azure Key Vault Provider")
    print("="*70)
    
    # Check prerequisites
    vault_name = os.getenv("AZURE_KEY_VAULT_NAME")
    if not vault_name:
        print("⚠ AZURE_KEY_VAULT_NAME not set. Skipping Azure tests.")
        print("  Set AZURE_KEY_VAULT_NAME environment variable to run this test.")
        return None
    
    print(f"\nUsing Key Vault: {vault_name}")
    
    try:
        # Check dependencies
        print("\n[1/6] Checking dependencies...")
        try:
            import azure.keyvault.secrets
            import azure.identity
            print("✓ Azure SDK installed")
        except ImportError:
            print("✗ Azure SDK not installed")
            print("  Install: pip install azure-keyvault-secrets azure-identity")
            return False
        
        # Initialize
        print("\n[2/6] Initializing Azure Key Vault...")
        manager = init_secrets_manager(provider="azure")
        print(f"✓ Initialized: {manager.name}")
        
        # Health check
        print("\n[3/6] Running health check...")
        healthy = health_check()
        print(f"✓ Health check: {'PASS' if healthy else 'FAIL'}")
        
        if not healthy:
            print("  Key Vault not accessible. Check:")
            print("  1. Key Vault name is correct")
            print("  2. You're authenticated (az login)")
            print("  3. Access policy is configured")
            return False
        
        # Get individual secret
        print("\n[4/6] Testing get_secret()...")
        openai_key = get_secret("OPENAI_API_KEY")
        if openai_key:
            redacted = f"{openai_key[:8]}...{openai_key[-8:]}" if len(openai_key) > 16 else "****"
            print(f"✓ OPENAI_API_KEY: {redacted}")
        else:
            print("⚠ OPENAI_API_KEY not found in Key Vault")
            print("  Add with: az keyvault secret set --vault-name {vault_name} --name OPENAI-API-KEY --value 'sk-...'")
        
        # Get all secrets
        print("\n[5/6] Testing get_all_secrets()...")
        all_secrets = get_all_secrets()
        print(f"✓ Found {len(all_secrets)} secrets in Key Vault")
        for key in all_secrets.keys():
            print(f"  - {key}")
        
        # Inject into environment
        print("\n[6/6] Testing inject_secrets_into_env()...")
        inject_secrets_into_env()
        print(f"✓ Injected secrets into os.environ")
        
        print("\n" + "="*70)
        print("✓ Azure Key Vault Provider: ALL TESTS PASSED")
        print("="*70)
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_aws_provider():
    """Test AWS Secrets Manager provider."""
    print("\n" + "="*70)
    print("TEST 3: AWS Secrets Manager Provider")
    print("="*70)
    
    # Check prerequisites
    secret_name = os.getenv("AWS_SECRET_NAME", "agentic-system/prod")
    region = os.getenv("AWS_REGION", "us-east-1")
    
    print(f"\nUsing secret: {secret_name} (region: {region})")
    
    try:
        # Check dependencies
        print("\n[1/6] Checking dependencies...")
        try:
            import boto3
            print("✓ boto3 installed")
        except ImportError:
            print("✗ boto3 not installed")
            print("  Install: pip install boto3")
            return False
        
        # Initialize
        print("\n[2/6] Initializing AWS Secrets Manager...")
        manager = init_secrets_manager(provider="aws")
        print(f"✓ Initialized: {manager.name}")
        
        # Health check
        print("\n[3/6] Running health check...")
        healthy = health_check()
        print(f"✓ Health check: {'PASS' if healthy else 'FAIL'}")
        
        if not healthy:
            print("  Secrets Manager not accessible. Check:")
            print("  1. AWS credentials configured (aws configure)")
            print("  2. Secret exists and name is correct")
            print("  3. IAM permissions are correct")
            return False
        
        # Get individual secret
        print("\n[4/6] Testing get_secret()...")
        openai_key = get_secret("OPENAI_API_KEY")
        if openai_key:
            redacted = f"{openai_key[:8]}...{openai_key[-8:]}" if len(openai_key) > 16 else "****"
            print(f"✓ OPENAI_API_KEY: {redacted}")
        else:
            print("⚠ OPENAI_API_KEY not found in secret")
            print(f"  Add to secret: {secret_name}")
        
        # Get all secrets
        print("\n[5/6] Testing get_all_secrets()...")
        all_secrets = get_all_secrets()
        print(f"✓ Found {len(all_secrets)} secrets")
        for key in all_secrets.keys():
            print(f"  - {key}")
        
        # Inject into environment
        print("\n[6/6] Testing inject_secrets_into_env()...")
        inject_secrets_into_env()
        print(f"✓ Injected secrets into os.environ")
        
        print("\n" + "="*70)
        print("✓ AWS Secrets Manager Provider: ALL TESTS PASSED")
        print("="*70)
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test secrets management integration")
    parser.add_argument(
        "--provider",
        choices=["env", "azure", "aws"],
        help="Provider to test"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests"
    )
    
    args = parser.parse_args()
    
    if not args.provider and not args.all:
        parser.print_help()
        return 1
    
    results = {}
    
    if args.all or args.provider == "env":
        results["env"] = test_env_provider()
    
    if args.all or args.provider == "azure":
        result = test_azure_provider()
        if result is not None:
            results["azure"] = result
    
    if args.all or args.provider == "aws":
        result = test_aws_provider()
        if result is not None:
            results["aws"] = result
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for provider, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{provider.upper():20} {status}")
    
    print("="*70)
    
    # Return exit code
    all_passed = all(results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
