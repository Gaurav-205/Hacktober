# Build plan (gated)

The plan is ordered so that **a partial run still leaves a working vertical slice**. Do not start a gate until the previous gate's exit checks pass. Commit at the end of every task with a message that explains why. Tick boxes in this file as you go and keep it in the repository.

Time guide is for a human team in one event day (about 9 working hours). A coding agent working alone should still respect the order, not the clock.

Legend: `[ ]` open, `[x]` done. "Exit" lines are commands that must pass.

---

## Gate 0: Foundations (0:00 to 0:45)

- [ ] T0.0 Event-rule confirmation recorded and preflight commands run (the master prompt, sections 0 and 5; in the Claude Code kit it is `docs/planning/MASTER_PROMPT.md`); results in `docs/PROGRESS.md`.
- [ ] T0.1 Create the repo skeleton from `docs/ARCHITECTURE.md` section 2, after the first commit of the planning documents (`git init`, default branch `main`; the first commit contains only the pre-existing planning files).
- [ ] T0.2 `uv` workspace: root `pyproject.toml`, four member packages (`munim_core`, `munim_ai`, `munim_web`, `munim_mcp` placeholder), Python 3.12, dev dependency group.
- [ ] T0.3 Tooling config in root `pyproject.toml`: ruff (lint + format; rules E,F,I,B,UP,SIM,S,C4,PL minimal set), mypy strict for core and ai, pytest (strict markers, asyncio auto), coverage (branch, fail_under per package), import-linter contracts from ARCHITECTURE section 3.
- [ ] T0.4 `Makefile`: `install`, `run`, `check`, `test`, `test-fast`, `e2e`, `eval`, `bless`, `dossier-pdf`, `fixtures`, `screens` (Playwright screenshots of every page at 360, 768 and 1440 px in en and hi into `docs/screens/`), `ci`.
- [ ] T0.5 `scripts/build_tokens.py`: parse `DESIGN.md` front matter -> `static/css/tokens.css` (custom properties). `scripts/check_contrast.py`, `scripts/design_lint.py`, `scripts/check_fonts.py`, `scripts/check_i18n.py`, `scripts/check_licences.py` with their own unit tests (one failing and one passing sample per rule).
- [ ] T0.6 Fonts: download Mukta and Kalam from `google/fonts` (OFL) as WOFF2, place in `static/fonts/` with licence files; run `check_fonts.py`; if Mukta lacks `tnum`, switch to IBM Plex Sans + Plex Sans Devanagari and update `DESIGN.md` front matter.
- [ ] T0.7 Pre-commit: ruff, mypy, `detect-secrets`, large-file and image-location guard, design lint, i18n check.
- [ ] T0.8 CI workflow per `TESTING.md` section 10 (jobs static, design, test, e2e, eval-replay). Actions pinned by SHA.
- [ ] T0.9 `.gitignore`, `.env.example`, `LICENSE` (the unmodified Apache-2.0 text, copied from apache.org or an installed package's LICENSE file; never paraphrased), `NOTICE`, `THIRD_PARTY.md` (empty table with columns), `SECURITY.md`, `CONTRIBUTING.md`.

**Exit:** `make check` passes on the empty skeleton; `python scripts/check_contrast.py` prints all pairs passing; CI green on the first push.

---

## Gate 1: Core domain, no AI, no web (0:45 to 2:15)

Order matters: each item is test-first.

- [ ] T1.1 `money.py`: `Paise` helpers, `parse_inr`, `format_inr`, rounding. Tests + properties (TESTING section 2, 3).
- [ ] T1.2 `dates.py`: parse with day-first assumption, ambiguity detection, Devanagari digit conversion, month-end-safe `add_months`.
- [ ] T1.3 `ids.py`: GSTIN/PAN/Aadhaar wrappers around python-stdnum, `lookalike_candidates`, `mask_aadhaar`. Pure-Python reference GSTIN in `tests/ref_gstin.py` and the hypothesis cross-check.
- [ ] T1.4 `verify/` package: `Finding` model; one module per rule family (identifiers, invoice, cross); registry `run_all(case_state) -> list[Finding]`; message keys only.
- [ ] T1.5 `clock.py`: `compute_due_date`, `compute_interest` returning `ClockResult` with `steps`; bank rate table lookup; part payments (should); golden outputs from `DOMAIN_RULES.md` 5.3 as tests.
- [ ] T1.6 `dossier_model.py`: pure builder from claims + findings + clock to a `DossierModel` dataclass.
- [ ] T1.7 `rules/*.yaml` + loader; test that every rule id in `DOMAIN_RULES.md` exists in YAML and in code, and vice versa.
- [ ] T1.8 CLI: `python -m munim_core.cli interest --principal 500000 --due 2026-01-01 --as-on 2026-04-01 --rate 18` (for the fallback demo and for debugging).

**Exit:** `uv run pytest tests/unit tests/property tests/golden -q --cov=munim_core --cov-branch` passes with core coverage >= 95% lines and >= 90% branches (tests live in the top-level `tests/` tree, see ARCHITECTURE section 2); mypy strict clean; `make check` green.

---

## Gate 2: AI layer (2:15 to 3:45)

- [ ] T2.1 `schemas.py`, `normalize.py`, tests.
- [ ] T2.2 `imageprep.py`: orient (EXIF), resize to long edge 1568, JPEG q90, quality heuristics (brightness, Laplacian variance), crop with expansion, PDF first pages via pypdfium2. Tests with generated images.
- [ ] T2.3 `Provider` protocol, `ReplayProvider` (+ record wrapper), `OllamaProvider`, `GeminiProvider` (optional extra), contract tests against replay and a fake Ollama transport.
- [ ] T2.4 Prompts as files with `prompt_version`; builder that renders the schema compactly.
- [ ] T2.5 `extract.py` (parse, validate, one retry, soft failure) and `repair.py` (section 7 of AI_SPEC) with outcomes; tests with replay fixtures including malformed output and runaway text.
- [ ] T2.6 `scripts/gen_fixtures.py`: deterministic synthetic papers + degradations + ground truth + injected-fault variants; produce >= 30 papers; commit as `eval/fixtures/*` (images are small JPEGs, total under 6 MB).
- [ ] T2.7 `eval/run_eval.py` and report schema; run against the replay provider to prove the harness; **run against a live provider (Ollama if available, else Gemini) and record fixtures with `record` mode**; write `eval/reports/latest.json`.
- [ ] T2.8 Preflight probes for Ollama (model present, vision, JSON format) and the Settings messages.

**Exit:** `make eval` produces a valid report with all metrics; recorded fixtures exist for the demo set; `uv run pytest tests -q -m "not e2e and not live" --cov=munim_core --cov=munim_ai` green; if no live model is reachable, the report is explicitly labelled "replay only" and Gate 6 includes a live run.

---

## Gate 3: Web vertical slice (3:45 to 6:00)

Goal: a person can create a case, add three papers, read them (replay or live), see boxes and the claims table, edit values, see findings, and confirm. Use the design tokens from the start; do not write a throwaway unstyled version.

- [ ] T3.1 App factory, `Settings`, structlog, security headers middleware, Host allow-list, CSRF dependency, error pages, `/healthz`.
- [ ] T3.2 SQLite: connection management, migration runner, `0001_init.sql` from ARCHITECTURE section 4, repositories with tests on a temp DB.
- [ ] T3.3 i18n: loader, `t()` Jinja global, language switch cookie, `⟦key⟧` dev placeholders, `check_i18n` passing; `en.json` and `hi.json` seeded from `docs/CONTENT.md`.
- [ ] T3.4 Base layout, tokens.css, components.css, macros: button, field, sheet, verdict_chip, dropzone, claims_row, icons (section 10 of DESIGN.md).
- [ ] T3.5 Pages: case list with empty state and create form; workbench frame (rail, viewer, claims panel placeholder).
- [ ] T3.6 Upload endpoint with the validation in API.md; thumbnails; rotate; delete paper.
- [ ] T3.7 Read flow: background task, status polling fragment, claims panel with rows, boxes on the viewer (SVG overlay), selection sync, edit with original struck through.
- [ ] T3.8 Findings in the claims panel (run core verify after each change), accept-with-reason, confirm endpoint with 409 rules.
- [ ] T3.9 Integration tests for all of the above; E2E-1 (happy path) and E2E-3 (unrepairable) pass.

**Exit:** `make check` green; `make e2e -k "E2E-1 or E2E-3"` green; axe zero serious/critical on workbench states; a screenshot at 1440px looks like `DESIGN.md` section 5 wireframe.
**Fallback trigger:** if this gate is not green at hour 6, stop adding features, fix what is broken, and go to Gate 4 with the reduced scope in PRD section 10.

---

## Gate 4: The signature moments (6:00 to 7:30)

- [ ] T4.1 Red-pen sequence: `redpen.js` + CSS per DESIGN 4.8, reduced-motion path, repair endpoint wired to the repair loop, E2E-2 passes.
- [ ] T4.2 Case settings form (acceptance date, agreement, credit days, Udyam, objection, interest base, as-on date) and eligibility panel text.
- [ ] T4.3 Clock strip + working page (steps table), bank-rate table UI with "not confirmed" state.
- [ ] T4.4 Evidence file (dossier): screen layout, print stylesheet, stamp SVG + conditions, originals pages, notice (en, hi) via templates, copy buttons.
- [ ] T4.5 `make dossier-pdf` + E2E-10.
- [ ] T4.6 Golden tests for dossier and notices; bless once after manual review.

**Exit:** the full demo (DEMO_SCRIPT.md) runs end to end on the replay provider; the printed PDF is 4+ pages A4 and passes visual review.

---

## Gate 5: Quality pass (7:30 to 8:30)

- [ ] T5.1 Hindi complete: every screen in `hi`, long-text checks, E2E-4; flag unreviewed status in the About page footer until a human reviewer signs off.
- [ ] T5.2 Responsive: 360, 768, 1024, 1440; E2E-7.
- [ ] T5.3 Keyboard and screen-reader pass; E2E-5, E2E-6; `docs/A11Y_CHECKLIST.md` completed.
- [ ] T5.4 Privacy: delete case wipe test, VACUUM, network-only-loopback assertion in E2E, About and Settings text, consent flow for Gemini.
- [ ] T5.5 Design review against `DESIGN.md` section 7 using screenshots; fix every violation; run `design_lint`.
- [ ] T5.6 Evaluation page and Rules page.
- [ ] T5.7 Error states: provider down (E2E-9), corrupt image, unsupported file, timeouts.

**Exit:** `make ci` green locally; all E2E scenarios pass in Chromium and Firefox; no `TODO` or `FIXME` without an issue reference.

---

## Gate 6: Release and stretch (8:30 to end)

Required:
- [ ] T6.1 `README.md` completed with real numbers from `eval/reports/latest.json`, real screenshots from `docs/screens/`, install steps verified from a clean clone in a temp directory (record the commands that were run).
- [ ] T6.2 `THIRD_PARTY.md` complete (`check_licences.py` green); `docs/AI_CONTRIBUTION.md` brackets filled.
- [ ] T6.3 Live run against a real model, recorded as fixtures; re-run `make eval`.
- [ ] T6.4 `docs/SUBMISSION.md` filled; demo video checklist.
- [ ] T6.5 Tag `v0.1.0`; GitHub release notes; make sure the repository is public.

Stretch, in this order, only if Gates 0 to 5 are green:
- [ ] T6.6 `munim_mcp` with three tools + tests via the MCP SDK client; README snippet for connecting.
- [ ] T6.7 `skills/munim-checks/SKILL.md`; validate with `skills-ref validate`.
- [ ] T6.8 IFSC check with razorpay/ifsc data (MIT); pixel blur for Aadhaar boxes; ZIP export.
- [ ] T6.9 Real-paper evaluation (local), write `docs/EVAL_REAL.md` with aggregates only.

**Final exit (Definition of Done):** see the master prompt's "Definition of Done" section (`docs/planning/MASTER_PROMPT.md` in the Claude Code kit).

---

## Task discipline

- One task, one commit (small follow-ups allowed). Tests first for Gate 1 and 2.
- Never mark a box done unless the task's check passed in this session; paste the command and result summary into the commit body or `docs/PROGRESS.md`.
- Write `docs/PROGRESS.md` entries as you go: date/time, task id, what changed, what was verified, what was surprising. It becomes the build log judges can read.
- If a task is blocked, write the blocker in `docs/PROGRESS.md`, choose the smallest working alternative, and continue.
