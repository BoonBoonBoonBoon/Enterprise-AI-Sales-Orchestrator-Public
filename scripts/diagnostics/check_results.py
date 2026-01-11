import redis
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Get the last 10 messages from the result stream
results = r.xrevrange('agentic-dev:agents:rag:results', count=10)

print('Last 10 RAG Results:\n')
for i, (msg_id, data) in enumerate(results, 1):
    print(f'{i}. Message ID: {msg_id}')
    
    if 'payload' in data:
        try:
            payload = json.loads(data['payload'])
            task_id = payload.get('task_id', 'N/A')
            status = payload.get('status', 'N/A')
            print(f'   Task ID: {task_id}')
            print(f'   Status: {status}')
            
            # If there's a result, show summary
            if 'result' in payload:
                result = payload['result']
                if isinstance(result, dict):
                    if 'score' in result:
                        print(f'   Score: {result["score"]}')
                    if 'message' in result:
                        print(f'   Message: {result["message"][:80]}')
        except Exception as e:
            print(f'   Parse error: {str(e)[:50]}')
    
    print()
