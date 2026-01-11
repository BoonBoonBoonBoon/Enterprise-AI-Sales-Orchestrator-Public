"""Plugin: HeadOfSales (optional)

Place optional, business-facing orchestrators/plugins here. These should be
registered opt-in and not part of the critical run path.
"""

from typing import Dict, Any


class HeadOfSalesPlugin:
    def __init__(self, sources: Dict[str, Any] | None = None):
        self.sources = sources or {}

    def summarize(self, campaign_id: str) -> Dict[str, Any]:
        raise NotImplementedError()


PLUGIN_CLASS = HeadOfSalesPlugin
