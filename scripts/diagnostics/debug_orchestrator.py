"""Debug orchestrator processing."""
from dotenv import load_dotenv
load_dotenv()  # Load .env file first!

from agent.orchestrators.workflow_manager import WorkflowManager
from agent.utils.typed_envelope import from_redis_message

wm = WorkflowManager()
print(f'Orchestrator listening on: {wm.stream}')
print(f'Worker ID: {wm.worker_id}')
print(f'Group: {wm.group}')
print()

entries = wm.r.client.xreadgroup(wm.group, wm.worker_id, {wm.stream: '>'}, count=10, block=1000)
print(f'Read {len(entries or [])} stream entries')

if entries:
    for stream_name, msgs in entries:
        print(f'Stream: {stream_name}, Messages: {len(msgs)}')
        for msg_id, fields in msgs:
            print(f'  Processing: {msg_id}')
            try:
                env = from_redis_message(fields)
                print(f'  Command type: {env.payload.get("type")}')
                print(f'  Correlation: {env.metadata.correlation_id}')
                
                # Try to process it through the orchestrator
                cmd_type = env.payload.get("type")
                print(f'  Routing command: {cmd_type}')
                
                if cmd_type == "query_leads":
                    wm._handle_query_leads(env)
                    print('  ✅ Routed to RAG')
                elif cmd_type == "generate_copy":
                    wm._handle_generate_copy(env)
                    print('  ✅ Routed to copywriter')
                
                # Acknowledge
                wm.r.client.xack(wm.stream, wm.group, msg_id)
                print('  ✅ Acknowledged')
                
            except Exception as e:
                print(f'  ❌ Error: {e}')
                import traceback
                traceback.print_exc()
else:
    print('No pending messages')
