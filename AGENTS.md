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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Hacktober** (2630 symbols, 5195 relationships, 137 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/Hacktober/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Hacktober/clusters` | All functional areas |
| `gitnexus://repo/Hacktober/processes` | All execution flows |
| `gitnexus://repo/Hacktober/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
