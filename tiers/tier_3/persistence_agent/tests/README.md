# Persistence Agent Tests

Comprehensive test suite for Persistence Agent write operations.

## Quick Start

### 1. Start Consumer (Terminal 1)
```powershell
.\.venv\Scripts\Activate.ps1
python -m tiers.tier_3.persistence_agent.consumer
```

### 2. Run Test (Terminal 2)
```powershell
.\.venv\Scripts\Activate.ps1
python tiers/tier_3/persistence_agent/tests/run_write_test.py
```

## Files

- **`test_write_all_tables.py`** - Main test suite (18 mock records across 4 tables)
- **`run_write_test.py`** - Pre-flight check + test runner
- **`TEST_IMPLEMENTATION_SUMMARY.md`** - Detailed documentation

## Test Coverage

| Table | Records | Operations Tested |
|-------|---------|-------------------|
| staging_leads | 4 | batch_create |
| leads | 4 | create (individual) |
| conversations | 4 | create (with FK) |
| messages | 6 | create (with FK + sentiment) |

## See Also

- [Persistence Agent README](../README.md)
- [Supabase Schema Reference](../../../../docs/SUPABASE_SCHEMA_REFERENCE.md)
