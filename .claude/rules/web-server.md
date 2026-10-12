---
paths:
  - "packages/munim_web/src/munim_web/**/*.py"
  - "packages/munim_web/src/munim_web/migrations/**"
---

# Rules for the web server

- Thin routes, services for logic, repositories for SQL. No SQL in routes and no HTTP types in services (`docs/ARCHITECTURE.md` section 7).
- SQLite with plain SQL and numbered migrations. Turn on `PRAGMA foreign_keys`, WAL and `secure_delete`. Claims keep `value_read` forever; edits change `value_current` and bump `version`.
- Security (`docs/API.md`, `docs/SECURITY_PRIVACY.md`):
  - bind to loopback
  - Host allow-list with the port
  - a CSRF token on every non-GET request, compared with `secrets.compare_digest`
  - the full header set on every response, including errors and static files
  - uploads checked by magic bytes, with a streaming size limit, a pixel limit and generated file names
- Render HTML with Starlette's `Jinja2Templates`, which autoescapes. Never mark model or user text `|safe`. Notices are plain-text `.md.j2` templates filled with values already formatted.
- Background reads use `asyncio.create_task` and a semaphore of 1, and persist every state change. On startup, mark papers stuck in `reading` as failed.
- Logs (structlog) carry ids, durations and error classes only, never field values, document text, client file names or keys.
- The audit `events` table records reads, repairs, edits, confirmations, exports and deletions without values.
- Settings come from one `Settings` class. Nothing else reads the environment.
- After changes here, ask the `security-reviewer` subagent for a review at the next gate close, or immediately if the change touches uploads, middleware, logging or providers.
