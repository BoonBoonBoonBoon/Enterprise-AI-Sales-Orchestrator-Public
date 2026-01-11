#!/usr/bin/env python
import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('REDIS_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
os.environ.setdefault('TENANT_ID', os.getenv('TENANT_ID', 'agentic-dev'))

import redis
from tiers.tier_1.manager.manager_agent import ManagerAgent

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
tenant_id = os.getenv('TENANT_ID', 'agentic-dev')

redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
manager = ManagerAgent(redis_client=redis_client, tenant_id=tenant_id)

task_data = {
    'task_id': 'test-123',
    'goal': 'Find 50 AI/ML startups in San Francisco',
    'criteria': {'location': 'San Francisco', 'industry': 'AI/ML'},
}

result = manager.execute(task_data)
print(f"Intent: {result['intent']}")
print(f"Orchestrators: {result['orchestrators']}")
print(f"Enqueued: {result['enqueued']}")
