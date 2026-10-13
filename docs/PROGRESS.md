# Build log

## Kickoff
- **This build did not start at the Hack Day.** It started on 2026-10-12 at 18:24 UTC (23:54 IST), before the Hacktoberfest Hack Day Pune kickoff on 13 Oct 2026, in a Claude Code cloud session.
- Confirmed by: human message. Asked about the event rule in `docs/planning/CLAUDE_CODE_PROMPT.md` section 0, the owner answered "Build now, record honestly". So this code must not be presented as built at the event. Commit timestamps show when each commit was made.
- Submission deadline: none given. The event-time fallback triggers (build prompt section 1.8) are not applied; full scope is built.
- Machine: Linux cloud container (x86_64), 4 CPUs, 15 GB RAM. Live model: Ollama not installed and no `gemma4` model (pending-live). Hosted key present: no (`GEMINI_API_KEY` not set).
- Claude Code model: an Anthropic Claude model, named in each commit's `Co-Authored-By` trailer. Session policy keeps raw model ids out of repository files.
- Pushing: the owner asked for finished work to be pushed to `main` on `Gaurav-205/Hacktober` (the container is temporary). This overrides the "never push" rule in `CLAUDE.md` for this session only.

## Pre-event materials (present before the build started)
Commit `f25d567` (2026-10-12 23:49:30 +0530, "docs: add Munim planning pack prepared before the event") holds these 45 files:
- `.claude/agents/{design-reviewer,domain-verifier,security-reviewer,test-auditor}.md`
- `.claude/rules/{core-domain,model-layer,tests,web-server,web-ui}.md`
- `.claude/settings.json`
- `.claude/skills/{build-log,check-all,demo-run,design-pass,gate,pickup}/SKILL.md`
- `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `DESIGN.md`, `NOTICE`, `README.md`, `SECURITY.md`, `THIRD_PARTY.md`
- `docs/{AI_CONTRIBUTION,AI_SPEC,API,ARCHITECTURE,CONTENT,DEMO_SCRIPT,DOMAIN_RULES,PRD,SECURITY_PRIVACY,SUBMISSION,TASKS,TESTING}.md`
- `docs/adr/0001` to `0006`
- `docs/planning/{CLAUDE_CODE_PROMPT,MASTER_PROMPT,START_HERE}.md`
- These are planning documents and configuration. None is application code.

## Preflight (T0.0)
- `python3 --version`: 3.13.16 (system). `uv python install 3.12` installed CPython 3.12.13.
- `uv --version`: 0.11.32. `git --version`: 2.43.0. `node --version`: v22.22.0 (npm 10.9.4). `make --version`: GNU Make 4.3.
- `ollama --version`: command not found. `curl -s http://127.0.0.1:11434/api/tags`: no answer. Live model: **pending-live**.
- `sys.platform`: linux.
- Network: registry.npmjs.org, pypi.org, raw.githubusercontent.com and www.apache.org reachable. The Playwright browser CDN is not reachable. Chromium is pre-installed in `/opt/pw-browsers` (revision 1194).
- Golden values recomputed from the text of `docs/DOMAIN_RULES.md` section 5.3 with a standalone script (scratchpad, not committed): 2283919, 9780909, and 4290370 with 177 days late. All match the document.

## Decisions
- 2026-10-13 03:26 UTC: Pre-commit hooks were not installed in this container until `5263376`, so the Gate 1 commits did not run them. A docstring GSTIN example (R3) got through that way and was removed in `5263376`. `make check` on `5263376` covers every earlier commit's files. `uv run pre-commit install` is now done, and `make install` does it on a fresh machine.
- 2026-10-12 18:40 UTC: Commit trailers are `Assisted-by: Claude Code` plus the harness's `Co-Authored-By` and `Claude-Session` lines. `CLAUDE.md` asks for a model id in the trailer, but session policy forbids raw model ids in pushed artifacts. The `Co-Authored-By` line already names the model.
- 2026-10-12 18:40 UTC: Track work per gate in the session task list instead of one item per task id, because the gates are the unit of verification. Each task id still gets a log entry and a checkbox in `docs/TASKS.md`.

## Follow-ups
- Human: Hindi review by a native reader; Bank Rate confirmation by an accountant; live-model run (`ollama pull gemma4:e4b`, then `MUNIM_LIVE=1 make eval`); demo video; submission form.

## Gates
| Gate | Started (sha, time) | Closed (time) | Exit evidence |
| --- | --- | --- | --- |
| 0 | `f25d567`, 2026-10-12 18:24 UTC | 2026-10-13 03:35 UTC | `make check` exit 0 at `5263376` (752 passed, 1 skipped; contrast "21 pairs checked, 0 problems"; fonts "18 checks, 0 problems"); CI run 2 green at `0435103` |
| 1 | `0435103`, 2026-10-12 22:11 UTC | open (reviewers running) | `make check` exit 0 at `5263376`; munim_core lines 98.64%, branches 96.89% |

## Log
### 2026-10-12 18:52 UTC Step 0: orientation
- Changed: `docs/PROGRESS.md`, `.gitignore`, `docs/PLAN_REVIEW.md` and spec fixes in 12 documents.
- Checked with: a standalone recomputation of DOMAIN_RULES 5.3, which gave 2283919, 9780909 and 4290370 paise with 177 days (all match). Four reviewer agents cross-checked the documents; 45 findings were turned into 18 decisions (`docs/PLAN_REVIEW.md`).
- Notes: the session hit a usage limit at about 19:00 UTC and resumed at 21:40 UTC. Three research agents and three builders died mid-task; their partial files were reviewed before use. Facts were re-checked by hand with web search. rbi.org.in is blocked by the egress policy, so the Bank Rate history comes from secondary sources and stays "not confirmed".

