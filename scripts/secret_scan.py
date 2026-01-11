import re
import os
import sys
from pathlib import Path

PATTERNS = [
    # Look for values, not variable names; exclude common placeholder markers
    re.compile(r"(?i)(^|\b)(api[_-]?key|secret)\s*[:=]\s*(?!<REDACTED>|__REDACTED__|your-)[']?[A-Za-z0-9\-\._]{12,}"),
    re.compile(r"(?i)authorization:\s*bearer\s+(?!<REDACTED>|__REDACTED__)[A-Za-z0-9\-\._]{12,}"),
    re.compile(r"(?i)(ghp_|hf_|sk-)(?!<REDACTED>|__REDACTED__)[A-Za-z0-9\-\._]{12,}"),
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PGP) PRIVATE KEY-----"),
]

EXCLUDE_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
EXCLUDE_FILES = {"secret_scan.py"}
EXCLUDE_PATH_SUBSTRINGS = {os.path.join('config', 'settings.py')}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    hits = []
    for p in root.rglob("*"):
        if p.is_dir() or should_skip(p):
            continue
        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue
        # Skip known files that contain env var names for documentation/config purposes
        if any(sub in str(p) for sub in EXCLUDE_PATH_SUBSTRINGS):
            continue
        for pat in PATTERNS:
            for m in pat.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                snippet = text[m.start(): m.start()+80].replace("\n", " ")
                hits.append((p, line_no, snippet))
    if hits:
        print("SECRET SCAN FOUND POTENTIAL SECRETS:\n")
        for p, ln, snip in hits:
            print(f"{p}:{ln}: {snip}")
        return 1
    print("Secret scan: no obvious secrets found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
