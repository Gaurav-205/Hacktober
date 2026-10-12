# AGENTS.md

Instructions for AI coding agents (and a useful summary for humans) working in this repository. Keep this file short; details live in `docs/`.

## What this is
Munim: open-source tool that reads photos of an Indian tax invoice, delivery challan and purchase order with Gemma 4, checks them with deterministic rules, and computes the MSMED Act payment clock and interest to produce an evidence file. Local first. Python 3.12, FastAPI, Jinja2, htmx, SQLite.

## Read before you change anything
1. `docs/PRD.md` (what and why), `docs/DOMAIN_RULES.md` (rules, golden numbers), `docs/ARCHITECTURE.md`, `docs/AI_SPEC.md`, `docs/TESTING.md`.
2. For any UI work: `DESIGN.md`. It is a contract enforced by `scripts/design_lint.py` and `scripts/check_contrast.py`.
3. `docs/TASKS.md` for ordering. Do not skip gates.

## Commands
```
make install     # uv sync, pre-commit hooks, Playwright browsers
make run         # app on http://127.0.0.1:8765
make check       # ruff, mypy, bandit, import-linter, design lints, unit/property/integration tests
make e2e         # Playwright journeys (replay provider)
make eval        # evaluation harness
make bless       # re-bless golden files after reviewing diffs
make ci          # everything except live-model eval
```

## Rules you must follow
- **Model proposes, code disposes.** Never let model output decide a check, a number or user-facing text.
- **Money is integer paise.** No floats for money. Use `munim_core.money`.
- **Pure core.** `munim_core` imports no framework, no network, no filesystem. `import-linter` enforces this.
- **No hard-coded UI strings.** Use i18n keys in `en.json` and `hi.json`; `check_i18n` must pass.
- **Design tokens only.** No raw hex outside `tokens.css`; no shadows, gradients, pills, emoji; sentence case. See `DESIGN.md` section 7 and 12.
- **Privacy.** No real documents, GSTINs of real businesses, names or keys in the repository, tests, logs or screenshots. Logs carry ids only. Never log claim values.
- **Say Passed, never Verified.** A passed check does not prove a value is right.
- **Do not invent facts.** Legal, rate and model-capability statements need a source in `DOMAIN_RULES.md` or `AI_SPEC.md`; unverified items stay labelled unverified.
- **Tests first** for `munim_core` and `munim_ai`. Every bug fix starts with a failing test.
- **Small commits** with a message that says why. If AI wrote material code, add a trailer `Assisted-by: <tool>`.
- **Do not weaken a check to make a test pass.** If a golden number changes, explain why in the commit and update `DOMAIN_RULES.md`.

## Where things go
- New rule: `munim_core/verify/*`, rule id in `docs/DOMAIN_RULES.md` and `rules/*.yaml`, message key in both language files, tests (pass, fail, boundary, skipped).
- New paper type: schema in `munim_ai/schemas.py`, prompt files, verify rules, fixtures, e2e.
- New screen: template + macros + CSS using tokens + i18n + axe test + screenshots at 360/768/1440 in en and hi.
- Prompt change: bump `prompt_version`, re-run `make eval`, update the report.

## Do not
- Add a JS framework, a CSS framework, an icon library, analytics, telemetry or CDN links.
- Add dependencies without a line in `THIRD_PARTY.md` and an allowed licence.
- Commit images outside `eval/fixtures/` and `docs/screens/`.
- Claim measured results that are not in `eval/reports/latest.json`.

## When blocked
Write the blocker and the smallest working alternative in `docs/PROGRESS.md`, take it, and continue. Do not stop to ask unless a rule above would be broken.
