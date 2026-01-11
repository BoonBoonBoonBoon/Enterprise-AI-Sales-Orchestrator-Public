"""Discovery registry for local tools under `agent.tools`.

Scans the `agent.tools` package for modules and imports them. Modules can
expose `TOOL` or `create_tool` to be discovered.
"""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Any

PACKAGE = "agent.tools"


def discover_local_tools(package: str = PACKAGE) -> Dict[str, Any]:
    """Discover local tool modules in a PEP-420-safe way.

    Iterates over entries in package.__path__ so it works with namespace
    packages as well as normal packages with __init__.py.
    """
    pkg = importlib.import_module(package)
    tools: Dict[str, Any] = {}
    for path_entry in pkg.__path__:
        base_path = Path(path_entry)
        for finder, name, ispkg in pkgutil.iter_modules([str(base_path)]):
            if ispkg:
                # skip subpackages for now
                continue
            full_mod = f"{package}.{name}"
            try:
                mod = importlib.import_module(full_mod)
            except Exception:
                continue
            tool_obj = getattr(mod, "TOOL", None) or getattr(mod, "create_tool", None)
            if tool_obj is not None:
                tools[name] = tool_obj
    return tools
