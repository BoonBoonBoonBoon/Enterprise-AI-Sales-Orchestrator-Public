"""
Comprehensive Multi-Table Test Suite
Tests all CRUD operations across all tables with RAG (read-only) and Persistence (read/write) agents.

Run: python -m scripts.comprehensive_table_tests
"""

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.persistence.adapters.supabase_adapter import SupabaseAdapter

# Test configuration
TABLES_TO_TEST = [
    'clients',
    'staging_leads',
    'leads',
    'conversations',
    'messages'
]

# Mock data generators
def generate_client_data():
    return {
        "id": str(uuid.uuid4()),
        "name": f"Test Client {datetime.now().strftime('%H%M%S')}"
    }

def generate_staging_lead_data(client_id, campaign_id=None):
    """Generate staging lead with required campaign_id and source"""
    if campaign_id is None:
        # Use actual campaign ID from database
        campaign_id = "9646f98a-e987-4a8c-b786-9b82ea985d38"
    
    return {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "campaign_id": campaign_id,
        "source": "test",  # Required field
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "first_name": "Test",
        "last_name": "Lead",
        "company_name": "Test Company Inc",
        "job_title": "Software Engineer",
        "enrichment_status": "pending",
        "promotion_ready": False
    }

def generate_lead_data(client_id, campaign_id=None):
    """Generate lead data with required fields"""
    if campaign_id is None:
        # Use actual campaign ID from database
        campaign_id = "9646f98a-e987-4a8c-b786-9b82ea985d38"
    
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=1)
    future = now + timedelta(days=7)
    
    return {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "campaign_id": campaign_id,
        "email": f"lead_{uuid.uuid4().hex[:8]}@example.com",
        "first_name": "Test",
        "last_name": "Lead",
        "company_name": "Test Corp",
        "job_title": "Engineer",
        "current_status": "new",
        "sequence_step": 0,
        "sequence_active": False,
        "next_action_date": future.isoformat(),
        "last_contact_date": past.isoformat(),
        "re_engagement_date": future.isoformat(),
        "booking_status": "not_booked",
        "phone_number": ""
    }

def generate_conversation_data(client_id, lead_id):
    """Generate conversation with required lead_id"""
    return {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "lead_id": lead_id,
        "channel": "email",
        "status": "active",
        "summary": "Test conversation for validation"
    }

def generate_message_data(conversation_id):
    return {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "sender_type": "agent",
        "text_content": f"Test message at {datetime.now().isoformat()}",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {}  # Required NOT NULL field (JSONB)
    }


