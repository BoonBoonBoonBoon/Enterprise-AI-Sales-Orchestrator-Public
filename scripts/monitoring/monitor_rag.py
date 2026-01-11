#!/usr/bin/env python
"""
Monitor RAG Agent Task Processing
Real-time dashboard showing task queue, processing status, and results
"""

import redis
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import time

load_dotenv()

redis_url = os.getenv('REDIS_URL')
r = redis.from_url(redis_url, decode_responses=True)

def get_progress():
    """Get current processing statistics"""
    tasks_total = r.xlen('agentic-dev:agents:rag:tasks')
    results_total = r.xlen('agentic-dev:agents:rag:results')
    
    # Get pending in consumer group
    try:
        group_info = r.xinfo_groups('agentic-dev:agents:rag:tasks')
        pending = group_info[0]['pending'] if group_info else 0
        consumers = group_info[0]['consumers'] if group_info else 0
    except:
        pending = 0
        consumers = 0
    
    processed = results_total
    remaining = pending
    
    return {
        'total_tasks': tasks_total,
        'total_results': results_total,
        'pending': pending,
        'active_consumers': consumers,
        'processed': processed,
    }

def display_dashboard():
    """Display real-time processing dashboard"""
    progress = get_progress()
    
    print('\n')
    print('╔' + '═'*78 + '╗')
    print('║' + ' '*20 + 'RAG AGENT PROCESSING DASHBOARD' + ' '*27 + '║')
    print('╚' + '═'*78 + '╝')
    
    print(f'\n⏱️  Last updated: {datetime.now().strftime("%H:%M:%S")}\n')
    
    # Progress bar
    total = progress['total_tasks']
    processed = progress['processed']
    pending = progress['pending']
    
    if total > 0:
        pct = int(100 * processed / total)
        bar_len = 40
        filled = int(bar_len * processed / total)
        bar = '█' * filled + '░' * (bar_len - filled)
        
        print(f'Processing Progress: [{bar}] {pct}%')
        print(f'  {processed} results / {total} total tasks')
        print(f'  {pending} pending (being processed by {progress["active_consumers"]} workers)')
    else:
        print('No tasks queued')
    
    print('\n📊 Queue Status:')
    print(f'  Task Stream: {progress["total_tasks"]} messages')
    print(f'  Result Stream: {progress["total_results"]} messages')
    print(f'  Pending in Consumer Group: {progress["pending"]}')
    print(f'  Active Workers: {progress["active_consumers"]}')
    
    # Recent results
    print('\n📋 Recent Results (last 5):')
    results = r.xrevrange('agentic-dev:agents:rag:results', count=5)
    
    for i, (msg_id, data) in enumerate(results, 1):
        raw = data.get('data') or data.get('payload')
        try:
            payload = json.loads(raw)
            metadata = payload.get('metadata', {})
            task_status = payload.get('payload', {}).get('status', 'unknown')
            
            # Extract email from result if available
            result = payload.get('payload', {}).get('result', {})
            msg_count = len(result.get('messages', [])) if isinstance(result, dict) else 0
            
            print(f'\n  {i}. {msg_id}')
            print(f'     Status: {task_status}')
            print(f'     Messages: {msg_count}')
            print(f'     Time: {metadata.get("created_at", "N/A")[:19]}')
        except:
            print(f'\n  {i}. {msg_id} [parse error]')
    
    print('\n' + '═'*80 + '\n')

if __name__ == '__main__':
    print('\n🚀 RAG Agent Monitor - Press Ctrl+C to exit\n')
    
    try:
        while True:
            display_dashboard()
            print('Waiting 5 seconds before next update...')
            time.sleep(5)
    except KeyboardInterrupt:
        print('\n\n✅ Monitor stopped\n')
