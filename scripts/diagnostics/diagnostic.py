#!/usr/bin/env python3
"""
Diagnostic script to check system status before running tests

Checks:
1. Redis connectivity
2. Environment variables
3. Python dependencies
4. Consumer requirements
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def check_redis():
    """Check Redis connectivity"""
    print_header("1. REDIS CONNECTIVITY")
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    print(f"REDIS_URL: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
    
    try:
        import redis
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        print("✅ Redis connection: OK\n")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}\n")
        return False

def check_environment():
    """Check required environment variables"""
    print_header("2. ENVIRONMENT VARIABLES")
    
    required_vars = {
        'OPENAI_API_KEY': '(OpenAI API key)',
        'REDIS_URL': '(Redis Cloud endpoint)',
        'TENANT_ID': '(default: agentic-dev)',
    }
    
    all_set = True
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if var in ['OPENAI_API_KEY']:
                display = f"{value[:20]}...***"
            elif var in ['REDIS_URL']:
                display = value.split('@')[-1] if '@' in value else value
            else:
                display = value
            print(f"✅ {var:20} = {display}")
        else:
            print(f"⚠️  {var:20} = (not set) {desc}")
            all_set = False
    
    if not os.getenv('OPENAI_API_KEY'):
        print("\n⚠️  OPENAI_API_KEY is required for consumers to run!")
    
    print()
    return all_set

def check_dependencies():
    """Check Python dependencies"""
    print_header("3. PYTHON DEPENDENCIES")
    
    required_packages = {
        'redis': 'Redis client',
        'deepagents': 'Deep Agents framework',
        'langchain': 'LangChain',
        'openai': 'OpenAI API client',
    }
    
    all_installed = True
    for package, description in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {package:20} ✓")
        except ImportError:
            print(f"❌ {package:20} NOT installed ({description})")
            all_installed = False
    
    print()
    return all_installed

def check_files():
    """Check required files exist"""
    print_header("4. REQUIRED FILES")
    
    required_files = {
        # Tier 1: Manager
        'agent/manager/manager_agent.py': 'Manager Agent (Tier 1)',
        'agent/manager/manager_agent_harness.py': 'Manager harness',
        'agent/manager/consumer.py': 'Manager consumer',
        'agent/manager/tools/delegation_tools.py': 'Delegation tools',
        'agent/manager/deep_agent_factory.py': 'Deep Agent factory',
        
        # Tier 2: Orchestrators
        'agent/orchestrators/leads_orchestrator/leads_orchestrator.py': 'Leads orchestrator',
        'agent/orchestrators/leads_orchestrator/leads_orchestrator_harness.py': 'Leads harness',
        'agent/orchestrators/leads_orchestrator/consumer.py': 'Leads consumer',
        'agent/orchestrators/outreach_orchestrator/outreach_orchestrator.py': 'Outreach orchestrator',
        'agent/orchestrators/outreach_orchestrator/outreach_orchestrator_harness.py': 'Outreach harness',
        'agent/orchestrators/outreach_orchestrator/consumer.py': 'Outreach consumer',
        
        # Startup & Utils
        'start_all_consumers.py': 'Startup script',
        'reset_consumer_groups.py': 'Consumer group reset utility',
    }
    
    all_exist = True
    for filepath, description in required_files.items():
        if os.path.exists(filepath):
            print(f"✅ {filepath}")
        else:
            print(f"❌ {filepath} (missing - {description})")
            all_exist = False
    
    print()
    return all_exist

def check_venv():
    """Check virtual environment"""
    print_header("5. VIRTUAL ENVIRONMENT")
    
    venv_python = '.venv/Scripts/python.exe'
    if os.path.exists(venv_python):
        print(f"✅ Virtual environment found: {venv_python}\n")
        return True
    else:
        print(f"❌ Virtual environment not found: {venv_python}\n")
        return False

def check_redis_streams():
    """Check Redis streams and consumer groups"""
    print_header("6. REDIS STREAMS & CONSUMER GROUPS")
    
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    tenant_id = os.getenv('TENANT_ID', 'agentic-dev')
    
    try:
        import redis
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        
        # Check streams
        streams = {
            f"{tenant_id}:manager:tasks": "Tier 1: Manager task queue",
            f"{tenant_id}:manager:results": "Tier 1: Manager results",
            f"{tenant_id}:leads:tasks": "Tier 2: Leads task queue",
            f"{tenant_id}:leads:results": "Tier 2: Leads results",
            f"{tenant_id}:outreach:tasks": "Tier 2: Outreach task queue",
            f"{tenant_id}:outreach:results": "Tier 2: Outreach results",
        }
        
        for stream, description in streams.items():
            try:
                length = client.xlen(stream)
                print(f"✅ {stream}: {length} messages ({description})")
                
                # Check consumer groups
                try:
                    groups = client.xinfo_groups(stream)
                    if groups:
                        for group in groups:
                            group_name = group.get('name', 'unknown')
                            consumers = group.get('consumers', 0)
                            pending = group.get('pending', 0)
                            print(f"   └─ Consumer group: {group_name} ({consumers} consumers, {pending} pending)")
                except:
                    pass
                    
            except redis.ResponseError:
                print(f"⚠️  {stream}: Not created yet ({description})")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Could not check streams: {e}\n")
        return False

def print_next_steps():
    """Print next steps"""
    print_header("NEXT STEPS")
    
    print("🎯 THREE-TIER ARCHITECTURE FLOW:\n")
    print("Tier 1 (Manager) → Tier 2 (Leads/Outreach) → Tier 3 (Operational Agents)\n")
    
    print("Option A: Test Manager → Orchestrators delegation:\n")
    print("Terminal 1 - Start consumers individually:")
    print("  # Manager consumer")
    print('  $env:OPENAI_API_KEY="your-key" ; $env:TENANT_ID="agentic-dev"')
    print("  python agent/manager/consumer.py\n")
    print("  # Leads consumer (separate terminal)")
    print("  python agent/orchestrators/leads_orchestrator/consumer.py\n")
    print("  # Outreach consumer (separate terminal)")
    print("  python agent/orchestrators/outreach_orchestrator/consumer.py\n")
    
    print("Terminal 2 - Send test task:")
    print("  python test_manager_orchestrator_flow.py\n")
    
    print("Option B: Use monitoring script:")
    print("  python start_all_consumers.py  # Starts all 3 tiers\n")
    
    print("What to expect:")
    print("  1. Manager receives task from agentic-dev:manager:tasks")
    print("  2. Manager analyzes goal and delegates:")
    print("     - Leads goal → XADD agentic-dev:leads:tasks")
    print("     - Outreach goal → XADD agentic-dev:outreach:tasks")
    print("  3. Orchestrators process and publish results")
    print("  4. Manager publishes final result to agentic-dev:manager:results\n")
    
    print("📊 Utilities:")
    print("  • Reset consumer groups: python reset_consumer_groups.py")
    print("  • Verify streams: python verify_redis_streams.py")
    print("  • Check this diagnostic: python diagnostic.py\n")

def main():
    """Run all checks"""
    print_header("SYSTEM DIAGNOSTIC - THREE-TIER ARCHITECTURE")
    print("Checking prerequisites for Manager → Orchestrators → Agents flow\n")
    
    results = {
        'Redis': check_redis(),
        'Environment': check_environment(),
        'Dependencies': check_dependencies(),
        'Files': check_files(),
        'VirtualEnv': check_venv(),
        'Streams': check_redis_streams(),
    }
    
    # Summary
    print_header("DIAGNOSTIC SUMMARY")
    for check, result in results.items():
        status = "✅" if result else "⚠️"
        print(f"{status} {check}")
    
    all_good = all(results.values())
    
    if all_good:
        print("\n✅ All checks passed! Ready to run tests.\n")
        print_next_steps()
    else:
        print("\n⚠️ Some checks failed. Please fix the issues above.\n")
        if not results['Redis']:
            print("Fix: Ensure REDIS_URL is set and Redis is running")
        if not results['Environment']:
            print("Fix: Set required environment variables in .env or terminal")
        if not results['Dependencies']:
            print("Fix: Run 'pip install -r requirements.txt'")
        if not results['Files']:
            print("Fix: Run 'git pull' to get latest files")
        print()

if __name__ == "__main__":
    main()
