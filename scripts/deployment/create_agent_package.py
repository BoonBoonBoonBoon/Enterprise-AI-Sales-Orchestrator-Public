"""
Create agent package compatibility layer.
This script creates the entire agent/ package structure to map old imports to new structure.
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Define all directories to create
DIRS = [
    "agent",
    "agent/tools",
    "agent/tools/redis",
    "agent/tools/persistence",
    "agent/tools/persistence/adapters",
    "agent/tools/vector_db",
    "agent/tools/external_apis",
    "agent/utils",
    "agent/schemas",
    "agent/operational_agents",
    "agent/operational_agents/rag_agent",
    "agent/operational_agents/persistence_agent",
    "agent/orchestrators",
    "agent/orchestrators/control",
    "agent/manager",
    "agent/config",
    "agent/harness",
    "utils",
]

# Define all files to create with their content
FILES = {
    "agent/__init__.py": '''"""
Compatibility layer for agent.* imports.
Maps old import paths to new structure (core/, services/, tiers/).
"""

# Re-export core modules
from core import schemas, utils, envelope, observability, exceptions, harness, deep_agents

__all__ = [
    'schemas',
    'utils',
    'envelope',
    'observability',
    'exceptions',
    'harness',
    'deep_agents',
]
''',
    "agent/tools/__init__.py": '''"""Tools module compatibility layer."""
from services import redis, persistence, vector_db, external_apis

__all__ = ['redis', 'persistence', 'vector_db', 'external_apis']
''',
    "agent/tools/redis/__init__.py": '''"""Redis tools compatibility layer."""
from services.redis import *
''',
    "agent/tools/redis/client.py": '''"""Redis client compatibility layer."""
from services.redis.client import *
''',
    "agent/tools/redis/messages.py": '''"""Redis messages compatibility layer."""
from services.redis.messages import *
''',
    "agent/tools/persistence/__init__.py": '''"""Persistence tools compatibility layer."""
from services.persistence import *
''',
    "agent/tools/persistence/service.py": '''"""Persistence service compatibility layer."""
try:
    from services.persistence.service import *
except ImportError:
    pass
''',
    "agent/tools/persistence/adapters/__init__.py": '''"""Persistence adapters compatibility layer."""
try:
    from services.persistence.adapters import *
except ImportError:
    pass
''',
    "agent/tools/persistence/adapters/in_memory_adapter.py": '''"""In-memory adapter compatibility layer."""
try:
    from services.persistence.adapters.in_memory_adapter import *
except ImportError:
    pass
''',
    "agent/tools/vector_db/__init__.py": '''"""Vector DB tools compatibility layer."""
from services.vector_db import *
''',
    "agent/tools/vector_db/client.py": '''"""Vector DB client compatibility layer."""
from services.vector_db.client import *
''',
    "agent/tools/vector_db/embeddings.py": '''"""Vector DB embeddings compatibility layer."""
from services.vector_db.embeddings import *
''',
    "agent/tools/external_apis/__init__.py": '''"""External APIs tools compatibility layer."""
from services.external_apis import *
''',
    "agent/tools/external_apis/crunchbase.py": '''"""Crunchbase API compatibility layer."""
try:
    from services.external_apis.crunchbase import *
except ImportError:
    pass
''',
    "agent/tools/external_apis/linkedin.py": '''"""LinkedIn API compatibility layer."""
try:
    from services.external_apis.linkedin import *
except ImportError:
    pass
''',
    "agent/utils/__init__.py": '''"""Utils compatibility layer."""
from core.utils import *
''',
    "agent/utils/typed_envelope.py": '''"""Typed envelope compatibility layer."""
try:
    from core.schemas.typed_envelope import *
except ImportError:
    try:
        from core.envelope.envelope import *
    except ImportError:
        pass
''',
    "agent/utils/rate_limiter.py": '''"""Rate limiter compatibility layer."""
from core.utils.rate_limiter import *
''',
    "agent/utils/graceful_shutdown.py": '''"""Graceful shutdown compatibility layer."""
from core.utils.graceful_shutdown import *
''',
    "agent/utils/mock_leads.py": '''"""Mock leads compatibility layer."""
from core.utils.mock_leads import *
''',
    "agent/utils/tracing.py": '''"""Tracing compatibility layer."""
from core.utils.tracing import *
''',
    "agent/utils/workflow_progress.py": '''"""Workflow progress compatibility layer."""
from core.utils.workflow_progress import *
''',
    "agent/schemas/__init__.py": '''"""Schemas compatibility layer."""
from core.schemas import *
''',
    "agent/schemas/typed_envelope.py": '''"""Typed envelope schema compatibility layer."""
try:
    from core.schemas.typed_envelope import *
except ImportError:
    try:
        from core.envelope.envelope import *
    except ImportError:
        pass
''',
    "agent/operational_agents/__init__.py": '''"""Operational agents compatibility layer."""
try:
    from tiers.tier_3 import rag_agent, persistence_agent, copywriter_agent
except ImportError:
    pass
''',
    "agent/operational_agents/rag_agent/__init__.py": '''"""RAG agent compatibility layer."""
try:
    from tiers.tier_3.rag_agent import *
except ImportError:
    pass
''',
    "agent/operational_agents/rag_agent/rag_agent.py": '''"""RAG agent compatibility layer."""
try:
    from tiers.tier_3.rag_agent.rag_agent import *
except ImportError:
    pass
''',
    "agent/operational_agents/rag_agent/worker.py": '''"""RAG agent worker compatibility layer."""
try:
    from tiers.tier_3.rag_agent.worker import *
except ImportError:
    pass
''',
    "agent/operational_agents/persistence_agent/__init__.py": '''"""Persistence agent compatibility layer."""
try:
    from tiers.tier_3.persistence_agent import *
except ImportError:
    pass
''',
    "agent/operational_agents/persistence_agent/persistence_agent.py": '''"""Persistence agent compatibility layer."""
try:
    from tiers.tier_3.persistence_agent.persistence_agent import *
except ImportError:
    pass
''',
    "agent/operational_agents/factory.py": '''"""Operational agents factory compatibility layer."""
try:
    from tiers.tier_3.factory import *
except ImportError:
    pass
''',
    "agent/orchestrators/__init__.py": '''"""Orchestrators compatibility layer."""
try:
    from tiers.tier_2 import *
except ImportError:
    pass
''',
    "agent/orchestrators/workflow_manager.py": '''"""Workflow manager compatibility layer."""
try:
    from tiers.tier_2.leads_orchestrator.leads_orchestrator import *
except ImportError:
    pass
''',
    "agent/orchestrators/base_orchestrator.py": '''"""Base orchestrator compatibility layer."""
try:
    from tiers.tier_2.base_orchestrator import *
except ImportError:
    pass
''',
    "agent/orchestrators/control/__init__.py": '''"""Control orchestrators compatibility layer."""
try:
    from tiers.tier_2.control import *
except ImportError:
    pass
''',
    "agent/orchestrators/control/campaign_manager.py": '''"""Campaign manager compatibility layer."""
try:
    from tiers.tier_2.control.campaign_manager import *
except ImportError:
    pass
''',
    "agent/manager/__init__.py": '''"""Manager compatibility layer."""
try:
    from tiers.tier_1.manager import *
except ImportError:
    pass
''',
    "agent/manager/manager_agent.py": '''"""Manager agent compatibility layer."""
try:
    from tiers.tier_1.manager.manager_agent import *
except ImportError:
    pass
''',
    "agent/manager/shortcut_registry.py": '''"""Shortcut registry compatibility layer."""
try:
    from tiers.tier_1.manager.shortcut_registry import *
except ImportError:
    pass
''',
    "agent/manager/deep_agent_factory.py": '''"""Deep agent factory compatibility layer."""
try:
    from tiers.tier_1.manager.deep_agent_factory import *
except ImportError:
    pass
''',
    "agent/config/__init__.py": '''"""Config compatibility layer."""
try:
    from config import *
except ImportError:
    pass
''',
    "agent/config/persistence_config.py": '''"""Persistence config compatibility layer."""
try:
    from config.persistence_config import *
except ImportError:
    pass
''',
    "agent/harness/__init__.py": '''"""Harness compatibility layer."""
from core.harness import *
''',
    "agent/harness/agent_harness.py": '''"""Agent harness compatibility layer."""
try:
    from core.harness.agent_harness import *
except ImportError:
    pass
''',
    "agent/harness/config.py": '''"""Harness config compatibility layer."""
try:
    from core.harness.config import *
except ImportError:
    pass
''',
    "utils/__init__.py": '''"""Utils compatibility layer (for relative imports)."""
from core.utils import *
''',
    "utils/redis.py": '''"""Redis utils compatibility layer."""
from services.redis import *
''',
}

def main():
    print("Creating agent package compatibility layer...")
    
    # Create directories
    for dir_path in DIRS:
        full_path = BASE_DIR / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {dir_path}")
    
    # Create files
    for file_path, content in FILES.items():
        full_path = BASE_DIR / file_path
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created file: {file_path}")
    
    print("\nAgent package compatibility layer created successfully!")
    print("This allows old 'agent.*' imports to work with the new structure.")

if __name__ == "__main__":
    main()
