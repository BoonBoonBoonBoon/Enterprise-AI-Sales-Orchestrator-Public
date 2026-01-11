"""
Standalone test - directly calls Persistence Agent without Redis Streams.
Run with: python tiers/tier_3/persistence_agent/tests/direct_test.py
"""

import asyncio
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
import redis

# Load environment
load_dotenv()

async def main():
    """Test Persistence Agent directly without consumer."""
    from tiers.tier_3.persistence_agent.persistence_agent import PersistenceAgent
    
    print("\n" + "="*80)
    print("DIRECT PERSISTENCE AGENT TEST (No Consumer)")
    print("="*80)
    
    # Initialize Redis
    redis_url = os.getenv("REDIS_URL")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    
    # Initialize Persistence Agent
    agent = PersistenceAgent(
        redis_client=redis_client,
        tenant_id="agentic-dev",
        model="gpt-4o-mini"
    )
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Test 1: Create staging lead
    print("\n" + "-"*80)
    print("TEST 1: Create Staging Lead")
    print("-"*80)
    
    result = await agent.execute(
        task_data_or_goal=f"Create staging lead for direct_test_{timestamp}@example.com",
        context={
            "email": f"direct_test_{timestamp}@example.com",
            "first_name": "Direct",
            "last_name": "Test",
            "company_name": "Test Company",
            "job_title": "Tester",
            "source": "direct_test"
        }
    )
    
    print(f"\n[RESULT] {result}")
    
    if result.get("status") == "success":
        print(f"\n[SUCCESS] Created staging lead with ID {result.get('id')}")
    else:
        print(f"[FAILED] {result}")
    
    # Test 2: Create lead
    print("\n" + "-"*80)
    print("TEST 2: Create Lead")
    print("-"*80)
    
    result = await agent.execute(
        task_data_or_goal=f"Create lead for direct_test_lead_{timestamp}@example.com",
        context={
            "email": f"direct_test_lead_{timestamp}@example.com",
            "first_name": "Lead",
            "last_name": "Test",
            "company_name": "Lead Co",
            "job_title": "CEO",
            "current_status": "active",
            "lead_score": 75
        }
    )
    
    print(f"\n[RESULT] {result}")
    
    if result.get("status") == "success":
        lead_id = result.get("id")
        print(f"\n[SUCCESS] Created lead with ID {lead_id}")
        
        # Test 3: Create conversation
        print("\n" + "-"*80)
        print("TEST 3: Create Conversation")
        print("-"*80)
        
        result = await agent.execute(
            task_data_or_goal="Create conversation for the lead",
            context={
                "lead_id": lead_id,
                "channel": "email",
                "status": "active"
            }
        )
        
        print(f"\n[RESULT] {result}")
        
        if result.get("status") == "success":
            conv_id = result.get("id")
            print(f"\n[SUCCESS] Created conversation with ID {conv_id}")
            
            # Test 4: Create message
            print("\n" + "-"*80)
            print("TEST 4: Create Message")
            print("-"*80)
            
            result = await agent.execute(
                task_data_or_goal="Create outbound message in the conversation",
                context={
                    "conversation_id": conv_id,
                    "sender_type": "agent",
                    "text_content": "This is a test message from direct test"
                }
            )
            
            print(f"\n[RESULT] {result}")
            
            if result.get("status") == "success":
                print(f"\n[SUCCESS] Created message with ID {result.get('id')}")
            else:
                print(f"[FAILED] {result}")
        else:
            print(f"[FAILED] {result}")
    else:
        print(f"[FAILED] {result}")
    
    print("\n" + "="*80)
    print("[COMPLETE] DIRECT TEST COMPLETE")
    print("="*80)
    print(f"\nTest timestamp: {timestamp}")
    print(f"Check Supabase for records with emails containing: {timestamp}")
    
    redis_client.close()

if __name__ == "__main__":
    asyncio.run(main())
