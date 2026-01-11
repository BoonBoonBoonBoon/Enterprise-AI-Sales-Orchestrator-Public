"""
Start All Production Consumers

Starts LeadsOrchestrator, RAG, and Persistence consumers in separate terminals.
Use Ctrl+C to stop all consumers.
"""
import os
import sys
import subprocess
import time
from typing import List

# ANSI color codes for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_color(message: str, color: str):
    """Print colored message."""
    print(f"{color}{message}{RESET}")


def start_consumer_in_background(module_path: str, name: str, python_executable: str, env: dict) -> subprocess.Popen:
    """
    Start a consumer in the background.
    
    Args:
        module_path: Python module path (e.g., 'tiers.tier_2.leads_orchestrator.consumer')
        name: Display name for the consumer
    
    Returns:
        Process handle
    """
    print_color(f"\n🚀 Starting {name}...", BLUE)
    
    # Start process in new window (Windows) using venv python
    if sys.platform == "win32":
        process = subprocess.Popen(
            [python_executable, '-m', module_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=env
        )
    else:
        # Unix-like systems - use nohup or screen
        process = subprocess.Popen(
            [python_executable, '-m', module_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )
    
    print_color(f"✅ {name} started (PID: {process.pid})", GREEN)
    return process


def main():
    """Start all consumers."""
    print_color("\n" + "="*80, BLUE)
    print_color("  🎯 STARTING ALL PRODUCTION CONSUMERS", BLUE)
    print_color("="*80 + "\n", BLUE)
    
    consumers = [
        ('tiers.tier_2.leads_orchestrator.consumer', 'LeadsOrchestrator'),
        ('tiers.tier_3.rag_agent.consumer', 'RAG Agent'),
        ('tiers.tier_3.persistence_agent.consumer', 'Persistence Agent'),
    ]

    # Prefer the project venv python; fallback to current interpreter
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_python = os.path.join(project_root, '.venv', 'Scripts', 'python.exe')
    python_executable = venv_python if os.path.exists(venv_python) else sys.executable

    # Inherit current env and ensure TENANT_ID is set
    base_env = os.environ.copy()
    base_env.setdefault('TENANT_ID', 'agentic-dev')
    
    processes: List[subprocess.Popen] = []
    
    try:
        # Start all consumers
        for module_path, name in consumers:
            try:
                process = start_consumer_in_background(module_path, name, python_executable, base_env)
                processes.append(process)
                time.sleep(2)  # Give each consumer time to initialize
            except Exception as e:
                print_color(f"❌ Failed to start {name}: {str(e)}", RED)
        
        print_color("\n" + "="*80, GREEN)
        print_color(f"  ✅ {len(processes)}/{len(consumers)} CONSUMERS STARTED", GREEN)
        print_color("="*80, GREEN)
        
        print_color("\n💡 Consumers are running in separate windows", YELLOW)
        print_color("💡 Check each window for consumer logs", YELLOW)
        print_color("\n📋 To verify all systems:", YELLOW)
        print_color("   python scripts/verify_production_ready.py", YELLOW)
        print_color("\n🧪 To run E2E tests:", YELLOW)
        print_color("   pytest tests/integration/test_leads_orchestrator_e2e.py -v -s --no-cov", YELLOW)
        
        print_color("\n⏸️  Press Ctrl+C to stop all consumers", YELLOW)
        
        # Keep script running
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print_color("\n\n🛑 Stopping all consumers...", YELLOW)
        
        for process in processes:
            try:
                process.terminate()
                print_color(f"✅ Stopped process {process.pid}", GREEN)
            except Exception as e:
                print_color(f"⚠️  Error stopping process {process.pid}: {str(e)}", RED)
        
        print_color("\n✅ All consumers stopped", GREEN)
        sys.exit(0)


if __name__ == "__main__":
    main()
