# Architecture

## 1. Principles

1. **The model proposes, code disposes.** Gemma reads; deterministic code decides what passed. No legal or arithmetic conclusion comes from the model.
2. **Pure core.** All rules, money, dates and the payment clock live in a package with no I/O, no network, no framework imports. It is testable in milliseconds and reusable by the web app, the MCP server and the CLI.
3. **Provider abstraction.** Reading is behind one interface with three implementations: `ollama` (local, default), `gemini` (hosted Gemma 4 via `google-genai`), `replay` (recorded responses keyed by content hash, used in CI and as the demo safety net).
4. **Local first.** One process, one SQLite file, one data folder. No accounts, no cloud storage, no telemetry, no third-party requests.
5. **Server-rendered HTML with a sprinkle of JS.** FastAPI + Jinja2 + htmx for partial updates; small vanilla ES modules for the viewer and the red-pen animation. No SPA framework, no build step for JS, no CSS framework.
6. **Everything has provenance.** Every claim records where it came from (`model`, `repair`, `user`), the box, the rule results, the provider and model name.

## 2. Repository layout

```
munim/
├─ pyproject.toml                  # uv workspace root, tool configs (ruff, mypy, pytest, coverage)
├─ uv.lock
├─ Makefile                        # install, run, check, test, eval, e2e, dossier-pdf
├─ DESIGN.md  README.md  AGENTS.md  CONTRIBUTING.md  SECURITY.md  LICENSE  NOTICE  THIRD_PARTY.md
├─ docs/                           # this pack
├─ rules/                          # rule metadata + bank_rate.yaml (data, versioned)
├─ packages/
│  ├─ munim_core/                  # pure domain
│  │  └─ src/munim_core/{money,dates,ids,verify,clock,dossier_model,i18n_keys}.py
│  ├─ munim_ai/                    # model layer
│  │  └─ src/munim_ai/{providers/{base,ollama,gemini,replay},schemas,normalize,prompts/,extract,repair,imageprep}.py
│  ├─ munim_web/                   # FastAPI app
│  │  └─ src/munim_web/{main,deps,db,models,routes/,services/,templates/,static/,i18n/}
│  └─ munim_mcp/                   # stretch: MCP server exposing core
├─ skills/munim-checks/SKILL.md    # stretch: Agent Skill
├─ eval/{synth/,fixtures/,reports/,run_eval.py}
├─ tests/{unit,property,integration,contract,golden,e2e,a11y,eval,scripts,hooks}   # all tests live here, not inside packages
├─ scripts/{check_contrast.py,design_lint.py,check_fonts.py,build_tokens.py,gen_fixtures.py,check_licences.py,check_i18n.py}
├─ .github/workflows/ci.yml
└─ data/                           # gitignored runtime data: munim.db, uploads/
```

## 3. Component diagram

```
Browser (htmx + ES modules)
   |  HTML fragments, JSON for viewer
   v
munim_web (FastAPI)  --------------------------------+
   routes ── services ── repositories(SQLite)         |
      |         |                                      |
      |         +──> munim_ai.extract / repair         |
      |                  |                             |
      |                  v                             |
      |            Provider interface                  |
      |        /          |           \                |
      |   ollama      gemini         replay            |
      |   (local)     (hosted)     (fixtures)          |
      |                                                |
      +──> munim_core.verify / clock / dossier_model <─+
```

Dependency rule (enforced by `import-linter` in CI):
- `munim_core` imports only the standard library, `python-stdnum`, `python-dateutil`, `rapidfuzz`, `pydantic`.
- `munim_ai` may import `munim_core` (for schemas) and provider SDKs.
- `munim_web` may import both.
- Nothing imports `munim_web`.

## 4. Data model (SQLite via SQLModel or plain SQL with Pydantic; choose plain SQL + `sqlite3`)

Plain SQL with a tiny repository layer keeps the dependency surface small and the schema reviewable. Migrations are numbered `.sql` files applied by a 30-line runner and recorded in `schema_migrations`.

