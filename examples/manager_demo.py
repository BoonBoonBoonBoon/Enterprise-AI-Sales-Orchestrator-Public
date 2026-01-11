"""
Manager Agent Demo

Quick demonstration of Manager Agent capabilities:
1. Shortcut execution (< 50ms)
2. Goal analysis and delegation
3. Task tracking

Usage:
    python examples/manager_demo.py
"""

import os
import redis
from agent.manager.manager_agent import ManagerAgent

# Set OpenAI API key (if available)
if not os.environ.get("OPENAI_API_KEY"):
    print("⚠️  Warning: OPENAI_API_KEY not set. Agent delegation will fail.")
    print("Set it with: export OPENAI_API_KEY=your_key_here\n")

# Initialize Redis
try:
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False)
    redis_client.ping()
    print("✅ Redis connected\n")
except redis.ConnectionError:
    print("❌ Redis not available. Start it with: docker compose up -d redis")
    exit(1)

# Create Manager Agent
print("🤖 Initializing Manager Agent...\n")
manager = ManagerAgent(
    redis_client=redis_client,
    tenant_id="demo",
    model="gpt-4o",
    temperature=0.0
)

print("=" * 70)
print("MANAGER AGENT DEMO")
print("=" * 70)

# Demo 1: Shortcut - Simple calculation
print("\n📊 Demo 1: Shortcut Execution (Calculation)")
print("-" * 70)
result = manager.execute("What is 25 * 4?")
print(f"Goal: 'What is 25 * 4?'")
print(f"Path: {result['path']}")
print(f"Result: {result['result']}")
print(f"Latency: {result['latency_ms']:.2f}ms")
print(f"✅ Fast path: {result['latency_ms'] < 50}ms")

# Demo 2: Shortcut - Current time
print("\n📊 Demo 2: Shortcut Execution (Date/Time)")
print("-" * 70)
result = manager.execute("What is the current time?")
print(f"Goal: 'What is the current time?'")
print(f"Path: {result['path']}")
print(f"Result: {result['result']}")
print(f"Latency: {result['latency_ms']:.2f}ms")

# Demo 3: Shortcut - Health check
print("\n📊 Demo 3: Shortcut Execution (Health Check)")
print("-" * 70)
result = manager.execute("Run health check")
print(f"Goal: 'Run health check'")
print(f"Path: {result['path']}")
print(f"Redis: {result['result']['redis']}")
print(f"Timestamp: {result['result']['timestamp']}")
print(f"Latency: {result['latency_ms']:.2f}ms")

# Demo 4: Agent delegation - Data query
print("\n📊 Demo 4: Agent Delegation (Data Query)")
print("-" * 70)
print("Goal: 'Find all leads in the tech industry created in the last 30 days'")

if os.environ.get("OPENAI_API_KEY"):
    result = manager.execute("Find all leads in the tech industry created in the last 30 days")
    print(f"Path: {result['path']}")
    if result['success']:
        print(f"Result: {result['result']}")
        print(f"Agent Steps: {result.get('agent_steps', 'N/A')}")
        print(f"Latency: {result['latency_ms']:.2f}ms")
        
        # Try to parse task_id from result
        import json
        try:
            if '"task_id"' in result['result']:
                # Agent returned JSON with task_id
                print("\n📋 Task delegated to Data Orchestrator")
                print("You can check status with manager.get_task_result(task_id)")
        except Exception:
            pass
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
else:
    print("⏭️  Skipped (requires OPENAI_API_KEY)")

# Demo 5: Agent delegation - Email generation
print("\n📊 Demo 5: Agent Delegation (Email Generation)")
print("-" * 70)
print("Goal: 'Generate an outreach email for lead_123 in campaign_456'")

if os.environ.get("OPENAI_API_KEY"):
    result = manager.execute("Generate an outreach email for lead_123 in campaign_456")
    print(f"Path: {result['path']}")
    if result['success']:
        print(f"Result: {result['result']}")
        print(f"Agent Steps: {result.get('agent_steps', 'N/A')}")
        print(f"Latency: {result['latency_ms']:.2f}ms")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
else:
    print("⏭️  Skipped (requires OPENAI_API_KEY)")

# Demo 6: Manager health check
print("\n📊 Demo 6: Manager Health Check")
print("-" * 70)
health = manager.health_check()
print(f"Status: {health['status']}")
print(f"Model: {health['model']}")
print(f"Tenant: {health['tenant_id']}")
print(f"Components:")
for component, status in health['components'].items():
    icon = "✅" if status == "healthy" else "⚠️"
    print(f"  {icon} {component}: {status}")

print("\n" + "=" * 70)
print("DEMO COMPLETE")
print("=" * 70)
print("\n📚 Next Steps:")
print("1. Set OPENAI_API_KEY to test full delegation")
print("2. Start orchestrator workers to process delegated tasks")
print("3. Check Redis Streams to see queued tasks:")
print("   redis-cli XREAD STREAMS demo:coding:tasks demo:data:tasks 0-0 0-0")
print("\n💡 Tips:")
print("- Shortcuts handle simple tasks in <50ms")
print("- Complex tasks are delegated to specialist orchestrators")
print("- All delegations go through Redis Streams for async processing")
print("- Manager tracks execution_id for observability")
