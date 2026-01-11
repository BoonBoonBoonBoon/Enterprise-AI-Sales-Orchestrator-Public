"""Check Redis streams and consumer groups status."""
import asyncio
import redis.asyncio as redis

async def check_redis():
    client = redis.Redis(host='localhost', port=6379)
    
    # Check persistence stream
    print('='*80)
    print('PERSISTENCE STREAM')
    print('='*80)
    
    info = await client.xinfo_stream('agentic-dev:agents:persistence:tasks')
    print(f'Task Stream Length: {info.get("length")} messages')
    print(f'Result Stream: agentic-dev:agents:persistence:results')
    
    try:
        groups = await client.xinfo_groups('agentic-dev:agents:persistence:tasks')
        for group in groups:
            name = group.get('name')
            if isinstance(name, bytes):
                name = name.decode()
            print(f'\nConsumer Group: {name}')
            print(f'  Consumers: {group.get("consumers")}')
            print(f'  Pending: {group.get("pending")}')
            
            # List consumers in group
            consumers = await client.xinfo_consumers('agentic-dev:agents:persistence:tasks', name)
            for consumer in consumers:
                cname = consumer.get('name')
                if isinstance(cname, bytes):
                    cname = cname.decode()
                print(f'    - {cname}: {consumer.get("pending")} pending')
    except Exception as e:
        print(f'  No consumer groups yet: {e}')
    
    # Check copywriter stream
    print('\n' + '='*80)
    print('COPYWRITER STREAM')
    print('='*80)
    
    info = await client.xinfo_stream('agentic-dev:agents:copywriter:tasks')
    print(f'Task Stream Length: {info.get("length")} messages')
    print(f'Result Stream: agentic-dev:agents:copywriter:results')
    
    try:
        groups = await client.xinfo_groups('agentic-dev:agents:copywriter:tasks')
        for group in groups:
            name = group.get('name')
            if isinstance(name, bytes):
                name = name.decode()
            print(f'\nConsumer Group: {name}')
            print(f'  Consumers: {group.get("consumers")}')
            print(f'  Pending: {group.get("pending")}')
            
            # List consumers in group
            consumers = await client.xinfo_consumers('agentic-dev:agents:copywriter:tasks', name)
            for consumer in consumers:
                cname = consumer.get('name')
                if isinstance(cname, bytes):
                    cname = cname.decode()
                print(f'    - {cname}: {consumer.get("pending")} pending')
    except Exception as e:
        print(f'  No consumer groups yet: {e}')
    
    print('\n' + '='*80)
    print('RESULT STREAMS')
    print('='*80)
    
    try:
        info = await client.xinfo_stream('agentic-dev:agents:persistence:results')
        print(f'Persistence Results: {info.get("length")} messages')
    except:
        print('Persistence Results: Stream not created yet')
    
    try:
        info = await client.xinfo_stream('agentic-dev:agents:copywriter:results')
        print(f'Copywriter Results: {info.get("length")} messages')
    except:
        print('Copywriter Results: Stream not created yet')
    
    await client.close()

asyncio.run(check_redis())
