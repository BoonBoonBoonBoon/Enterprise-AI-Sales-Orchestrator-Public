import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

print('Stream Lengths:')
print(f'  Tasks: {r.xlen("agentic-dev:agents:rag:tasks")}')
print(f'  Results: {r.xlen("agentic-dev:agents:rag:results")}')

print('\nLast Task Message:')
last_task = r.xrevrange('agentic-dev:agents:rag:tasks', count=1)
if last_task:
    msg_id, data = last_task[0]
    print(f'  ID: {msg_id}')
    for k, v in data.items():
        if len(str(v)) > 100:
            print(f'  {k}: {str(v)[:100]}...')
        else:
            print(f'  {k}: {v}')
else:
    print('  No tasks found')

print('\nLast Result Message:')
last_result = r.xrevrange('agentic-dev:agents:rag:results', count=1)
if last_result:
    msg_id, data = last_result[0]
    print(f'  ID: {msg_id}')
    for k, v in data.items():
        if len(str(v)) > 100:
            print(f'  {k}: {str(v)[:100]}...')
        else:
            print(f'  {k}: {v}')
else:
    print('  No results found')