```sql
CREATE TABLE cases (
  id TEXT PRIMARY KEY,                 -- ULID
  title TEXT NOT NULL,
  supplier_name TEXT NOT NULL,
  buyer_name TEXT NOT NULL,
  udyam_number TEXT, udyam_date TEXT,  -- ISO date
  enterprise_size TEXT CHECK (enterprise_size IN ('micro','small','medium') OR enterprise_size IS NULL),
  agreement TEXT CHECK (agreement IN ('written','none')),
  credit_days INTEGER,
  objection_removed_on TEXT,
  acceptance_date TEXT,                -- user-confirmed
  interest_base TEXT NOT NULL DEFAULT 'invoice_total',
  as_on_date TEXT,
  confirmed_at TEXT,                   -- set by "Confirm these values"
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE papers (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('invoice','challan','po')),
  original_path TEXT NOT NULL,         -- relative to data/uploads
  sha256 TEXT NOT NULL,
  width INTEGER, height INTEGER, rotation INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,                -- added|reading|read|failed
  provider TEXT, model TEXT, read_at TEXT, error TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE claims (
  id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  field TEXT NOT NULL,                 -- e.g. supplier_gstin, line_items[2].quantity
  value_read TEXT,                     -- first read, never overwritten
  value_current TEXT,                  -- after repair or user edit
  normalized_json TEXT,
  box_y1 INTEGER, box_x1 INTEGER, box_y2 INTEGER, box_x2 INTEGER,  -- 0..1000 grid
  source TEXT NOT NULL CHECK (source IN ('model','repair','user')),
  repair_attempts INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 1,  -- optimistic concurrency, bumped on every change
  accepted_reason TEXT,                -- user typed reason to accept a failing check
  UNIQUE (paper_id, field)
);

CREATE TABLE findings (                -- recomputed; stored for the dossier snapshot only at confirm
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  rule_id TEXT NOT NULL, status TEXT NOT NULL, severity TEXT NOT NULL,
  message_key TEXT NOT NULL, params_json TEXT NOT NULL, fields_json TEXT NOT NULL,
  rule_version TEXT NOT NULL
);

CREATE TABLE payments (id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  paid_on TEXT NOT NULL, amount_paise INTEGER NOT NULL CHECK (amount_paise > 0));

CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);   -- provider, model, language, cloud_consent
CREATE TABLE bank_rates (effective_from TEXT PRIMARY KEY, percent TEXT NOT NULL, source TEXT NOT NULL, confirmed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, at TEXT NOT NULL, kind TEXT NOT NULL, detail_json TEXT NOT NULL);  -- append-only audit log
```
- `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`, `PRAGMA secure_delete=ON`.
- Money columns are integer paise stored as text in `normalized_json`; `payments.amount_paise` is integer.
- The `events` table is the audit trail: every read, repair, edit, confirm and export is a row.

## 5. Key flows

### 5.1 Read a paper
```
POST /papers/{id}/read
 -> service.mark_reading(paper)
 -> background task (asyncio.create_task with a semaphore of 1 for Ollama):
      img = imageprep.prepare(original)             # orient, resize long edge <= 1568, JPEG q90
      raw = provider.extract(img, schema_for(kind)) # text out
      data = parse_and_validate(raw)                # Pydantic; one retry with stricter prompt
      claims = to_claims(data)                      # mask Aadhaar; convert boxes
      save_claims(paper, claims); status=read
      findings = verify.run(case_state)             # pure
      for f in findings where f.repairable and attempts<2: enqueue repair(f)
 -> UI polls GET /papers/{id}/status (htmx every 1s) and swaps the claims panel
```

### 5.2 Repair (the red pen)
```
repair(claim, finding):
   candidates = ids.lookalike_candidates(claim.value) if claim.field is a GSTIN
   if exactly one candidate passes checksum: propose it (source='repair', needs_review)
   else:
     crop = imageprep.crop(prepared image, claim.box expanded by 8%)   # the image the model read (D9)
     value2 = provider.reread(crop, field_spec, ctx.for_reread(field, box, reread_version))
   run verify for that field only
   outcome = corrected | unchanged | check_by_hand
   append event; update claim; UI swaps row with the red-pen animation class
```

### 5.3 Confirm and clock
```
POST /cases/{id}/confirm
  - refuse (409) if any blocking finding is neither passed nor accepted-with-reason
  - snapshot findings, set confirmed_at
GET /cases/{id}/clock?as_on=YYYY-MM-DD
  - core.clock.compute(acceptance, agreement, credit_days, principal, rates, payments, as_on) -> ClockResult with steps[]
```

### 5.4 Dossier
`GET /cases/{id}/dossier` renders `DossierModel` (built in core from claims + findings + clock) with `dossier.html` (HTML templates use the `.html` extension; only the plain-text notice templates are `.md.j2`). Print CSS produces the A4 layout. `make dossier-pdf CASE=<id>` uses Playwright Chromium to render `/cases/{id}/dossier?print=1` to PDF (used in e2e golden test).

## 6. Provider interface

```python
class Provider(Protocol):
    name: str
    model: str
    async def extract(self, image: bytes, kind: PaperKind, language_hint: str | None, ctx: ReadContext) -> ProviderResult: ...
    async def reread(self, crop: bytes, field: FieldSpec, ctx: ReadContext) -> ProviderResult: ...
    async def preflight(self) -> PreflightReport: ...        # model present? supports images? returns json?

@dataclass(frozen=True)
class ReadContext:            # PLAN_REVIEW D9: what replay keys on and what a retry or re-read needs
    original_sha256: str      # hash of the original uploaded bytes, never of a re-encoded copy
    kind: PaperKind; prompt_version: str
    rotation: int = 0         # degrees the user rotated the paper before reading
    attempt: int = 1          # 2 is the strict-JSON retry
    field: str | None = None; box: tuple[int, int, int, int] | None = None   # re-reads only

@dataclass(frozen=True)
class ProviderResult:
    text: str                 # raw model text
    latency_ms: int
    provider: str; model: str # "replay" when replayed
    usage: dict[str, int] | None
    replayed: bool = False
    recorded_from: str | None = None   # "synthetic" or "live" for replayed results
```
Details of prompts, schemas, retries and evaluation are in `docs/AI_SPEC.md`.