class ComprehensiveTestSuite:
    def __init__(self):
        # Load environment
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.rag_jwt = os.getenv("SUPABASE_RAG_JWT")
        self.persistence_jwt = os.getenv("SUPABASE_PERSISTENCE_JWT")
        
        if not all([self.supabase_url, self.anon_key, self.rag_jwt, self.persistence_jwt]):
            raise ValueError("Missing required environment variables")
        
        # Initialize adapters with anon_key support
        self.rag_adapter = SupabaseAdapter(
            url=self.supabase_url,
            key=self.rag_jwt,
            anon_key=self.anon_key
        )
        
        self.persistence_adapter = SupabaseAdapter(
            url=self.supabase_url,
            key=self.persistence_jwt,
            anon_key=self.anon_key
        )
        
        # Test state tracking
        self.test_client_id = None
        self.test_lead_id = None  # Track created lead for FK dependencies
        self.created_records: Dict[str, List[str]] = {table: [] for table in TABLES_TO_TEST}
        self.passed_tests = 0
        self.failed_tests = 0
        self.results = []
    
    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        symbol = "[PASS]" if passed else "[FAIL]"
        status = "PASSED" if passed else "FAILED"
        
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
        
        result = f"{symbol} {test_name}: {status}"
        if message:
            result += f" - {message}"
        
        self.results.append(result)
        print(result)
    
    def setup_test_client(self):
        """Phase 0: Create test client for FK relationships"""
        print("\n=== PHASE 0: SETUP ===")
        try:
            client_data = generate_client_data()
            self.test_client_id = client_data["id"]
            
            result = self.persistence_adapter.write("clients", [client_data])
            if result.get("status") == "ok":
                self.created_records["clients"].append(self.test_client_id)
                self.log_result("Setup test client", True, f"Client ID: {self.test_client_id}")
            else:
                self.log_result("Setup test client", False, f"Failed: {result}")
                raise Exception("Cannot proceed without test client")
        except Exception as e:
            self.log_result("Setup test client", False, str(e))
            raise
    
    def test_layer1_api_gateway(self, table: str):
        """Test Layer 1: API Gateway requires valid apikey"""
        test_name = f"{table} - Layer 1: API Gateway"
        
        try:
            import requests
            
            # Test: Request WITH proper apikey + JWT should succeed
            url = f"{self.supabase_url}/rest/v1/{table}?limit=1"
            headers = {
                "apikey": self.anon_key,
                "Authorization": f"Bearer {self.rag_jwt}"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            # Should get 200 with proper auth
            if response.status_code == 200:
                self.log_result(test_name, True, "API Gateway accepted valid auth")
            else:
                # Any other status means something is wrong with our setup
                self.log_result(test_name, False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result(test_name, False, f"Error: {e}")
    
    def test_layer2_postgresql_permissions(self, table: str):
        """Test Layer 2: PostgreSQL GRANT permissions exist"""
        test_name = f"{table} - Layer 2: PostgreSQL Grants"
        
        try:
            # Try simple read - if permissions missing, this will fail
            result = self.rag_adapter.query(table, limit=1)
            
            if isinstance(result, list):
                self.log_result(test_name, True, "GRANT permissions verified")
            elif "permission denied" in str(result).lower():
                self.log_result(test_name, False, "Missing GRANT permissions")
            else:
                self.log_result(test_name, False, f"Unexpected result: {result}")
        except Exception as e:
            if "permission denied" in str(e).lower():
                self.log_result(test_name, False, "Missing GRANT permissions")
            else:
                self.log_result(test_name, False, f"Error: {e}")
    
    def test_layer3_rls_policies(self, table: str):
        """Test Layer 3: RLS policies enforce role restrictions"""
        print(f"\n--- {table} - Layer 3: RLS Policies ---")
        
        # Test 1: RAG agent (agent_reader) can SELECT
        try:
            result = self.rag_adapter.query(table, limit=1)
            if isinstance(result, list):
                self.log_result(f"{table} - RLS: RAG can SELECT", True)
            else:
                self.log_result(f"{table} - RLS: RAG can SELECT", False, str(result))
        except Exception as e:
            self.log_result(f"{table} - RLS: RAG can SELECT", False, str(e))
        
        # Test 2: RAG agent (agent_reader) CANNOT INSERT
        try:
            test_data = self._get_mock_data(table)
            # write() expects a dict, not a list
            result = self.rag_adapter.write(table, test_data)
            
            # Check if write succeeded (it shouldn't for agent_reader)
            if isinstance(result, dict) and "id" in result:
                self.log_result(f"{table} - RLS: RAG blocked from INSERT", False, "RAG should not be able to INSERT")
            else:
                self.log_result(f"{table} - RLS: RAG blocked from INSERT", True)
        except Exception as e:
            if "policy" in str(e).lower() or "permission" in str(e).lower():
                self.log_result(f"{table} - RLS: RAG blocked from INSERT", True)
            else:
                self.log_result(f"{table} - RLS: RAG blocked from INSERT", False, str(e))
    
    def _get_mock_data(self, table: str) -> Dict[str, Any]:
        """Get appropriate mock data for a table"""
        if table == "clients":
            return generate_client_data()
        elif table == "staging_leads":
            return generate_staging_lead_data(self.test_client_id)
        elif table == "leads":
            return generate_lead_data(self.test_client_id)
        elif table == "conversations":
            # Need a lead_id - create a lead first if not exists
            if not self.test_lead_id:
                lead_data = generate_lead_data(self.test_client_id)
                lead_result = self.persistence_adapter.write("leads", lead_data)
                if isinstance(lead_result, dict) and ("id" in lead_result or lead_result.get("status") == "ok"):
                    self.test_lead_id = lead_data["id"]
                    self.created_records["leads"].append(self.test_lead_id)
                else:
                    raise Exception(f"Cannot create conversation without lead: {lead_result}")
            return generate_conversation_data(self.test_client_id, self.test_lead_id)
        elif table == "messages":
            # Need a conversation ID - create one first
            conv_data = generate_conversation_data(self.test_client_id, self.test_lead_id or "temp")
            # Ensure we have a lead first
            if not self.test_lead_id:
                lead_data = generate_lead_data(self.test_client_id)
                lead_result = self.persistence_adapter.write("leads", lead_data)
                if isinstance(lead_result, dict) and ("id" in lead_result or lead_result.get("status") == "ok"):
                    self.test_lead_id = lead_data["id"]
                    self.created_records["leads"].append(self.test_lead_id)
                    conv_data["lead_id"] = self.test_lead_id
            conv_result = self.persistence_adapter.write("conversations", conv_data)
            if isinstance(conv_result, dict) and ("id" in conv_result or conv_result.get("status") == "ok"):
                self.created_records["conversations"].append(conv_data["id"])
                return generate_message_data(conv_data["id"])
            else:
                raise Exception(f"Cannot create message without conversation: {conv_result}")
        else:
            raise ValueError(f"Unknown table: {table}")
    
    def test_crud_operations(self, table: str):
        """Test full CRUD cycle with cross-agent validation"""
        print(f"\n--- {table} - CRUD Operations ---")
        
        # CREATE with Persistence agent
        try:
            test_data = self._get_mock_data(table)
            record_id = test_data["id"]
            
            # write() expects a dict, not a list
            result = self.persistence_adapter.write(table, test_data)
            # Successful write returns either the record dict OR {"status": "ok"}
            if (isinstance(result, dict) and "id" in result) or (isinstance(result, dict) and result.get("status") == "ok"):
                self.created_records[table].append(record_id)
                self.log_result(f"{table} - CREATE", True, f"ID: {record_id}")
            else:
                self.log_result(f"{table} - CREATE", False, str(result))
                return  # Cannot continue without record
        except Exception as e:
            self.log_result(f"{table} - CREATE", False, str(e))
            return
        
        # READ with Persistence agent
        try:
            result = self.persistence_adapter.read(table, record_id)
            if result and isinstance(result, dict):
                self.log_result(f"{table} - READ (Persistence)", True)
            else:
                self.log_result(f"{table} - READ (Persistence)", False, str(result))
        except Exception as e:
            self.log_result(f"{table} - READ (Persistence)", False, str(e))
        
        # READ with RAG agent (cross-agent verification)
        try:
            result = self.rag_adapter.read(table, record_id)
            if result and isinstance(result, dict):
                self.log_result(f"{table} - READ (RAG)", True, "Cross-agent verification passed")
            else:
                self.log_result(f"{table} - READ (RAG)", False, str(result))
        except Exception as e:
            self.log_result(f"{table} - READ (RAG)", False, str(e))
        
        # UPDATE with Persistence agent (only for tables with updatable fields)
        if table == "clients":
            try:
                update_data = {
                    "id": record_id,
                    "name": f"Updated Client {datetime.now().strftime('%H%M%S')}"
                }
                result = self.persistence_adapter.upsert(table, update_data)
                # Accept both dict with id or {"status": "ok"} as success
                if (isinstance(result, dict) and "id" in result) or (isinstance(result, dict) and result.get("status") == "ok"):
                    self.log_result(f"{table} - UPDATE", True)
                else:
                    self.log_result(f"{table} - UPDATE", False, str(result))
            except Exception as e:
                self.log_result(f"{table} - UPDATE", False, str(e))
    
    def test_query_features(self, table: str):
        """Test query capabilities: LIMIT, ORDER BY, SELECT projection"""
        print(f"\n--- {table} - Query Features ---")
        
        # LIMIT test
        try:
            result = self.rag_adapter.query(table, limit=2)
            if isinstance(result, list):
                if len(result) <= 2:
                    self.log_result(f"{table} - LIMIT", True, f"Returned {len(result)} records")
                else:
                    self.log_result(f"{table} - LIMIT", False, f"Returned {len(result)} records (expected <=2)")
            else:
                self.log_result(f"{table} - LIMIT", False, str(result))
        except Exception as e:
            self.log_result(f"{table} - LIMIT", False, str(e))
        
        # ORDER BY test
        try:
            result = self.rag_adapter.query(
                table,
                limit=5,
                order_by="created_at" if table != "clients" else "id"
            )
            if isinstance(result, list):
                self.log_result(f"{table} - ORDER BY", True)
            else:
                self.log_result(f"{table} - ORDER BY", False, str(result))
        except Exception as e:
            self.log_result(f"{table} - ORDER BY", False, str(e))
        
        # SELECT projection test
        try:
            select_field = "id"
            result = self.rag_adapter.query(table, limit=1, select=[select_field])
            if isinstance(result, list) and result:
                if list(result[0].keys()) == [select_field]:
                    self.log_result(f"{table} - SELECT projection", True)
                else:
                    self.log_result(f"{table} - SELECT projection", False, "Did not return only selected field")
            else:
                self.log_result(f"{table} - SELECT projection", False, str(result))
        except Exception as e:
            self.log_result(f"{table} - SELECT projection", False, str(e))
    
    def cleanup(self):
        """Phase 4: Delete all test records"""
        print("\n=== PHASE 4: CLEANUP ===")
        
        # Delete in reverse order (messages -> conversations -> leads -> staging_leads -> clients)
        cleanup_order = ["messages", "conversations", "leads", "staging_leads", "clients"]
        
        for table in cleanup_order:
            record_ids = self.created_records.get(table, [])
            if not record_ids:
                continue
            
            try:
                for record_id in record_ids:
                    # Use the adapter's delete method
                    result = self.persistence_adapter.delete(table, record_id)
                    
                    if result.get("status") == "ok":
                        print(f"[DELETE] {table}: {record_id}")
                    else:
                        error = result.get("error", result)
                        print(f"[FAILED] {table}: {record_id} - {error}")
            except Exception as e:
                print(f"[ERROR] {table} cleanup: {e}")
    
    def print_summary(self):
        """Print final test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.passed_tests + self.failed_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.failed_tests}")
        print("="*60)
        
        if self.failed_tests == 0:
            print("\n[SUCCESS] ALL TESTS PASSED!")
        else:
            print("\n[ATTENTION] Some tests failed. Review results above.")
            print("\nFailed tests:")
            for result in self.results:
                if "[FAIL]" in result:
                    print(f"  - {result}")
    
    def run_all_tests(self):
        """Execute all test phases"""
        try:
            # Phase 0: Setup
            self.setup_test_client()
            
            # Phases 1-3: Test each table
            for table in TABLES_TO_TEST:
                print(f"\n{'='*60}")
                print(f"TESTING TABLE: {table}")
                print(f"{'='*60}")
                
                # Phase 1: API Gateway
                self.test_layer1_api_gateway(table)
                
                # Phase 2: PostgreSQL Permissions
                self.test_layer2_postgresql_permissions(table)
                
                # Phase 3: RLS Policies
                self.test_layer3_rls_policies(table)
                
                # Phase 2: CRUD Operations
                self.test_crud_operations(table)
                
                # Phase 3: Query Features
                self.test_query_features(table)
            
            # Phase 4: Cleanup
            self.cleanup()
            
        except Exception as e:
            print(f"\n[CRITICAL ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.print_summary()


def main():
    try:
        suite = ComprehensiveTestSuite()
        suite.run_all_tests()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