### 2026-10-12 22:05 UTC T0.1 to T0.4, T0.6 to T0.9: workspace, tooling, fonts, CI
- Changed: `pyproject.toml`, `uv.lock`, `packages/*/pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `.secrets.baseline`, `.env.example`, `LICENSE`, `CODE_OF_CONDUCT.md`, fonts and htmx under `static/`, `scripts/check_coverage.py`, `scripts/check_repo_files.py`.
- Checked with: `uv sync --all-packages --all-groups` (ok); a Playwright Chromium launch (141.0.7390.37); `pip-audit --strict --disable-pip` on the exported runtime requirements, which reported "No known vulnerabilities found"; `uv run lint-imports`: "Contracts: 3 kept, 0 broken"; `pytest tests/scripts/test_check_repo_files.py tests/scripts/test_check_coverage.py`: 19 passed.
- Notes: `playwright` is pinned to 1.56.0 because it drives the pre-installed Chromium build 1194. The Firefox download is denied by the egress policy (403 from cdn.playwright.dev), so Firefox E2E runs in GitHub Actions only. LICENSE was fetched verbatim (sha256 cfc7749b...). Ruff 0.17 formats Python fences inside Markdown; `*.md` is excluded from formatting because the spec's pseudo-code is prose.

### 2026-10-12 22:20 UTC T0.5 and T0.10: check scripts and hooks
- Changed: `scripts/{build_tokens,check_contrast,design_lint,check_i18n,check_licences}.py`, `scripts/hooks/{pre_write_guard,post_edit}.py` and their tests; `docs/adr/0007-dev-only-licence-exception.md`; dev rows in `THIRD_PARTY.md`.
- Checked with: `uv run pytest -q tests/hooks`: 109 passed; `pytest tests/scripts/test_check_i18n.py tests/scripts/test_check_licences.py`: 41 passed (the tests found a real bug: a requirement name with an underscore was cut short); `python scripts/check_licences.py`: "106 distributions, 0 problems"; `python scripts/check_contrast.py`: "21 pairs checked, 0 problems" (ink on bond 16.29, hairline-strong on sheet 3.59, tick on tick-wash 4.59).
- Hooks shown live in this session: (1) a Write of `.scratch/guard_check.txt` containing `AIza` plus 35 `x` was refused with "Blocked by pre_write_guard G4: the new text contains what looks like a Google API key (line 1 of the new text)..."; (2) a Write of `scratch_hook_check.py` using an undefined name got PostToolUse feedback "[ruff check] scratch_hook_check.py:1:7: F821 Undefined name ... Fix this before continuing." The file was then deleted.

### 2026-10-12 22:19 UTC T1.1 to T1.8: the pure core
- Changed: `packages/munim_core/src/munim_core/{text,money,dates,ids,states,clock,dossier_model,cli}.py`, `verify/{models,catalog,common,values,identifiers,invoice,dates,cross,registry}.py`, `rules/{rules,bank_rate,message_keys}.yaml`, tests under `tests/unit`, `tests/property`, `tests/golden`, and `tests/ref_gstin.py` (commits `6066b08` to `f53e0dd`).
- Checked with: `uv run pytest tests/unit tests/property tests/golden -q --cov=munim_core --cov-branch`: 362 passed, 1 skipped (the rule-sync language test waits for the Gate 3 i18n files); munim_core lines 98.47%; `mypy` strict clean; `lint-imports`: "Contracts: 3 kept, 0 broken". The golden file `tests/golden/demo_clock.json` was read line by line before blessing. It holds the algorithm vector at an explicit 17.25% (interest 4,290,370 paise, total 54,290,370) and the demo on the seeded Bank Rate table (interest 4,097,671 paise, total 54,097,671; D2), both 177 days late.
- Notes: Hypothesis found two real bugs while the tests were written: `normalise_reference` let different references collide (groups are now joined with "-"), and python-stdnum's `compact` is not idempotent on some Unicode input (Munim now has its own NFKC normaliser). An `INV-TOTAL` bug, where a missing tax line looked the same as an unreadable one, was found by a unit test and fixed.

### 2026-10-13 03:35 UTC Gate 0 complete
- Reviewer: test-auditor on the scripts and hooks tests reported 1 high and 10 medium findings. All were fixed in `d66fcc5`: exit 2 on non-UTF-8 input in four scripts; `check_licences` main exit codes; tests that text-unidecode is not a run-time dependency and is never imported; the repo-file guard scans every text file in any letter case; the G4 guard catches GitHub fine-grained tokens; design-lint rule 4 requires every selector of a list to target `.stamp` (and `:not(.stamp)` does not count); rule 7 tracks `lang` per element instead of per line.
- Checked with: `uv run pytest -q tests/scripts tests/hooks`: 390 passed. `make check` at `5263376` with the uncommitted Gate 2 files stashed: exit 0. Its output included: "Contracts: 3 kept, 0 broken.", "check_licences: 106 distributions, 0 problems", "design_lint: 2 files checked, 0 problems", "check_contrast: 21 pairs checked, 0 problems", "check_fonts: 18 checks, 0 problems", "752 passed, 1 skipped", "munim_core: lines 98.64%, branches 96.89% ... ok".
- The first `make check` run at `d66fcc5` failed in bandit on two `assert` statements in the core (B101). They were replaced with plain control flow in `752a41d`. The repo-file guard then caught the CLI docstring GSTIN, fixed in `5263376`.
- CI: run 1 (`71b4f0d`) failed in the secret scan; run 2 (`0435103`) passed; run 3 (`5263376`) queued at 03:45 UTC.

STATUS: IN PROGRESS (Gate 1 close review and Gate 2 build)
