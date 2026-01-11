import redis
import json
import time

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

print("Sending test tasks to Redis streams...")
print()

# Test 1: RAG tasks
for i in range(5):
    payload = {
        "lead_id": f"test-lead-{i}",
        "query": f"What is machine learning? (query {i})",
        "variant": "A" if i % 2 == 0 else "B"
    }
    
    stream_id = r.xadd(
        'agentic-dev:rag:tasks',
        {
            'payload': json.dumps(payload),
            'msg_type': 'task',
            'correlation_id': f'test-rag-{i}'
        }
    )
    print(f"✓ RAG task {i}: {stream_id}")
    time.sleep(0.5)

print()

# Test 2: Copywriter tasks
for i in range(5):
    payload = {
        "lead_id": f"test-lead-{i}",
        "template": "cold_email",
        "tone": "professional",
        "variant": "A"
    }
    
    stream_id = r.xadd(
        'agentic-dev:copy:tasks',
        {
            'payload': json.dumps(payload),
            'msg_type': 'task',
            'correlation_id': f'test-copy-{i}'
        }
    )
    print(f"✓ Copywriter task {i}: {stream_id}")
    time.sleep(0.5)

print()

# Test 3: Persistence tasks
for i in range(5):
    payload = {
        "operation": "upsert",
        "table": "leads",
        "data": {
            "email": f"test{i}@example.com",
            "name": f"Test User {i}",
            "company": f"Test Co {i}"
        }
    }
    
    stream_id = r.xadd(
        'agentic-dev:persist:tasks',
        {
            'payload': json.dumps(payload),
            'msg_type': 'task',
            'correlation_id': f'test-persist-{i}'
        }
    )
    print(f"✓ Persistence task {i}: {stream_id}")
    time.sleep(0.5)

print()
print("=" * 60)
print("Stream Summary:")
print("=" * 60)

# Check stream lengths
streams = [
    'agentic-dev:rag:tasks',
    'agentic-dev:copy:tasks',
    'agentic-dev:persist:tasks',
    'agentic-dev:rag:results',
    'agentic-dev:copy:results'
]

for stream in streams:
    length = r.xlen(stream)
    print(f"{stream}: {length} messages")

print()
print("✅ Test tasks sent successfully!")
print("📊 View in Grafana: http://localhost:3000")
print("🔍 Check Prometheus metrics: http://localhost:9090")
