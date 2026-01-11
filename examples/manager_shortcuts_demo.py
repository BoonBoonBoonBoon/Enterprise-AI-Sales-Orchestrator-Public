"""
Manager Agent Shortcut Demo

Quick demonstration of Manager Agent shortcut capabilities (no API key required):
1. Simple calculations
2. Date/time queries
3. Health checks

Usage:
    python examples/manager_shortcuts_demo.py
"""

import redis
from agent.manager.shortcut_registry import ShortcutRegistry

# Initialize Redis
try:
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False)
    redis_client.ping()
    print("✅ Redis connected\n")
except redis.ConnectionError:
    print("❌ Redis not available. Start it with: docker compose up -d redis")
    exit(1)

# Create Shortcut Registry
print("⚡ Initializing Shortcut Registry...\n")
shortcuts = ShortcutRegistry(redis_client)

print("=" * 70)
print("MANAGER AGENT - SHORTCUT DEMO")
print("=" * 70)

# Demo 1: Simple calculation
print("\n📊 Demo 1: Simple Calculation")
print("-" * 70)
goal = "What is 25 * 4?"
print(f"Goal: '{goal}'")

if shortcuts.can_shortcut(goal):
    result = shortcuts.execute_shortcut(goal)
    print(f"✅ Shortcut detected")
    print(f"Result: {result['result']}")
    print(f"Latency: {result['latency_ms']}")
else:
    print("❌ No shortcut found")

# Demo 2: Complex calculation with parentheses
print("\n📊 Demo 2: Complex Calculation")
print("-" * 70)
goal = "Calculate (100 + 50) / 3"
print(f"Goal: '{goal}'")

if shortcuts.can_shortcut(goal):
    result = shortcuts.execute_shortcut(goal)
    print(f"✅ Shortcut detected")
    print(f"Result: {result['result']}")
    print(f"Latency: {result['latency_ms']}")
else:
    print("❌ No shortcut found")

# Demo 3: Current time
print("\n📊 Demo 3: Current Time")
print("-" * 70)
goal = "What is the current time?"
print(f"Goal: '{goal}'")

if shortcuts.can_shortcut(goal):
    result = shortcuts.execute_shortcut(goal)
    print(f"✅ Shortcut detected")
    print(f"Result: {result['result']}")
    print(f"Latency: {result['latency_ms']}")
else:
    print("❌ No shortcut found")

# Demo 4: Today's date
print("\n📊 Demo 4: Today's Date")
print("-" * 70)
goal = "What date is today?"
print(f"Goal: '{goal}'")

if shortcuts.can_shortcut(goal):
    result = shortcuts.execute_shortcut(goal)
    print(f"✅ Shortcut detected")
    print(f"Result: {result['result']}")
    print(f"Latency: {result['latency_ms']}")
else:
    print("❌ No shortcut found")

# Demo 5: Health check
print("\n📊 Demo 5: Health Check")
print("-" * 70)
goal = "Run health check"
print(f"Goal: '{goal}'")

if shortcuts.can_shortcut(goal):
    result = shortcuts.execute_shortcut(goal)
    print(f"✅ Shortcut detected")
    print(f"Result:")
    health = result['result']
    print(f"  - Redis: {health['redis']}")
    print(f"  - Workers Active: {health.get('workers_active', 0)}")
    if health.get('workers'):
        print(f"  - Worker List: {', '.join(health['workers'])}")
    print(f"  - Timestamp: {health['timestamp']}")
    print(f"Latency: {result['latency_ms']}")
else:
    print("❌ No shortcut found")

# Demo 6: Non-shortcut goal
print("\n📊 Demo 6: Complex Goal (No Shortcut)")
print("-" * 70)
goal = "Find all leads in the tech industry"
print(f"Goal: '{goal}'")

if shortcuts.can_shortcut(goal):
    result = shortcuts.execute_shortcut(goal)
    print(f"✅ Shortcut detected")
    print(f"Result: {result['result']}")
else:
    print("❌ No shortcut found")
    print("This would be delegated to Data Orchestrator by Manager Agent")

print("\n" + "=" * 70)
print("DEMO COMPLETE")
print("=" * 70)
print("\n💡 Key Takeaways:")
print("- Shortcuts handle simple operations in <50ms")
print("- No LLM calls required for shortcuts (zero cost)")
print("- Arithmetic, date/time, health checks are instant")
print("- Complex goals require Manager Agent delegation")
print("\n📚 Next Steps:")
print("- Set OPENAI_API_KEY to test full Manager Agent with delegation")
print("- Run: python -m examples.manager_demo")
print("- Or run full test suite: pytest tests/test_manager_agent.py -v")
