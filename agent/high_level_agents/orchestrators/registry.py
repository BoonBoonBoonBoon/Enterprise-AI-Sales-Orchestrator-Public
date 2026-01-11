from typing import Any, Dict, Optional


class Registry:
    """Simple registry for agents and tools.

    - register(name, obj)
    - get(name) -> obj
    - list() -> names
    """

    def __init__(self):
        self._items: Dict[str, Any] = {}

    def register(self, name: str, obj: Any):
        self._items[name] = obj

    def get(self, name: str) -> Optional[Any]:
        return self._items.get(name)

    def list(self):
        return list(self._items.keys())


# predictable discovery
REGISTRY_CLASS = Registry