## 7. Web layer conventions

- Routes thin, services hold logic, repositories hold SQL. No SQL in routes, no HTTP concepts in services.
- Templates: base layout, components as macros (button, field, sheet, verdict_chip, stamp, claims_row, clock_strip). All strings come through `t("key", **params)`.
- htmx: fragments return the smallest useful piece (`hx-target`, `hx-swap="outerHTML"`); every fragment endpoint also works as a full page when JS is off (progressive enhancement where practical; the viewer requires JS and says so).
- JS modules (`static/js/`): `viewer.js` (zoom, pan, boxes), `redpen.js` (strike and write animation), `clipboard.js`, `i18n.js` (language toggle persisted in a cookie). Each under 300 lines, no dependencies, ES2022, tested via Playwright and a few Vitest-free unit tests run in the browser harness (see TESTING).
- CSP: `default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'`. No inline scripts or styles; no CSP exceptions.
- CSRF: same-site cookie `munim_csrf` + hidden field on forms + `hx-headers` for htmx; checked by a dependency on every non-GET route.
- The server binds to `127.0.0.1` by default; the README explains `--host` risks.

## 8. Error handling

| Situation | Behaviour |
| --- | --- |
| Ollama not running / model missing | Settings page and an inline notice on the first read: what is missing and the exact command to fix it |
| Model returns invalid JSON | One retry; then claims empty, the paper shows "Munim couldn't read this paper automatically. Enter the values by hand." with the form |
| Provider timeout (90 s) | Cancel, mark failed, keep the file |
| Unsupported file | 415 with message in the user's language |
| Corrupt image | 422 with a message; nothing stored |
| Database busy | Retry 3 times with backoff, then 503 |
| Unhandled exception | Log with a request id; the user sees "Something went wrong. Nothing was lost. Reference: abc123" |

Logs never contain document text or field values; they contain ids, durations and error classes.

## 9. Observability (local)

`structlog` JSON logs to stdout; `/healthz` returns versions and provider preflight status; the Evaluation page reads reports from disk. No external telemetry.

## 10. Configuration

Environment variables (see `.env.example`; no secrets committed):
```
MUNIM_DATA_DIR=./data
MUNIM_HOST=127.0.0.1
MUNIM_PORT=8765
MUNIM_PROVIDER=ollama            # ollama | gemini | replay
MUNIM_OLLAMA_URL=http://127.0.0.1:11434
MUNIM_OLLAMA_MODEL=gemma4:e4b
MUNIM_GEMINI_MODEL=gemma-4-31b-it
GEMINI_API_KEY=                  # only if provider=gemini; never logged
MUNIM_LANG=en
```
Settings are loaded by one `Settings` class (pydantic-settings); there is exactly one place that reads the environment.

## 11. Dependencies (pinned in `uv.lock`; each justified in THIRD_PARTY.md)

Runtime: fastapi, uvicorn, jinja2, python-multipart, pydantic, pydantic-settings, python-stdnum, python-dateutil, rapidfuzz, pillow, pillow-heif (HEIC), pypdfium2 (PDF to image), httpx, ollama, google-genai (optional extra), structlog, pyyaml, python-ulid.
Dev: pytest, pytest-asyncio, pytest-cov, hypothesis, playwright, axe-playwright-python, ruff, mypy, bandit, pip-audit, import-linter, pre-commit, reportlab (fixture generation), fonttools + brotli (WOFF2 reading and conversion), mutmut (optional).
Front end: htmx 2.x vendored file (BSD-2) with its licence; no other JS dependency.

Licence check: `scripts/check_licences.py` fails if any dependency's licence is not in the allow-list (MIT, BSD, Apache-2.0, ISC, MPL-2.0, PSF, LGPL-2.1-or-later for python-stdnum as a dynamically imported, unmodified library, OFL for fonts).

## 12. Performance budget

- Image prepared for the model: long edge <= 1568 px, JPEG quality 90; reading a typical invoice under 60 s with E4B on a modern 16 GB laptop is the target, not a promise; measure and record in the evaluation report.
- UI: HTML fragments under 30 KB; no layout shifts when claims arrive (reserve row height).

## 13. Extension points (stretch)

- `munim_mcp`: FastMCP server exposing `check_gstin`, `check_invoice_arithmetic`, `compute_msmed_interest`, `list_rules`, all calling `munim_core`. No document upload tool (privacy).
- `skills/munim-checks/SKILL.md`: an Agent Skill that tells another agent when and how to call these tools, with name and description frontmatter per the Agent Skills spec.
- New paper types: add a schema in `munim_ai/schemas`, prompts in `prompts/`, verify rules in core; documented in CONTRIBUTING.
