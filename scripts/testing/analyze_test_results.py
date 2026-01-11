import redis
import json
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

redis_url = os.getenv('REDIS_URL')
r = redis.from_url(redis_url, decode_responses=True)

# Our test task IDs (from last run)
test_task_ids = {
    'real_1': '3072993c-dbbd-431c-be03-7813fb16c6ea',  # chris.wilson
    'real_2': 'f4197c38-9b9d-45e2-8fbf-7a75ee7e678c',  # jordan.brown
    'real_3': '46049dcf-401c-4515-9213-9438fcdd97cd',  # alex.taylor
    'fake_complete': '8202926f-fcff-477f-ba11-7df1e7b58656',  # sarah.martinez
    'fake_partial': '0cea2bed-e9ea-47ad-8863-e788ef11c21f',  # michael.chen
    'fake_hopeless': 'cfe1372b-b996-4437-986c-3e25ae28e922',  # hopeless
}

print('Test Results Analysis')
print('='*80)

# Get all results
results = r.xrevrange('agentic-dev:agents:rag:results', count=100)

found = {}
for msg_id, data in results:
    if 'data' in data:
        raw = data.get('data') or data.get('payload')
    else:
        raw = data.get('payload')
    
    try:
        payload = json.loads(raw)
        metadata = payload.get('metadata', {})
        task_id = metadata.get('task_id')
        
        # Check if this is one of our test tasks
        for test_name, expected_id in test_task_ids.items():
            if task_id == expected_id:
                found[test_name] = {
                    'task_id': task_id,
                    'result': payload.get('payload', {}),
                    'status': payload.get('payload', {}).get('status', 'unknown'),
                    'created_at': metadata.get('created_at'),
                    'msg_id': msg_id
                }
    except Exception:
        pass

print(f'\n🔍 Found {len(found)}/{len(test_task_ids)} test results\n')

# Display results
for test_name in ['real_1', 'real_2', 'real_3', 'fake_complete', 'fake_partial', 'fake_hopeless']:
    if test_name in found:
        result = found[test_name]
        status = result['status']
        
        if 'real' in test_name:
            emoji = '✅'
            category = 'REAL SUPABASE'
        elif 'complete' in test_name:
            emoji = '✅'
            category = 'FAKE COMPLETE'
        elif 'partial' in test_name:
            emoji = '🔧'
            category = 'FAKE PARTIAL'
        else:
            emoji = '❌'
            category = 'FAKE HOPELESS'
        
        print(f'{emoji} {test_name.upper()}')
        print(f'   Category: {category}')
        print(f'   Status: {status}')
        print(f'   Message ID: {result["msg_id"]}')
        
        # Get result details
        result_data = result['result'].get('result', {})
        if isinstance(result_data, dict):
            if 'score' in result_data:
                print(f'   Completeness Score: {result_data.get("score")}')
            if 'execution_path' in result_data:
                print(f'   Execution Path: {result_data.get("execution_path")}')
            if 'message' in result_data:
                msg = result_data.get('message', '')
                if len(msg) > 60:
                    print(f'   Result: {msg[:60]}...')
                else:
                    print(f'   Result: {msg}')
        print()
    else:
        if 'real' in test_name:
            emoji = '⏳'
        elif 'complete' in test_name:
            emoji = '⏳'
        elif 'partial' in test_name:
            emoji = '⏳'
        else:
            emoji = '⏳'
        
        print(f'{emoji} {test_name.upper()}')
        print(f'   Status: PENDING/NOT FOUND')
        print()

print('='*80)
print(f'Summary: {len(found)} of 6 test cases have results')
print(f'Total results in stream: {r.xlen("agentic-dev:agents:rag:results")}')
print(f'Total tasks in stream: {r.xlen("agentic-dev:agents:rag:tasks")}')

# Check pending
try:
    group_info = r.xinfo_groups('agentic-dev:agents:rag:tasks')
    for group in group_info:
        print(f'Pending in consumer group: {group["pending"]}')
except:
    pass
