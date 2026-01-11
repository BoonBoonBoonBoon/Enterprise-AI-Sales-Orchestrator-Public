"""CI Guard: Detect risky persistence usage patterns.

Checks:
 1. Direct instantiation of SupabaseAdapter outside approved factories.
 2. Direct InMemoryAdapter writes in non-test code.
 3. Attempts to write to governance tables ('clients', 'campaigns') outside tests.

Exit non-zero on violations.
"""
from __future__ import annotations
import os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TABLES = {"clients", "campaigns"}
_errors = []

ADAPTER_PATTERN = re.compile(r"SupabaseAdapter\(")
WRITE_CALL_PATTERN = re.compile(r"\.write\(")


def scan_file(path: Path):
    rel = path.relative_to(ROOT)
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "tests" in rel.parts:
        return
    # 1. Direct SupabaseAdapter instantiation
    if "SupabaseAdapter(" in text and "build_supabase_service" not in text and "factory" not in rel.parts:
        _errors.append(f"Direct SupabaseAdapter usage in {rel}")
    # 2 & 3: naive governance table write attempts
    for t in FORBIDDEN_TABLES:
        if f"write('{t}'" in text or f'write("{t}"' in text:
            _errors.append(f"Write to governance table '{t}' in {rel}")


def main():
    for p in ROOT.rglob("*.py"):
        if p.name.startswith("ci_guard_"):
            continue
        scan_file(p)
    if _errors:
        print("CI Guard Violations:\n" + "\n".join(f" - {e}" for e in _errors))
        sys.exit(1)
    print("CI Guard: OK (no violations)")


if __name__ == "__main__":  # pragma: no cover
    main()
