"""Discovery registry for local operational agents.

This scans the `agent.operational_agents` package directory for subpackages
and attempts to import each one. Modules should expose either `AGENT_CLASS`
or `create_agent()` so the registry can pick them up.

Usage:
    from agent.operational_agents.registry import discover_local_agents
    agents = discover_local_agents()
"""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Any

PACKAGE = "agent.operational_agents"


def discover_local_agents(package: str = PACKAGE) -> Dict[str, Any]:
    """Discover local agent subpackages in a PEP-420-safe way.

    This iterates over all entries in package.__path__ so it works when the
    package is an explicit package (has __init__.py) or a namespace package.
    """
    pkg = importlib.import_module(package)
    agents: Dict[str, Any] = {}
    # pkg.__path__ works for both normal and namespace packages
    for path_entry in pkg.__path__:
        base_path = Path(path_entry)
        for finder, name, ispkg in pkgutil.iter_modules([str(base_path)]):
            if not ispkg:
                continue
            full_mod = f"{package}.{name}"
            try:
                mod = importlib.import_module(full_mod)
            except Exception:
                # skip modules that error on import
                continue
            agent_obj = getattr(mod, "AGENT_CLASS", None)
            if agent_obj is None:
                agent_obj = getattr(mod, "create_agent", None)
            # Fall back: some agents place the implementation in a nested module
            # e.g. agent.operational_agents.rag_agent.rag_agent
            if agent_obj is None:
                try:
                    nested = importlib.import_module(f"{full_mod}.{name}")
                    agent_obj = getattr(nested, "AGENT_CLASS", None) or getattr(nested, "create_agent", None)
                except Exception:
                    agent_obj = None
            if agent_obj is not None:
                agents[name] = agent_obj
    return agents
