import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv('REDIS_URL')
r = redis.from_url(redis_url, decode_responses=True)

# Our test task IDs
test_task_ids = {
    'real_1': '3072993c-dbbd-431c-be03-7813fb16c6ea',  # chris.wilson
    'real_2': 'f4197c38-9b9d-45e2-8fbf-7a75ee7e678c',  # jordan.brown
    'real_3': '46049dcf-401c-4515-9213-9438fcdd97cd',  # alex.taylor
    'fake_complete': '8202926f-fcff-477f-ba11-7df1e7b58656',  # sarah.martinez
    'fake_partial': '0cea2bed-e9ea-47ad-8863-e788ef11c21f',  # michael.chen
    'fake_hopeless': 'cfe1372b-b996-4437-986c-3e25ae28e922',  # hopeless
}

print('Detailed Test Results\n')
print('='*80 + '\n')

results = r.xrevrange('agentic-dev:agents:rag:results', count=100)

test_results = {}
for msg_id, data in results:
    raw = data.get('data') or data.get('payload')
    
    try:
        payload = json.loads(raw)
        task_id = payload.get('metadata', {}).get('task_id')
        
        for test_name, expected_id in test_task_ids.items():
            if task_id == expected_id:
                test_results[test_name] = payload
    except Exception:
        pass

for test_name in ['real_1', 'real_2', 'real_3', 'fake_complete', 'fake_partial', 'fake_hopeless']:
    if test_name in test_results:
        payload = test_results[test_name]
        inner_payload = payload.get('payload', {})
        result = inner_payload.get('result', {})
        
        print(f'{test_name.upper()}')
        print('-'*80)
        
        # Extract key info
        if isinstance(result, dict):
            # Pretty print the result object
            print('Result object keys:', list(result.keys())[:5])
            
            # Try to extract meaningful data
            if 'messages' in result:
                print(f'Messages: {len(result["messages"])} items')
            if 'score' in result:
                print(f'Score: {result["score"]}')
            if 'execution_path' in result:
                print(f'Execution Path: {result["execution_path"]}')
            if 'message' in result:
                msg = result['message']
                print(f'Message (first 100 chars): {msg[:100]}')
        else:
            print(f'Result type: {type(result).__name__}')
            print(f'Result: {str(result)[:200]}')
        
        print()
    else:
        print(f'{test_name.upper()}')
        print('-'*80)
        print('NO RESULT FOUND')
        print()
