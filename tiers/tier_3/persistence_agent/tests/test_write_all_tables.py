"""
One-time write test for all core Supabase tables.

Tests Persistence Agent's write capabilities across:
- staging_leads (4 records via individual creates)
- leads (4 records via individual creates)
- conversations (1 per lead)
- messages (1 per conversation)

Also includes staging_conversations + staging_messages (1 per staging lead) using service-role
Supabase client to ensure the UI data model is covered in tests.

Run with: pytest tiers/tier_3/persistence_agent/tests/test_write_all_tables.py -v -s
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Dict, List

import pytest
import redis.asyncio as aioredis
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Supabase for cleanup
from supabase import create_client, Client


class TestWriteAllTables:
    """Test writes to all 4 core tables with FK relationships."""
    
    @pytest.fixture
    async def redis_client(self):
        """Create async Redis client."""
        client = aioredis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True
        )
        yield client
        await client.close()
    
    @pytest.fixture
    def supabase_client(self) -> Client:
        """Create Supabase client for cleanup."""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            pytest.skip("Supabase credentials not configured")
        
        return create_client(supabase_url, supabase_key)
    
    @pytest.fixture
    def tenant_id(self) -> str:
        """Use existing tenant for tests."""
        return "agentic-dev"
    
    @pytest.fixture
    def test_timestamp(self) -> str:
        """Unique timestamp for test data identification."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    @pytest.fixture
    def client_id(self) -> str:
        """
        Client ID for test records.
        
        NOTE: Using a test UUID. If your schema enforces FK to clients table,
        you may need to create a test client record first or use an existing client_id.
        """
        # Use a test UUID - update if FK constraint requires existing client
        return str(uuid.uuid4())
    
    async def _send_persistence_task(
        self,
        redis_client: aioredis.Redis,
        tenant_id: str,
        goal: str,
        context: Dict
    ) -> Dict:
        """
        Send task to Persistence Agent via Redis Streams.
        
        Args:
            redis_client: Async Redis client
            tenant_id: Tenant identifier
            goal: Natural language goal for Deep Agent
            context: Tool parameters
        
        Returns:
            Result from agent
        """
        task_stream = f"{tenant_id}:agents:persistence:tasks"
        result_stream = f"{tenant_id}:agents:persistence:results"
        task_id = str(uuid.uuid4())
        
        # Create envelope
        envelope = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "payload": {
                "goal": goal,
                "context": context
            },
            "metadata": {
                "source": "test",
                "target": "persistence",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Convert envelope to Redis fields (flatten the dict)
        import json
        redis_fields = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "payload": json.dumps(envelope["payload"]),
            "metadata": json.dumps(envelope["metadata"])
        }
        
        # Publish to tasks stream
        await redis_client.xadd(task_stream, redis_fields)
        print(f"📤 Published task {task_id} to {task_stream}")
        
        # Wait for result (with timeout)
        timeout = 30  # seconds
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            # Read from results stream
            results = await redis_client.xread(
                {result_stream: "0"},
                count=100,
                block=1000
            )
            
            if results:
                for stream, messages in results:
                    for message_id, data in messages:
                        if data.get("task_id") == task_id:
                            print(f"✅ Received result for task {task_id}")
                            # Parse the payload if it's JSON
                            import json
                            result_data = dict(data)
                            if "payload" in result_data and isinstance(result_data["payload"], str):
                                try:
                                    result_data["payload"] = json.loads(result_data["payload"])
                                except:
                                    pass
                            return result_data.get("payload", result_data)
            
            await asyncio.sleep(0.5)
        
        raise TimeoutError(f"No result received for task {task_id} after {timeout}s")
    
    @pytest.mark.asyncio
    async def test_write_staging_leads(
        self,
        redis_client: aioredis.Redis,
        tenant_id: str,
        test_timestamp: str,
        client_id: str
    ) -> List[str]:
        """Test 1: Write 4 staging leads via individual creates (capture IDs)."""
        print("\n" + "="*60)
        print("TEST 1: Writing 4 staging_leads (individual)")
        print("="*60)
        
        # Mock staging leads data
        staging_leads = [
            {
                "email": f"test_staging_1_{test_timestamp}@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "company": "Acme Corp",
                "title": "CEO",
                "source": "test_batch",
                "validation_status": "pending",
                "completeness_score": 0.8,
                "client_id": client_id
            },
            {
                "email": f"test_staging_2_{test_timestamp}@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "company": "Beta Inc",
                "title": "CTO",
                "source": "test_batch",
                "validation_status": "complete",
                "completeness_score": 1.0,
                "promotion_ready": True,
                "client_id": client_id
            },
            {
                "email": f"test_staging_3_{test_timestamp}@example.com",
                "first_name": "Mike",
                "last_name": "Johnson",
                "company": "Gamma LLC",
                "title": "VP Sales",
                "source": "test_batch",
                "validation_status": "failed",
                "completeness_score": 0.3,
                "error_log": "Missing required company data",
                "client_id": client_id
            },
            {
                "email": f"test_staging_4_{test_timestamp}@example.com",
                "first_name": "Lisa",
                "last_name": "Chen",
                "company": "Delta Systems",
                "title": "Head of Marketing",
                "source": "test_batch",
                "validation_status": "complete",
                "completeness_score": 0.95,
                "promotion_ready": True,
                "client_id": client_id
            }
        ]
        
        staging_ids = []
        for i, lead_data in enumerate(staging_leads, 1):
            print(f"\n📝 Creating staging lead {i}/4: {lead_data['email']}")
            result = await self._send_persistence_task(
                redis_client=redis_client,
                tenant_id=tenant_id,
                goal=f"Create staging lead for {lead_data['email']}",
                context=lead_data,
            )
            print(f"\n📊 Result: {result}")
            assert result.get("status") == "success"
            staging_id = result.get("id")
            staging_ids.append(staging_id)
            print(f"✅ Created staging lead with ID: {staging_id}")

        print(f"✅ Created {len(staging_ids)} staging leads")
        return staging_ids

    @pytest.mark.asyncio
    async def test_write_staging_conversations_and_messages(
        self,
        supabase_client: Client,
        redis_client: aioredis.Redis,
        tenant_id: str,
        test_timestamp: str,
        client_id: str
    ) -> List[str]:
        """Test 1b: Write 1 staging_conversation + 1 staging_message per staging lead."""
        print("\n" + "="*60)
        print("TEST 1b: Writing staging_conversations + staging_messages")
        print("="*60)

        staging_lead_ids = await self.test_write_staging_leads(
            redis_client, tenant_id, test_timestamp, client_id
        )

        now = datetime.now().isoformat()
        staging_convos = []
        for idx, staging_lead_id in enumerate(staging_lead_ids, 1):
            staging_convos.append(
                {
                    "staging_lead_id": staging_lead_id,
                    "status": "active",
                    "metadata": {"seed": True, "test": True},
                    "subject": f"Staging convo {idx} - {test_timestamp}",
                    "thread_id": f"stg-thread-{test_timestamp}-{idx}",
                    "channel": "email",
                    "created_at": now,
                    "updated_at": now,
                }
            )

        convo_result = supabase_client.table("staging_conversations").insert(staging_convos).execute()
        staging_conversation_ids = [row["id"] for row in convo_result.data]
        print(f"✅ Created {len(staging_conversation_ids)} staging_conversations")

        staging_messages = []
        for idx, convo_id in enumerate(staging_conversation_ids, 1):
            staging_messages.append(
                {
                    "staging_conversation_id": convo_id,
                    "sender": "lead",
                    "receiver": "agent",
                    "content": f"Staging message {idx} - {test_timestamp}",
                    "sent_at": now,
                    "metadata": {"seed": True, "test": True},
                    "created_at": now,
                    "updated_at": now,
                    "message_id": f"stg-msg-{test_timestamp}-{idx}",
                }
            )

        msg_result = supabase_client.table("staging_messages").insert(staging_messages).execute()
        print(f"✅ Created {len(msg_result.data)} staging_messages")

        return staging_conversation_ids
    
    @pytest.mark.asyncio
    async def test_write_leads(
        self,
        redis_client: aioredis.Redis,
        tenant_id: str,
        test_timestamp: str,
        client_id: str
    ) -> List[str]:
        """Test 2: Write 4 leads and return their IDs."""
        print("\n" + "="*60)
        print("TEST 2: Writing 4 leads (individual creates)")
        print("="*60)
        
        leads_data = [
            {
                "email": f"test_lead_john_{test_timestamp}@acme.com",
                "first_name": "John",
                "last_name": "Parker",
                "company": "Acme Corp",
                "title": "VP of Engineering",
                "status": "active",
                "qualification_score": 85,
                "qualification_status": "qualified",
                "lead_score": 85,
                "enrichment_status": "completed",
                "client_id": client_id
            },
            {
                "email": f"test_lead_jane_{test_timestamp}@beta.com",
                "first_name": "Jane",
                "last_name": "Williams",
                "company": "Beta Technologies",
                "title": "Director of Product",
                "status": "contacted",
                "qualification_score": 70,
                "qualification_status": "qualified",
                "lead_score": 70,
                "last_reply_sentiment": "positive",
                "client_id": client_id
            },
            {
                "email": f"test_lead_mike_{test_timestamp}@gamma.com",
                "first_name": "Mike",
                "last_name": "Anderson",
                "company": "Gamma Solutions",
                "title": "Sales Manager",
                "status": "active",
                "qualification_score": 60,
                "qualification_status": "pending",
                "lead_score": 60,
                "client_id": client_id
            },
            {
                "email": f"test_lead_lisa_{test_timestamp}@delta.com",
                "first_name": "Lisa",
                "last_name": "Taylor",
                "company": "Delta Enterprises",
                "title": "Chief Marketing Officer",
                "status": "active",
                "qualification_score": 90,
                "qualification_status": "qualified",
                "lead_score": 90,
                "enrichment_status": "completed",
                "client_id": client_id
            }
        ]
        
        lead_ids = []
        
        for i, lead_data in enumerate(leads_data, 1):
            print(f"\n📝 Creating lead {i}/4: {lead_data['email']}")
            
            result = await self._send_persistence_task(
                redis_client=redis_client,
                tenant_id=tenant_id,
                goal=f"Create lead for {lead_data['email']}",
                context=lead_data
            )
            
            assert result.get("status") == "success"
            lead_id = result.get("id")
            lead_ids.append(lead_id)
            print(f"✅ Created lead with ID: {lead_id}")
        
        print(f"\n✅ Created all 4 leads: {lead_ids}")
        return lead_ids
    
    @pytest.mark.asyncio
    async def test_write_conversations(
        self,
        redis_client: aioredis.Redis,
        tenant_id: str,
        test_timestamp: str,
        client_id: str
    ) -> List[str]:
        """Test 3: Write 1 conversation per lead."""
        print("\n" + "="*60)
        print("TEST 3: Writing conversations (1 per lead)")
        print("="*60)
        
        # First create leads to get IDs
        lead_ids = await self.test_write_leads(
            redis_client, tenant_id, test_timestamp, client_id
        )
        
        conversations_data = [
            {
                "lead_id": lead_id,
                "subject": f"Lead conversation {idx} - {test_timestamp}",
                "channel": "email",
                "status": "active",
                "client_id": client_id
            }
            for idx, lead_id in enumerate(lead_ids, 1)
        ]
        
        conversation_ids = []
        
        for i, conv_data in enumerate(conversations_data, 1):
            print(f"\n📝 Creating conversation {i}/4: {conv_data['subject']}")
            
            result = await self._send_persistence_task(
                redis_client=redis_client,
                tenant_id=tenant_id,
                goal=f"Create conversation with subject: {conv_data['subject']}",
                context=conv_data
            )
            
            assert result.get("status") == "success"
            conv_id = result.get("id")
            conversation_ids.append(conv_id)
            print(f"✅ Created conversation with ID: {conv_id}")
        
        print(f"\n✅ Created {len(conversation_ids)} conversations: {conversation_ids}")
        return conversation_ids
    
    @pytest.mark.asyncio
    async def test_write_messages(
        self,
        redis_client: aioredis.Redis,
        tenant_id: str,
        test_timestamp: str,
        client_id: str
    ):
        """Test 4: Write 1 message per conversation."""
        print("\n" + "="*60)
        print("TEST 4: Writing messages (1 per conversation)")
        print("="*60)
        
        # First create conversations to get IDs
        conversation_ids = await self.test_write_conversations(
            redis_client, tenant_id, test_timestamp, client_id
        )
        
        messages_data = [
            {
                "conversation_id": convo_id,
                "direction": "outbound",
                "content": f"Test message for conversation {idx} - {test_timestamp}",
                "sender_type": "agent",
                "sentiment_score": 0.0
            }
            for idx, convo_id in enumerate(conversation_ids, 1)
        ]
        
        message_ids = []
        
        for i, msg_data in enumerate(messages_data, 1):
            direction = msg_data['direction']
            preview = msg_data['content'][:50] + "..."
            print(f"\n📝 Creating message {i}/{len(messages_data)} ({direction}): {preview}")
            
            result = await self._send_persistence_task(
                redis_client=redis_client,
                tenant_id=tenant_id,
                goal=f"Create {direction} message in conversation",
                context=msg_data
            )
            
            assert result.get("status") == "success"
            msg_id = result.get("id")
            message_ids.append(msg_id)
            print(f"✅ Created message with ID: {msg_id}")
        
        print(f"\n✅ Created {len(message_ids)} messages: {message_ids}")
        return message_ids
    
    @pytest.mark.asyncio
    async def test_full_workflow(
        self,
        redis_client: aioredis.Redis,
        tenant_id: str,
        test_timestamp: str,
        client_id: str,
        supabase_client: Client
    ):
        """
        Master test: Run all 4 write operations in sequence.
        
        This simulates the full data pipeline:
        1. Import staging leads (batch)
        2. Create qualified leads
        3. Start conversations with leads
        4. Track message exchanges
        """
        print("\n" + "="*80)
        print("MASTER TEST: Full Write Workflow (All 4 Tables)")
        print("="*80)
        
        # Step 1: Staging leads + staging conversations/messages
        staging_conversation_ids = await self.test_write_staging_conversations_and_messages(
            supabase_client, redis_client, tenant_id, test_timestamp, client_id
        )
        
        # Step 2: Leads
        lead_ids = await self.test_write_leads(
            redis_client, tenant_id, test_timestamp, client_id
        )
        
        # Step 3: Conversations
        conversation_ids = await self.test_write_conversations(
            redis_client, tenant_id, test_timestamp, client_id
        )
        
        # Step 4: Messages
        message_ids = await self.test_write_messages(
            redis_client, tenant_id, test_timestamp, client_id
        )
        
        print("\n" + "="*80)
        print("✅ FULL WORKFLOW COMPLETE")
        print("="*80)
        print(f"📊 Summary:")
        print(f"  - Staging Leads: 4 created")
        print(f"  - Staging Conversations: {len(staging_conversation_ids)} created")
        print(f"  - Staging Messages: {len(staging_conversation_ids)} created")
        print(f"  - Leads: {len(lead_ids)} created")
        print(f"  - Conversations: {len(conversation_ids)} created")
        print(f"  - Messages: {len(message_ids)} created")
        print(f"  - Test Timestamp: {test_timestamp}")
        print("="*80)
    
    def test_cleanup_instructions(self, test_timestamp: str):
        """
        Print cleanup instructions (manual cleanup required).
        
        Since Persistence Agent has no delete tools, cleanup must be done manually
        via Supabase dashboard or SQL.
        """
        print("\n" + "="*80)
        print("🧹 CLEANUP INSTRUCTIONS")
        print("="*80)
        print(f"Test data identifier: {test_timestamp}")
        print("\nTo clean up test data, run this SQL in Supabase SQL Editor:\n")
        print(f"-- Delete messages")
        print(f"DELETE FROM messages")
        print(f"WHERE conversation_id IN (")
        print(f"  SELECT id FROM conversations WHERE lead_id IN (")
        print(f"    SELECT id FROM leads WHERE email LIKE '%{test_timestamp}%'")
        print(f"  )")
        print(f");")
        print(f"\n-- Delete staging_messages")
        print(f"DELETE FROM staging_messages")
        print(f"WHERE staging_conversation_id IN (")
        print(f"  SELECT id FROM staging_conversations WHERE staging_lead_id IN (")
        print(f"    SELECT id FROM staging_leads WHERE email LIKE '%{test_timestamp}%'")
        print(f"  )")
        print(f");")
        print(f"\n-- Delete conversations")
        print(f"DELETE FROM conversations")
        print(f"WHERE lead_id IN (")
        print(f"  SELECT id FROM leads WHERE email LIKE '%{test_timestamp}%'")
        print(f");")
        print(f"\n-- Delete staging_conversations")
        print(f"DELETE FROM staging_conversations")
        print(f"WHERE staging_lead_id IN (")
        print(f"  SELECT id FROM staging_leads WHERE email LIKE '%{test_timestamp}%'")
        print(f");")
        print(f"\n-- Delete leads")
        print(f"DELETE FROM leads WHERE email LIKE '%{test_timestamp}%';")
        print(f"\n-- Delete staging_leads")
        print(f"DELETE FROM staging_leads WHERE email LIKE '%{test_timestamp}%';")
        print("="*80)


if __name__ == "__main__":
    """
    Run test standalone (without pytest).
    
    Usage:
        python -m tiers.tier_3.persistence_agent.tests.test_write_all_tables
    """
    import sys
    
    async def main():
        test = TestWriteAllTables()
        redis_client = aioredis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True
        )
        
        tenant_id = "agentic-dev"
        test_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_id = "00000000-0000-0000-0000-000000000001"  # Update with real client_id
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY/SUPABASE_KEY are required for staging tests")

        supabase_client = create_client(supabase_url, supabase_key)

        try:
            await test.test_full_workflow(
                redis_client, tenant_id, test_timestamp, client_id, supabase_client
            )
            test.test_cleanup_instructions(test_timestamp)
        finally:
            await redis_client.close()
    
    asyncio.run(main())
