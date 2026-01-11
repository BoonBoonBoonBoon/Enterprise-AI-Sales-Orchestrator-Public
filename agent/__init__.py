# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ DEPRECATED: Compatibility Shim for Legacy Imports                          ║
# ║                                                                             ║
# ║ This package exists ONLY for backward compatibility with legacy tests      ║
# ║ and scripts. All new code should import from the canonical locations:      ║
# ║                                                                             ║
# ║   agent.harness.*              → core.harness.*                            ║
# ║   agent.tools.redis.*          → services.redis.*                          ║
# ║   agent.tools.persistence.*    → services.persistence.*                    ║
# ║   agent.operational_agents.*   → tiers.tier_3.*                            ║
# ║   agent.manager.*              → tiers.tier_1.manager.*                    ║
# ║   agent.orchestrators.*        → tiers.tier_2.*                            ║
# ║   agent.config.*               → config.*                                  ║
# ║                                                                             ║
# ║ TODO: Migrate all legacy imports and remove this package entirely.         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

import warnings as _warnings

_warnings.warn(
    "The 'agent' package is deprecated. "
    "Use 'core.*', 'services.*', or 'tiers.*' instead.",
    DeprecationWarning,
    stacklevel=2
)

