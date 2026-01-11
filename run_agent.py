"""Minimal runner for the RAG agent.

Usage: python run_agent.py --table leads --filter name ilike %john%

This runner accepts a JSON string for filters via --filters argument as well.
"""
import argparse
import json
import re
from agent.operational_agents.rag_agent.rag_agent import RAGAgent

parser = argparse.ArgumentParser(description='Query the leads table or send a free-text prompt to the agent')
group = parser.add_mutually_exclusive_group()
group.add_argument('--filters', help='JSON string of filters ({"id":..., "email":..., "company":...})')
group.add_argument('--id', help='Exact id to filter')
parser.add_argument('--email', help='Email to filter (supports % wildcards)')
parser.add_argument('--company', help='Company name to filter (partial match)')
parser.add_argument('--select', help='select clause', default='*')
parser.add_argument('--prompt', help='Free text natural language prompt to send to the agent', default=None)
parser.add_argument('--json', action='store_true', help='Emit raw JSON output instead of human-readable summary')
parser.add_argument('--include-raw', action='store_true', help='Include full raw_row in provenance (use sparingly)')
args = parser.parse_args()

agent = RAGAgent()

if args.prompt:
	# send free-text prompt to the agent; it will attempt parsing then fallback to the agent planner
	res = agent.run(args.prompt, return_json=args.json, include_raw=args.include_raw)
	# If JSON requested and result is list/dict-like, attempt to print JSON
	if args.json:
		# if the agent returned a formatted string, try to detect JSON inside
		try:
			# if it's already a list/dict, json.dumps will work
			print(json.dumps(res, default=str, ensure_ascii=False, indent=2))
			
		except TypeError:
			# fallback: if string contains JSON object/array, extract it
			if isinstance(res, str):
				m = re.search(r"(\{.*\}|\[.*\])", res, re.S)
				if m:
					try:
						print(json.dumps(json.loads(m.group(1)), ensure_ascii=False, indent=2))
					except Exception:
						print(res)
				else:
					print(res)
			else:
				print(res)
	else:
		print(res)
else:
	if args.filters:
		filters = json.loads(args.filters)
		# call tool directly
		tool = next(t for t in agent.tools if t.name == 'query_leads')
		print(tool.func({'filters': filters, 'select': args.select}))
	else:
		print(agent.query_leads(id=args.id, email=args.email, company=args.company, select=args.select))
