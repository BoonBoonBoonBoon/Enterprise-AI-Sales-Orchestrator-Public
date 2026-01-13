# Archived Documentation

This folder contains historical documentation that is no longer actively maintained but is preserved for reference.

## Why Archive Instead of Delete?

1. **Historical Context** — Understanding past decisions and migrations
2. **Audit Trail** — Tracking how the system evolved
3. **Recovery** — Information may become relevant again

## Archived Documents

| Document                         | Original Location        | Reason Archived                       | Date     |
| -------------------------------- | ------------------------ | ------------------------------------- | -------- |
| `project-cv.md`                  | `reference/`             | Personal CV, not system documentation | Jan 2026 |
| `sdr-langgraph.md`               | `reference/`             | External library reference            | Jan 2026 |
| `deep-agents-github.md`          | `reference/`             | External library reference            | Jan 2026 |
| `AGENT_PACKAGE_MIGRATION.md`     | `migration/`             | Migration completed                   | Jan 2026 |
| `SCRIPTS_MIGRATION_MAP.md`       | `scripts/`               | Scripts reorganized                   | Jan 2026 |
| `REDIS_MIGRATION_PLAN.md`        | `architecture/services/` | Migration completed                   | Jan 2026 |
| `REDIS_IMPLEMENTATION_STATUS.md` | `architecture/services/` | One-time status snapshot              | Jan 2026 |
| `SYSTEM_AUDIT.md`                | `docs/`                  | Historical audit from Nov 2025        | Jan 2026 |
| `ARCHITECTURE_UPDATE.md`         | `docs/`                  | Superseded by current docs            | Jan 2026 |
| `completion-report.md`           | `reference/`             | One-time completion report            | Jan 2026 |
| `quick-setup-llm.md`             | `getting-started/`       | Merged into quickstart.md             | Jan 2026 |

## Restoring Archived Content

If you need to restore content from an archived document:

1. Review the document in this folder
2. Extract relevant sections
3. Update for current architecture
4. Add to appropriate active documentation section
5. Submit PR with context on why restoration is needed

## Note

These documents are excluded from the MkDocs navigation and search via `exclude_docs` in `mkdocs.yml`.
