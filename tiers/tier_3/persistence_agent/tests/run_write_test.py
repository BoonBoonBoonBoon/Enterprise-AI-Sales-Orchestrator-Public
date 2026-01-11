"""
Pre-flight check and run script for Persistence Agent write test.

This script:
1. Checks environment variables
2. Verifies Redis/Supabase connectivity
3. Provides instructions for starting the consumer
4. Runs the write test
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

def check_environment():
    """Check required environment variables."""
    print("="*80)
    print("ENVIRONMENT CHECK")
    print("="*80)
    
    required_vars = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "REDIS_URL": os.getenv("REDIS_URL"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")
    }
    
    all_ok = True
    for var, value in required_vars.items():
        status = "✅" if value else "❌"
        print(f"{status} {var}: {'SET' if value else 'MISSING'}")
        if not value:
            all_ok = False
    
    print("="*80)
    return all_ok

def check_redis_connection():
    """Check Redis connectivity."""
    print("\n" + "="*80)
    print("REDIS CONNECTION CHECK")
    print("="*80)
    
    try:
        import redis
        redis_url = os.getenv("REDIS_URL")
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        print("✅ Redis connection successful")
        
        # Check if tasks stream exists
        stream_name = "agentic-dev:agents:persistence:tasks"
        exists = client.exists(stream_name)
        print(f"{'✅' if exists else '⚠️'} Stream '{stream_name}' {'exists' if exists else 'does not exist'}")
        
        client.close()
        print("="*80)
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("="*80)
        return False

def check_supabase_connection():
    """Check Supabase connectivity."""
    print("\n" + "="*80)
    print("SUPABASE CONNECTION CHECK")
    print("="*80)
    
    try:
        from supabase import create_client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        client = create_client(supabase_url, supabase_key)
        
        # Try a simple query on leads table (we know this exists)
        result = client.table("leads").select("id").limit(1).execute()
        print("✅ Supabase connection successful")
        print(f"✅ Leads table accessible")
        print("="*80)
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("="*80)
        return False

def print_consumer_instructions():
    """Print instructions for starting the consumer."""
    print("\n" + "="*80)
    print("PERSISTENCE AGENT CONSUMER")
    print("="*80)
    print("⚠️  IMPORTANT: The Persistence Agent consumer must be running!")
    print("\nTo start the consumer in a separate terminal:")
    print("\n  1. Open a new PowerShell terminal")
    print("  2. Activate virtual environment:")
    print("     .\\.venv\\Scripts\\Activate.ps1")
    print("\n  3. Start the consumer:")
    print("     python -m tiers.tier_3.persistence_agent.consumer")
    print("\n  4. Keep it running while the test executes")
    print("="*80)

def main():
    """Run pre-flight checks."""
    print("\n🚀 PRE-FLIGHT CHECK FOR PERSISTENCE AGENT WRITE TEST\n")
    
    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please set missing variables in .env file.")
        sys.exit(1)
    
    # Check Redis
    if not check_redis_connection():
        print("\n❌ Redis connection failed. Please check REDIS_URL in .env file.")
        sys.exit(1)
    
    # Check Supabase
    if not check_supabase_connection():
        print("\n❌ Supabase connection failed. Please check credentials in .env file.")
        sys.exit(1)
    
    # Print consumer instructions
    print_consumer_instructions()
    
    # Ask user if consumer is running
    print("\n" + "="*80)
    response = input("\nIs the Persistence Agent consumer running? (y/n): ").strip().lower()
    
    if response != 'y':
        print("\n⚠️  Please start the consumer first, then run this script again.")
        sys.exit(0)
    
    # Run the test
    print("\n" + "="*80)
    print("RUNNING WRITE TEST")
    print("="*80)
    print("\nExecuting: python -m pytest tiers/tier_3/persistence_agent/tests/test_write_all_tables.py::TestWriteAllTables::test_full_workflow -v -s\n")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tiers/tier_3/persistence_agent/tests/test_write_all_tables.py::TestWriteAllTables::test_full_workflow", "-v", "-s"],
        cwd=os.getcwd()
    )
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
