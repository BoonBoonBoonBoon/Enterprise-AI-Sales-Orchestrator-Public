"""
Production Environment Startup & Health Check Script

Verifies all components are running before E2E tests:
1. Docker services (Redis)
2. Consumer processes (LeadsOrchestrator, RAG, Persistence)
3. Stream connectivity
4. Consumer group registration

Usage:
    python scripts/verify_production_ready.py
"""
import os
import sys
import time
import subprocess
from typing import List, Tuple, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.redis.client import RedisStreamsClient


class ProductionHealthCheck:
    """Health check for production-ready system."""
    
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.tenant_id = 'agentic-dev'
        self.redis_client: Optional[RedisStreamsClient] = None
        
        self.checks_passed = 0
        self.checks_failed = 0
    
    def print_header(self, title: str):
        """Print section header."""
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}")
    
    def print_check(self, name: str, passed: bool, details: str = ""):
        """Print check result."""
        symbol = "✅" if passed else "❌"
        status = "PASS" if passed else "FAIL"
        print(f"{symbol} [{status}] {name}")
        if details:
            print(f"         {details}")
        
        if passed:
            self.checks_passed += 1
        else:
            self.checks_failed += 1
    
    def check_docker_services(self) -> bool:
        """Check if Docker services are running."""
        self.print_header("1. Docker Services")
        
        try:
            # Check if docker compose is available
            result = subprocess.run(
                ['docker', 'compose', 'ps', '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Check for Redis service
                if 'redis' in result.stdout.lower():
                    self.print_check("Docker Compose", True, "Services are running")
                    return True
                else:
                    self.print_check("Docker Compose", False, "Redis service not found")
                    print("\n💡 Start with: docker compose up -d")
                    return False
            else:
                self.print_check("Docker Compose", False, "Could not get service status")
                return False
        
        except FileNotFoundError:
            self.print_check("Docker", False, "Docker not installed or not in PATH")
            return False
        except subprocess.TimeoutExpired:
            self.print_check("Docker", False, "Docker command timed out")
            return False
        except Exception as e:
            self.print_check("Docker", False, f"Error: {str(e)}")
            return False
    
    def check_redis_connectivity(self) -> bool:
        """Check Redis connection."""
        self.print_header("2. Redis Connectivity")
        
        try:
            self.redis_client = RedisStreamsClient(url=self.redis_url, namespace=self.tenant_id)
            self.redis_client.client.ping()
            
            # Get Redis info
            info = self.redis_client.client.info('server')
            redis_version = info.get('redis_version', 'unknown')
            
            self.print_check("Redis Connection", True, f"Version {redis_version}")
            return True
        
        except Exception as e:
            self.print_check("Redis Connection", False, f"Error: {str(e)}")
            print("\n💡 Ensure Redis is running: docker compose up redis -d")
            return False
    
    def check_stream_infrastructure(self) -> bool:
        """Check if streams and consumer groups are set up."""
        self.print_header("3. Stream Infrastructure")
        
        if not self.redis_client:
            self.print_check("Stream Check", False, "Redis client not available")
            return False
        
        streams_to_check = [
            (f"{self.tenant_id}:orchestrators:leads:tasks", "leads-workers"),
            (f"{self.tenant_id}:agents:rag:tasks", "rag-workers"),
            (f"{self.tenant_id}:agents:persistence:tasks", "persistence-workers"),
        ]
        
        all_good = True
        
        for stream, group in streams_to_check:
            try:
                # Check if stream exists
                length = self.redis_client.client.xlen(stream)
                
                # Check if consumer group exists
                groups = self.redis_client.client.xinfo_groups(stream)
                group_names = [
                    g['name'].decode('utf-8') if isinstance(g['name'], bytes) else g['name']
                    for g in groups
                ]
                
                if group in group_names:
                    self.print_check(
                        f"Stream: {stream.split(':')[-2]}:{stream.split(':')[-1]}",
                        True,
                        f"Group '{group}' active, {length} messages"
                    )
                else:
                    self.print_check(
                        f"Stream: {stream.split(':')[-2]}:{stream.split(':')[-1]}",
                        False,
                        f"Group '{group}' not found. Consumer not started?"
                    )
                    all_good = False
            
            except Exception as e:
                self.print_check(
                    f"Stream: {stream.split(':')[-2]}:{stream.split(':')[-1]}",
                    False,
                    f"Not initialized (consumer not running)"
                )
                all_good = False
        
        if not all_good:
            print("\n💡 Start consumers:")
            print("   python -m tiers.tier_2.leads_orchestrator.consumer")
            print("   python -m tiers.tier_3.rag_agent.consumer")
            print("   python -m tiers.tier_3.persistence_agent.consumer")
        
        return all_good
    
    def check_consumer_processes(self) -> bool:
        """Check if consumer processes are running (Windows)."""
        self.print_header("4. Consumer Processes")
        
        try:
            # Use tasklist on Windows to find Python processes
            result = subprocess.run(
                ['powershell', '-Command', 'Get-Process python* | Select-Object Id, ProcessName, CommandLine | ConvertTo-Json'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout:
                import json
                try:
                    processes = json.loads(result.stdout)
                    if not isinstance(processes, list):
                        processes = [processes]
                    
                    # Look for consumer processes
                    consumers_to_find = [
                        'leads_orchestrator.consumer',
                        'rag_agent.consumer',
                        'persistence_agent.consumer'
                    ]
                    
                    found_consumers = []
                    for proc in processes:
                        cmd_line = proc.get('CommandLine', '') or ''
                        for consumer in consumers_to_find:
                            if consumer in cmd_line:
                                found_consumers.append(consumer)
                    
                    for consumer in consumers_to_find:
                        if consumer in found_consumers:
                            self.print_check(f"Consumer: {consumer}", True, "Process running")
                        else:
                            self.print_check(f"Consumer: {consumer}", False, "Process not found")
                    
                    return len(found_consumers) == len(consumers_to_find)
                
                except json.JSONDecodeError:
                    self.print_check("Process Check", False, "Could not parse process list")
                    return False
            else:
                self.print_check("Process Check", False, "Could not get process list")
                return False
        
        except Exception as e:
            self.print_check("Process Check", False, f"Error: {str(e)}")
            print("💡 Manual check: Use Task Manager or `ps aux | grep consumer`")
            return False
    
    def run_all_checks(self) -> bool:
        """Run all health checks."""
        print("\n" + "="*80)
        print("  🏥 PRODUCTION ENVIRONMENT HEALTH CHECK")
        print("="*80)
        
        # Run checks
        docker_ok = self.check_docker_services()
        redis_ok = self.check_redis_connectivity()
        streams_ok = self.check_stream_infrastructure() if redis_ok else False
        processes_ok = self.check_consumer_processes()
        
        # Summary
        self.print_header("SUMMARY")
        print(f"✅ Passed: {self.checks_passed}")
        print(f"❌ Failed: {self.checks_failed}")
        
        all_ok = docker_ok and redis_ok and streams_ok
        
        if all_ok:
            print("\n🎉 ALL CRITICAL SYSTEMS ARE READY!")
            print("\n✨ You can now run E2E tests:")
            print("   pytest tests/integration/test_leads_orchestrator_e2e.py -v -s --no-cov")
            return True
        else:
            print("\n⚠️  SYSTEM NOT READY")
            print("\n📋 Action Items:")
            if not docker_ok:
                print("   1. Start Docker services: docker compose up -d")
            if not redis_ok:
                print("   2. Verify Redis is accessible")
            if not streams_ok:
                print("   3. Start consumer processes (see above)")
            
            print("\n💡 Once all checks pass, run E2E tests")
            return False
    
    def quick_test_send(self):
        """Send a quick test message to verify end-to-end."""
        if not self.redis_client:
            print("\n❌ Cannot send test - Redis not connected")
            return
        
        self.print_header("5. Quick Test Message")
        
        try:
            from uuid import uuid4
            from core.envelope import task, to_redis_fields, Priority
            
            task_stream = f"{self.tenant_id}:orchestrators:leads:tasks"
            
            envelope = task(
                source="health_check",
                task_id=f"health-{uuid4()}",
                payload={"goal": "Health check test", "action": "ping"},
                destination="leads_orchestrator",
                priority=Priority.LOW,
                tenant_id=self.tenant_id
            )
            
            redis_fields = to_redis_fields(envelope)
            msg_id = self.redis_client.xadd(task_stream, redis_fields)
            
            self.print_check("Test Message Sent", True, f"Message ID: {msg_id}")
            print("\n💡 Check orchestrator logs for processing confirmation")
        
        except Exception as e:
            self.print_check("Test Message", False, f"Error: {str(e)}")


def main():
    """Main entry point."""
    checker = ProductionHealthCheck()
    
    # Run all checks
    system_ready = checker.run_all_checks()
    
    # Optionally send test message if system is ready
    if system_ready:
        try:
            response = input("\n❓ Send a test message to orchestrator? (y/n): ")
            if response.lower() == 'y':
                checker.quick_test_send()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSkipping test message")
    
    # Exit with appropriate code
    sys.exit(0 if system_ready else 1)


if __name__ == "__main__":
    main()
