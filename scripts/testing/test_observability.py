"""
Quick test of Manager with observability
"""
import redis
import time
import json

def send_test_request():
    """Send a test request to the Manager"""
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    request = {
        'tenant_id': 'test_company',
        'execution_id': f'test_{int(time.time())}',
        'goal': 'Send outreach campaign to new leads',
        'context': json.dumps({'campaign_type': 'cold_outreach'})
    }
    
    print("📤 Sending test request to Manager...")
    print(f"   Tenant: {request['tenant_id']}")
    print(f"   Goal: {request['goal']}")
    
    message_id = r.xadd('tier_1:manager:requests', request)
    print(f"✅ Request sent! Message ID: {message_id}")
    
    print("\n📊 Check observability:")
    print("   • Prometheus: http://localhost:9090")
    print("   • Grafana: http://localhost:3000")
    print("   • Metrics: http://localhost:8000/metrics")
    print(f"   • Redis audit: redis-cli XREAD STREAMS manager:decisions:test_company:2025-11-18 0")

if __name__ == "__main__":
    send_test_request()
