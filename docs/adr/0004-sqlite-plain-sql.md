# ADR 0004: SQLite with plain SQL and numbered migrations

Status: accepted. Date: 2026-10-12.

## Context
Single user, local, small data. We need foreign keys with cascading deletes, an auditable schema, and verified data wipe on deletion.

## Decision
`sqlite3` standard library with a thin repository layer, Pydantic models at the boundary, numbered `.sql` migrations applied by a small runner. `PRAGMA foreign_keys=ON`, `journal_mode=WAL`, `secure_delete=ON`. Money is stored as integer paise (or text for large normalised JSON), never floats.

## Consequences
+ No ORM to learn or debug; schema is reviewable in one file.
+ Delete-and-VACUUM test can inspect raw bytes.
- Some boilerplate in repositories.

## Alternatives rejected
- SQLModel/SQLAlchemy: more dependencies and magic than needed.
- Files only (JSON): weaker integrity, harder to wipe and query.
