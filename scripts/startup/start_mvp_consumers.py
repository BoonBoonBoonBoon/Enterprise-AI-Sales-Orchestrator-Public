"""
Start MVP consumers (Manager, Leads, RAG)

Usage:
    python start_mvp_consumers.py
"""

import subprocess
import sys
import os
import signal
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[INFO] Loaded environment variables from .env")
except ImportError:
    print("[WARNING] python-dotenv not installed, assuming env vars are set")

# Get project root
project_root = Path(__file__).parent

# Set UTF-8 encoding for output
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# MVP Consumers only
CONSUMERS = [
    {
        "name": "Manager",
        "module": "tiers.tier_1.manager.consumer",
        "description": "Tier 1: Receives external requests, delegates to orchestrators"
    },
    {
        "name": "Leads Orchestrator",
        "module": "tiers.tier_2.leads_orchestrator.consumer",
        "description": "Tier 2: Finds and qualifies leads"
    },
    {
        "name": "RAG Agent",
        "module": "tiers.tier_3.rag_agent.consumer",
        "description": "Tier 3: Enriches data with external sources"
    },
]

processes = []


def start_consumer(name: str, module: str, description: str):
    """Start a consumer process"""
    
    print(f"\n{'='*60}")
    print(f"Starting: {name}")
    print(f"Description: {description}")
    print(f"Module: {module}")
    print(f"{'='*60}\n")
    
    try:
        # Use venv python
        venv_python = project_root / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            venv_python = sys.executable
        
        # Start process with output (using -m to run as module)
        process = subprocess.Popen(
            [str(venv_python), "-m", module],
            cwd=str(project_root),
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        
        processes.append((name, process))
        print(f"[OK] Started {name} (PID: {process.pid})\n")
        
        return process
        
    except Exception as e:
        print(f"[ERROR] Failed to start {name}: {e}\n")
        return None


def handle_interrupt(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n" + "="*60)
    print("Shutting down MVP consumers...")
    print("="*60 + "\n")
    
    for name, process in processes:
        if process and process.poll() is None:
            print(f"Stopping {name} (PID: {process.pid})...")
            process.terminate()
            try:
                process.wait(timeout=5)
                print(f"[OK] Stopped {name}")
            except subprocess.TimeoutExpired:
                print(f"[WARNING] Killing {name} (didn't stop gracefully)")
                process.kill()
    
    print("\n[OK] MVP consumers shut down\n")
    sys.exit(0)


def main():
    """Start MVP consumers"""
    print("\n" + "="*60)
    print("AGENTIC SYSTEM - MVP CONSUMERS")
    print("="*60)
    print("\nTier 1: Manager")
    print("Tier 2: Leads Orchestrator")
    print("Tier 3: RAG Agent")
    print("\n" + "="*60 + "\n")
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, handle_interrupt)
    
    # Start consumers
    for consumer in CONSUMERS:
        start_consumer(
            name=consumer["name"],
            module=consumer["module"],
            description=consumer["description"]
        )
    
    # Wait for any process to finish
    try:
        while True:
            for name, process in processes:
                if process.poll() is not None:
                    print(f"\n[ERROR] {name} exited with code {process.returncode}")
            
            import time
            time.sleep(1)
            
    except KeyboardInterrupt:
        handle_interrupt(None, None)


if __name__ == "__main__":
    main()
