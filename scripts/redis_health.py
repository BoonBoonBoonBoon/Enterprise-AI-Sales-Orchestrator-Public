"""Basic Redis Streams health/visibility script.

Shows streams, lengths, and pending per consumer group for a given topic.

Usage:
  python scripts/redis_health.py --topic orchestrate
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from agent.Infastructure.queue.adapters.redis_streams_queue import RedisStreamsQueue


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--topic', default='orchestrate')
    args = p.parse_args()

    q = RedisStreamsQueue()
    client = q.client
    stream = q._stream(args.topic)
    group = q._group(args.topic)

    print('Stream:', stream)
    try:
        info = client.xinfo_stream(stream)
        print('Length:', info.get('length'))
        print('Last-generated-id:', info.get('last-generated-id'))
    except Exception as e:
        print('xinfo_stream error:', e)

    try:
        g = client.xinfo_groups(stream)
        print('Groups:')
        for grp in g:
            print('  -', grp)
    except Exception as e:
        print('xinfo_groups error:', e)

    try:
        consumers = client.xinfo_consumers(stream, group)
        print('Consumers:')
        for c in consumers:
            print('  -', c)
    except Exception as e:
        print('xinfo_consumers error:', e)

if __name__ == '__main__':
    main()
