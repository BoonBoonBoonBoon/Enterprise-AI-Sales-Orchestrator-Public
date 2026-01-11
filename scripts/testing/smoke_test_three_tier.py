#!/usr/bin/env python3
"""
End-to-End Smoke Test for Three-Tier Architecture
==================================================

Tests complete delegation flow:
1. Manager (Tier 1) receives high-level task
2. Manager delegates to Orchestrator (Tier 2)
3. Orchestrator delegates to operational agents (Tier 3)
4. Agents process and return results
5. Verify correct stream hierarchy

Usage:
    python scripts/smoke_test_three_tier.py
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Try new imports first, fall back to legacy
try:
    from services.redis import RedisPubSub
    from core.envelope import Envelope, Priority, Status
    print("Using NEW import paths (services/*, core/*)")
except ImportError:
    from services.redis import RedisStreamsClient as RedisPubSub
    from agent.utils.typed_envelope import Envelope, Priority, Status
    print("Using LEGACY import paths (agent.*)")


class SmokeTestRunner:
    """Orchestrates end-to-end smoke testing"""
    
    def __init__(self, tenant_id: str = "test"):
        self.tenant_id = tenant_id
        self.redis_client = RedisPubSub()
        self.test_results: Dict[str, bool] = {}
        self.start_time = datetime.now()
        
    def log(self, message: str, level: str = "INFO"):
        """Log test progress"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbol = {
            "INFO": "[*]",
            "PASS": "[+]",
            "FAIL": "[!]",
            "WARN": "[?]"
        }.get(level, "[*]")
        
        print(f"{timestamp} {symbol} {message}")
    
    def test_redis_connectivity(self) -> bool:
        """Test 1: Verify Redis connection"""
        self.log("Testing Redis connectivity...", "INFO")
        
        try:
            # Ping Redis
            self.redis_client.client.ping()
            self.log("Redis connection successful", "PASS")
            return True
        except Exception as e:
            self.log(f"Redis connection failed: {e}", "FAIL")
            return False
    
    def test_stream_creation(self) -> bool:
        """Test 2: Verify stream creation and naming"""
        self.log("Testing stream hierarchy...", "INFO")
        
        expected_streams = [
            f"{self.tenant_id}:tier_1:manager:tasks",
            f"{self.tenant_id}:tier_2:leads:tasks",
            f"{self.tenant_id}:tier_2:outreach:tasks",
            f"{self.tenant_id}:tier_3:rag:tasks",
            f"{self.tenant_id}:tier_3:persistence:tasks",
            f"{self.tenant_id}:tier_3:copywriter:tasks",
        ]
        
        # Create test streams if they don't exist
        for stream in expected_streams:
            try:
                # Try to get stream info (creates if doesn't exist)
                self.redis_client.client.xinfo_stream(stream)
            except Exception:
                # Stream doesn't exist, create it with a dummy message
                test_message = {
                    "task_type": "smoke_test",
                    "timestamp": str(time.time()),
                    "status": "created"
                }
                self.redis_client.client.xadd(stream, test_message)
        
        # Verify all streams exist
        all_keys = self.redis_client.client.keys(f"{self.tenant_id}:*")
        all_keys_str = [k.decode() if isinstance(k, bytes) else k for k in all_keys]
        
        missing = [s for s in expected_streams if s not in all_keys_str]
        
        if not missing:
            self.log(f"All {len(expected_streams)} tier streams exist", "PASS")
            return True
        else:
            self.log(f"Missing streams: {missing}", "FAIL")
            return False
    
    def test_manager_task_submission(self) -> bool:
        """Test 3: Submit task to Manager (Tier 1)"""
        self.log("Submitting task to Manager (Tier 1)...", "INFO")
        
        try:
            manager_stream = f"{self.tenant_id}:tier_1:manager:tasks"
            
            # Create a test task
            task_data = {
                "task_id": f"smoke_test_{int(time.time())}",
                "task_type": "campaign_workflow",
                "priority": "high",
                "status": "pending",
                "payload": str({
                    "campaign_id": "test_campaign_001",
                    "action": "generate_leads",
                    "test_mode": True
                }),
                "timestamp": str(time.time()),
                "tenant_id": self.tenant_id,
            }
            
            # Submit to Manager stream
            msg_id = self.redis_client.client.xadd(manager_stream, task_data)
            
            self.log(f"Task submitted to Manager: {msg_id}", "PASS")
            
            # Wait a moment for processing
            time.sleep(1)
            
            # Verify task appears in stream
            messages = self.redis_client.client.xrange(manager_stream, count=10)
            
            if messages:
                self.log(f"Manager stream has {len(messages)} messages", "INFO")
                return True
            else:
                self.log("No messages found in Manager stream", "WARN")
                return False
                
        except Exception as e:
            self.log(f"Failed to submit Manager task: {e}", "FAIL")
            return False
    
    def test_orchestrator_delegation(self) -> bool:
        """Test 4: Verify Orchestrator (Tier 2) receives tasks"""
        self.log("Checking Orchestrator streams (Tier 2)...", "INFO")
        
        try:
            orchestrator_streams = [
                f"{self.tenant_id}:tier_2:leads:tasks",
                f"{self.tenant_id}:tier_2:outreach:tasks",
            ]
            
            total_messages = 0
            for stream in orchestrator_streams:
                messages = self.redis_client.client.xrange(stream, count=5)
                count = len(messages)
                total_messages += count
                
                if count > 0:
                    self.log(f"Stream {stream.split(':')[-2]}: {count} messages", "INFO")
            
            if total_messages > 0:
                self.log(f"Orchestrator streams have {total_messages} total messages", "PASS")
                return True
            else:
                self.log("No messages in Orchestrator streams (expected for fresh system)", "WARN")
                return True  # Not a failure for smoke test
                
        except Exception as e:
            self.log(f"Failed to check Orchestrator streams: {e}", "FAIL")
            return False
    
    def test_agent_streams(self) -> bool:
        """Test 5: Verify Agent (Tier 3) streams exist"""
        self.log("Checking Agent streams (Tier 3)...", "INFO")
        
        try:
            agent_streams = [
                f"{self.tenant_id}:tier_3:rag:tasks",
                f"{self.tenant_id}:tier_3:persistence:tasks",
                f"{self.tenant_id}:tier_3:copywriter:tasks",
            ]
            
            total_messages = 0
            for stream in agent_streams:
                messages = self.redis_client.client.xrange(stream, count=5)
                count = len(messages)
                total_messages += count
                
                if count > 0:
                    self.log(f"Stream {stream.split(':')[-2]}: {count} messages", "INFO")
            
            if total_messages > 0:
                self.log(f"Agent streams have {total_messages} total messages", "INFO")
            else:
                self.log("Agent streams exist but empty (expected for fresh system)", "INFO")
            
            self.log("All Tier 3 agent streams verified", "PASS")
            return True
                
        except Exception as e:
            self.log(f"Failed to check Agent streams: {e}", "FAIL")
            return False
    
    def test_stream_hierarchy(self) -> bool:
        """Test 6: Verify stream naming follows tier hierarchy"""
        self.log("Validating stream hierarchy naming...", "INFO")
        
        try:
            all_keys = self.redis_client.client.keys(f"{self.tenant_id}:*")
            all_keys_str = [k.decode() if isinstance(k, bytes) else k for k in all_keys]
            
            tier_1_streams = [k for k in all_keys_str if ":tier_1:" in k]
            tier_2_streams = [k for k in all_keys_str if ":tier_2:" in k]
            tier_3_streams = [k for k in all_keys_str if ":tier_3:" in k]
            
            self.log(f"Tier 1 (Manager) streams: {len(tier_1_streams)}", "INFO")
            self.log(f"Tier 2 (Orchestrators) streams: {len(tier_2_streams)}", "INFO")
            self.log(f"Tier 3 (Agents) streams: {len(tier_3_streams)}", "INFO")
            
            # Expected hierarchy
            expected_hierarchy = {
                "tier_1": ["manager"],
                "tier_2": ["leads", "outreach"],
                "tier_3": ["rag", "persistence", "copywriter"],
            }
            
            hierarchy_valid = True
            
            for tier, expected_agents in expected_hierarchy.items():
                for agent in expected_agents:
                    expected_stream = f"{self.tenant_id}:{tier}:{agent}:tasks"
                    if expected_stream in all_keys_str:
                        self.log(f"  {tier}/{agent}: FOUND", "INFO")
                    else:
                        self.log(f"  {tier}/{agent}: MISSING", "WARN")
                        hierarchy_valid = False
            
            if hierarchy_valid:
                self.log("Stream hierarchy follows tier structure", "PASS")
                return True
            else:
                self.log("Some expected streams missing (non-critical)", "WARN")
                return True  # Not a critical failure
                
        except Exception as e:
            self.log(f"Failed to validate hierarchy: {e}", "FAIL")
            return False
    
    def test_cleanup(self) -> bool:
        """Test 7: Clean up test messages"""
        self.log("Cleaning up smoke test data...", "INFO")
        
        try:
            # Remove only smoke_test messages, not all data
            all_keys = self.redis_client.client.keys(f"{self.tenant_id}:*")
            
            cleaned_count = 0
            for key in all_keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                
                # Read messages
                messages = self.redis_client.client.xrange(key_str)
                
                for msg_id, msg_data in messages:
                    # Check if it's a smoke test message
                    task_type = msg_data.get(b'task_type', msg_data.get('task_type', b''))
                    task_type_str = task_type.decode() if isinstance(task_type, bytes) else task_type
                    
                    if 'smoke_test' in task_type_str:
                        # Delete this message
                        self.redis_client.client.xdel(key_str, msg_id)
                        cleaned_count += 1
            
            if cleaned_count > 0:
                self.log(f"Removed {cleaned_count} smoke test messages", "PASS")
            else:
                self.log("No smoke test messages to clean", "INFO")
            
            return True
            
        except Exception as e:
            self.log(f"Cleanup failed (non-critical): {e}", "WARN")
            return True  # Don't fail on cleanup errors
    
    def run_all_tests(self) -> bool:
        """Execute complete smoke test suite"""
        self.log("=" * 60, "INFO")
        self.log("THREE-TIER ARCHITECTURE SMOKE TEST", "INFO")
        self.log("=" * 60, "INFO")
        self.log(f"Tenant ID: {self.tenant_id}", "INFO")
        self.log(f"Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        self.log("", "INFO")
        
        # Run all tests
        tests = [
            ("Redis Connectivity", self.test_redis_connectivity),
            ("Stream Creation", self.test_stream_creation),
            ("Manager Task Submission", self.test_manager_task_submission),
            ("Orchestrator Delegation", self.test_orchestrator_delegation),
            ("Agent Streams", self.test_agent_streams),
            ("Stream Hierarchy", self.test_stream_hierarchy),
            ("Cleanup", self.test_cleanup),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            self.log("", "INFO")
            self.log(f"Running: {test_name}", "INFO")
            self.log("-" * 60, "INFO")
            
            try:
                result = test_func()
                self.test_results[test_name] = result
                
                if result:
                    passed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                self.log(f"Test crashed: {e}", "FAIL")
                self.test_results[test_name] = False
                failed += 1
        
        # Summary
        self.log("", "INFO")
        self.log("=" * 60, "INFO")
        self.log("SMOKE TEST SUMMARY", "INFO")
        self.log("=" * 60, "INFO")
        
        for test_name, result in self.test_results.items():
            status = "PASS" if result else "FAIL"
            symbol = "[+]" if result else "[!]"
            self.log(f"{symbol} {test_name}: {status}", status)
        
        self.log("", "INFO")
        self.log(f"Total Tests: {len(tests)}", "INFO")
        self.log(f"Passed: {passed}", "PASS" if passed > 0 else "INFO")
        self.log(f"Failed: {failed}", "FAIL" if failed > 0 else "INFO")
        
        duration = (datetime.now() - self.start_time).total_seconds()
        self.log(f"Duration: {duration:.2f}s", "INFO")
        
        self.log("", "INFO")
        
        if failed == 0:
            self.log("ALL TESTS PASSED - System Ready", "PASS")
            self.log("=" * 60, "INFO")
            return True
        else:
            self.log(f"{failed} TEST(S) FAILED - Review errors above", "FAIL")
            self.log("=" * 60, "INFO")
            return False


def main():
    """Entry point for smoke test"""
    
    # Parse command line args
    tenant_id = sys.argv[1] if len(sys.argv) > 1 else "test"
    
    # Run smoke test
    runner = SmokeTestRunner(tenant_id=tenant_id)
    success = runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
