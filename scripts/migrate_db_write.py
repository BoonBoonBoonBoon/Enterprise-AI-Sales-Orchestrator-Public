#!/usr/bin/env python
"""Migration utility to help find DBWriteAgent usage in the codebase.

This tool scans for files that may be using DBWriteAgent and provides
suggested replacements using PersistenceAgent.

Usage:
  python scripts/migrate_db_write.py
"""

import os
import sys
import re
from pathlib import Path


def scan_for_db_write_usage(base_dir="."):
    """Scan codebase for potential DBWriteAgent usage."""
    patterns = [
        r"DBWriteAgent",
        r"create_supabase_agent",
        r"create_in_memory_agent",
        r"from\s+agent\.tools\.db_write",
        r"from\s+agent\.operational_agents\.db_write_agent",
        r"import\s+.*DBWriteAgent",
    ]

    base_path = Path(base_dir)
    python_files = list(base_path.glob("**/*.py"))
    
    found_files = {}
    
    for pattern in patterns:
        regex = re.compile(pattern)
        for file_path in python_files:
            if file_path.name == "migrate_db_write.py":
                continue  # Skip this script itself
                
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    if regex.search(content):
                        if file_path not in found_files:
                            found_files[file_path] = []
                        
                        # Get the first few lines of the match for context
                        for i, line in enumerate(content.split("\n")):
                            if regex.search(line):
                                found_files[file_path].append((i+1, line))
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    
    return found_files


def main():
    """Main function to run the scanner and print results."""
    print("Scanning for DBWriteAgent usage in the codebase...")
    
    found_files = scan_for_db_write_usage()
    
    if not found_files:
        print("\nNo files found using DBWriteAgent.")
        return
    
    print(f"\nPotential DBWriteAgent usage found in {len(found_files)} files:\n")
    
    for i, (file_path, matches) in enumerate(found_files.items(), 1):
        rel_path = file_path.relative_to(Path("."))
        print(f"{i}. {rel_path}:")
        for line_num, line in matches[:3]:  # Show up to 3 matches per file
            print(f"   Line {line_num}: Possible usage of db_adapter/DBWriteAgent")
            print(f"   ```\n   {line.strip()}\n   ```")
        
        if len(matches) > 3:
            print(f"   ... and {len(matches) - 3} more matches")
        print()
    
    print("NOTE: This is a basic scan. Manual review is recommended to ensure all usage points are identified.")
    print("\nNext Steps:")
    print("1. Replace uses of 'create_supabase_agent()' with 'create_persistence_agent()' ")
    print("2. Replace uses of 'create_in_memory_agent()' with 'create_persistence_agent(kind=\"memory\")'")
    print("3. Update method calls as needed (parameter names should be compatible)")
    print("4. Test thoroughly after migration")
    print("5. Remove 'from agent.operational_agents.db_write_agent.db_write_agent import ...' imports")
    print("\nFor more details, see PERSISTENCE_MIGRATION.md")


if __name__ == "__main__":
    main()