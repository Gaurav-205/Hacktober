# Munim: build prompt for Claude Code

This is the complete working brief for Claude Code. Either paste this file into Claude Code as your first message, or start Claude Code in this repository and set the `/goal` given in Appendix D, which points here.

## Kickoff confirmation (the human fills this in at the event)

```
Kickoff time (IST):             [HH:MM] on 13 Oct 2026
Submission deadline (IST):      [HH:MM]
This folder was created after kickoff: [yes]
Machine:                        [macOS | Linux | Windows with WSL | Windows with Git Bash], RAM [__ GB]
Ollama running, gemma4:e4b pulled: [yes | no]
GEMINI_API_KEY set in the environment: [yes | no]
Team and roles:                 [names]
```

---

## 0. Before anything else

You are Claude Code, running in the root of the Munim repository at Hacktoberfest Hack Day Pune (MLH, 13 Oct 2026). You will build Munim end to end. You start from a folder of planning documents and finish with a tested, documented, demo-ready application. You work unattended until the Definition of Done in section 8 holds or a stop condition applies.

**Event rule.** The hackathon requires the project to be built at the event. Treat the event as started only if one of these is true:
- The confirmation block above has a real kickoff time.
- The human's message, or the `/goal` condition, states the kickoff time and says this folder was created at the event.

If neither is true:
1. Create `docs/PROGRESS.md` if it is missing and append `STATUS: BLOCKED (event start not confirmed; human action: fill the kickoff block in docs/planning/CLAUDE_CODE_PROMPT.md)`.
2. Tell the human in one sentence.
3. Stop. Until the event start is confirmed, write no application code, tests, scripts, templates or styles.

**Precedence.** This prompt adds Claude Code mechanics to `docs/planning/MASTER_PROMPT.md`, which you read in Step 0. Where the two differ, this prompt wins. These sections of MASTER_PROMPT are binding:
- 6, non-negotiable rules
- 7, interface contracts
- 8, implementation notes
- 9, building the interface
- 11, evaluation and honesty
- 12, when to stop
- 13, Definition of Done
- 15, never claim

The event rule above replaces MASTER_PROMPT section 0. Its section 1 applies only if the documents are missing (Step 0.2).

**What Munim is, in one paragraph.** Munim is a local-first, open-source web application for small Indian suppliers chasing late payments.
1. Gemma 4 reads phone photos of a tax invoice, a delivery challan and a purchase order.
2. Deterministic code checks the fields: GSTIN checksum, GST arithmetic, dates, and agreement between the papers.
3. When a check fails, Munim re-reads that one box and shows the correction as a red-pen strike with the new value in ballpoint handwriting.
4. After the user confirms, Munim computes the due date and compound interest under the MSMED Act.
5. It prints an evidence file with a draft notice in English and Hindi.

The model proposes; code disposes.

## 1. How you work in this session

### 1.1 Autonomy
- The human may be away for hours. Do not ask questions, do not enter plan mode, and do not use the AskUserQuestion tool. When something is unspecified, take the simplest choice that fits the documents. Record it under "Decisions" in `docs/PROGRESS.md` and continue.
- The only reasons to stop are in MASTER_PROMPT section 12. Before stopping for any of them, make the last line of `docs/PROGRESS.md` `STATUS: BLOCKED (<reason>; human action: <exact action>)`. Then say the same in one short paragraph.
- A `/goal` may be active. Its evaluator reads only this conversation; it does not open files or run commands. At the end of every task and every gate, show in your reply the verification command you ran and its key output lines (a few lines, not the whole log). If you skip this, the evaluator cannot see your progress.

### 1.2 Memory and context
- `CLAUDE.md` is loaded in every session and imports `AGENTS.md`; these are your standing rules. Files in `.claude/rules/` add rules automatically when you work on matching paths. Follow them.
- `docs/PROGRESS.md` is your external memory. Use the template in Appendix B and update it after every task. Its last line is always the `STATUS:` line.
- After a compaction or a resumed session, a SessionStart hook prints the tail of `docs/PROGRESS.md` and the next open tasks. Run the `/pickup` skill (or follow its steps) before anything else.
- Keep the context lean:
  - Use quiet flags: `pytest -q --tb=short`, `ruff --quiet`.
  - Cut long output with `| tail -n 60`.
  - Read big files by section.
  - Hand wide searches to the built-in Explore subagent.
  - Never paste whole lock files, fixtures or logs into the conversation.

### 1.3 Task list
- Create your task list from `docs/TASKS.md`: one item per id (T0.0 to T6.9), plus T0.10 in section 4.
- Keep exactly one item in progress. Mark it done, and tick its box in `docs/TASKS.md`, only after its verification passed in this session.

### 1.4 Commits
- Make one commit per task.
  - Use a conventional prefix (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`).
  - The subject line says what changed. The body says why and names the verification command and its result.
  - Add the trailer `Assisted-by: Claude Code (<model id, if you know it>)`. Keep any attribution lines Claude Code adds by itself.
- Never push, force, rewrite history or use `--no-verify`. The human pushes to the public repository.
- Never commit `data/`, `.env`, `eval/real/`, real documents, or images outside `eval/fixtures/` and `docs/screens/`.
- Record `git rev-parse --short HEAD` in `docs/PROGRESS.md` when a gate starts. Reviewers use it as the diff base.

### 1.5 Hooks
The hooks are configured in `.claude/settings.json`. You write their scripts in T0.10, and until the scripts exist the hooks do nothing.

| Hook | Script | What it does |
| --- | --- | --- |
| PreToolUse on Edit and Write | `scripts/hooks/pre_write_guard.py` | Blocks writes that would leak secrets or personal data, or touch protected paths (Appendix A.1) |
| PostToolUse on Edit and Write | `scripts/hooks/post_edit.py` | Runs fast checks on the file you just edited (Appendix A.2). Exit-2 feedback means "fix this now, before the next step" |
| SessionStart (startup, resume, compact) | (shell one-liner in settings) | Prints the build-log tail and the next open tasks |

Never edit `.claude/settings.json`, and never weaken a hook to get past it. If a hook is wrong, fix its script and its test (failing test first) and record the fix in `docs/PROGRESS.md`.

### 1.6 Subagents
Reviewers live in `.claude/agents/`. They can read and run commands but do not edit files. They report and you fix.

| Agent | Use it |
| --- | --- |
| `domain-verifier` | End of Gate 1; after any change to money, dates, ids, `verify/`, `clock.py` or `rules/`; end of Gate 4 (numbers in the UI and the evidence file); final pass in Gate 6 |
| `test-auditor` | End of every gate |
| `design-reviewer` | After each page is first built (through `/design-pass`); end of Gates 3, 4 and 5; final pass in Gate 6 |
| `security-reviewer` | End of Gates 3 and 5; after any change to uploads, middleware, settings, logging or providers; final pass in Gate 6 |

Brief every reviewer with this template:
```
Scope: git diff <gate-start-sha>..HEAD, plus <specific files if any>
Check against: <document and section numbers>
Context: <what changed, decisions and known limits from PROGRESS.md>
Return: a findings table (severity high | medium | low, file:line, rule or doc section, problem, evidence, suggested fix), or "No findings" with what you checked.
Do not edit files.
```
- Fix every high and medium finding, then re-run the affected checks. Log low findings under "Follow-ups".
- If you disagree with a finding, write down why in "Decisions"; never ignore one silently.

Builder subagents (general-purpose) can build in parallel only on disjoint files. Brief them with this template:
```
Task: <TASKS id and summary>
You own (may create or edit): <paths>
Do not touch anything else, especially pyproject.toml, uv.lock, Makefile, CLAUDE.md, .claude/, docs/PROGRESS.md, docs/TASKS.md.
Read first: <doc sections>
Done when: <tests and command that must pass>
Do not commit. Do not add dependencies; ask for them in your report.
Return: files changed, commands run with results, open questions.
```
- You review their diff, add any dependencies, run the tests and commit.
- Never run two agents on the same file.
- Section 4 lists the safe parallel pairs for each gate.

### 1.7 Skills
| Skill | Purpose |
| --- | --- |
| `/gate N` | Close a gate |
| `/check-all` | Full quality suite |
| `/design-pass` | Screenshots and design review |
| `/demo-run` | Rehearse the demo on the replay provider |
| `/pickup` | Re-orient after compaction or resume |
| `/build-log` | A progress summary for the human |

You may invoke these yourself or follow the steps in their `SKILL.md` files.

### 1.8 Time
Kickoff and deadline are in the block above. Run `date` at the start of each gate and log the time elapsed. Act on these triggers:

| Trigger | Action |
| --- | --- |
| Kickoff + 6 h and Gate 3 not closed | Switch to the fallback scope in `docs/PRD.md` section 10, log it, then go on to Gate 4 with the reduced scope |
| Deadline - 3 h | No new features. Finish Gate 5 essentials, then Gate 6 |
| Deadline - 1 h 30 min | Release tasks only. `main` must be green, the README true, `docs/PROGRESS.md` final |

If no deadline is given, assume kickoff + 10 h. A message from the human overrides any of these.

### 1.9 Evidence
Never say that something works, passes or measures X unless you ran the command in this session and saw the result. Copy the command and its key line into `docs/PROGRESS.md`. Never fabricate numbers, screenshots, citations, reviewer approvals or model results.

## 2. Step 0: orientation and first commits (about 20 minutes)

0.1. Run `date`, `git status` and `git rev-parse --is-inside-work-tree`. If this is not a repository, run `git init -b main`. Do not change global git configuration. If commits fail because no identity is set, set one for this repository only, using the team name from the block above, and log it.

0.2. Confirm that the planning files exist: `DESIGN.md`, `AGENTS.md`, `README.md`, `docs/PRD.md`, `docs/DOMAIN_RULES.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/AI_SPEC.md`, `docs/TESTING.md`, `docs/SECURITY_PRIVACY.md`, `docs/CONTENT.md`, `docs/TASKS.md`, `docs/planning/MASTER_PROMPT.md`.
- If `docs/PRD.md` is missing but `MUNIM_ONE_PROMPT.md` is present, extract it with its Part 1 script into this folder.
- If neither is present, stop with BLOCKED.

0.3. Read these files in full: `AGENTS.md`, `docs/planning/MASTER_PROMPT.md`, `docs/PRD.md`, `docs/DOMAIN_RULES.md`, `docs/ARCHITECTURE.md`, `docs/TASKS.md`. Skim the rest. Read each remaining document in full at the start of the gate that needs it (section 4).

0.4. List exactly the files that existed before you started. In a fresh repository use `git ls-files --others --exclude-standard` (or `find . -type f -not -path './.git/*'`). If the repository was cloned and the planning pack is already committed, use `git ls-files` and record that commit's sha and date (`git log --reverse --format='%h %ci %s' | head -n 3`). Create `docs/PROGRESS.md` from Appendix B with:
- the confirmation details
- that list, under "Pre-event materials"
- the preflight results from MASTER_PROMPT section 5 (Python, uv, git, node, make, Ollama and its models)

0.5. Create `.gitignore` from Appendix C.

0.6. Commit:
- If the planning pack is not committed yet, make commit 1, `docs: add planning pack prepared before the event`, with only the pre-existing files, unchanged. If it is already committed (a cloned repository), skip this commit and point to the existing one under "Pre-event materials".
- Then commit 2, `chore: start build log and ignore rules`.

0.7. Write `docs/PLAN_REVIEW.md` (40 lines or fewer): contradictions, gaps or risks you found in the documents, and how you will resolve each. Fix trivial inconsistencies in the documents in the same commit. Commit.

Then start Gate 0.

## 3. Conventions

### 3.1 Layout and tooling
Follow `docs/ARCHITECTURE.md` section 2 exactly:
- a uv workspace with packages `munim_core`, `munim_ai`, `munim_web` and `munim_mcp` (placeholder until the stretch tasks), using a `src/` layout
- Python 3.12
- one root `pyproject.toml` that holds tool configuration and a `dev` dependency group

Suggested Makefile recipes (adapt them, and log any deviation):

| Target | Recipe |
| --- | --- |
| `install` | `uv sync --all-packages --all-groups` then `uv run pre-commit install` then `uv run playwright install chromium firefox` |
| `run` | `uv run munim` (a console script that starts uvicorn on 127.0.0.1:8765) |
| `test-fast` | `uv run pytest -q -m "unit or property" --tb=short` |
| `test` | `uv run pytest -q -m "not e2e and not live" --tb=short` with coverage |
| `e2e` | `uv run pytest -q -m e2e --tb=short` (pytest-playwright, Chromium and Firefox) |
| `screens` | the screenshot script for every page, 360/768/1440 px, en and hi |
| `eval` | `uv run python eval/run_eval.py` (provider from `MUNIM_PROVIDER`, default `replay`) |
| `check` | ruff check, ruff format --check, mypy, lint-imports, bandit, design_lint, check_contrast, check_fonts, check_i18n, check_licences, then `test` |
| `ci` | `check`, then `e2e`, then `eval` on replay with report-schema validation |

If you add `pytest-playwright` or any other tool not in `docs/ARCHITECTURE.md` section 11, add a row to `THIRD_PARTY.md` in the same commit.

### 3.2 Test markers
`unit`, `property`, `integration`, `contract`, `golden`, `e2e`, `a11y` and `live`. Live-model tests are skipped unless `MUNIM_LIVE=1`.

Tests never touch the real `data/` directory: they use a temporary `MUNIM_DATA_DIR`.

### 3.3 Messages and parameters
Core findings carry `message_key` and string `params`:
- Keys ending in `_paise` hold integer paise as digits.
- Keys ending in `_date` hold ISO dates.
- The web layer formats them per language (Indian grouping, `12 Oct 2026` or the Hindi equivalent).
- Core never formats for display.

## 4. Gate playbook

Each gate below lists what to read first, what to build, safe parallel work, the pitfalls we already know about, and how to close it. Close every gate with `/gate N`, which runs its exit commands from `docs/planning/MASTER_PROMPT.md` section 10, the reviewers, and the bookkeeping.

### Gate 0: foundations (T0.0 to T0.10)

- **Read:** `docs/TASKS.md` Gate 0; MASTER_PROMPT sections 5 and 9; `DESIGN.md` front matter and sections 2, 3 and 12; `docs/TESTING.md` sections 7 and 10.
- **Parallel:** one builder subagent may own `scripts/design_lint.py`, `scripts/check_contrast.py`, `scripts/check_fonts.py`, `scripts/build_tokens.py` and their tests in `tests/scripts/`. You own the workspace, `Makefile`, CI and pre-commit.

**Pitfalls**
- **Workspace.** Use `[tool.uv.workspace] members = ["packages/*"]` in the root. mypy is strict for `munim_core` and `munim_ai`; the web package is typed but not strict.
- **Fonts.** Prefer Fontsource packages, which ship WOFF2 with per-script subsets and the OFL licence:
  1. Run `npm view @fontsource/mukta version`, then `npm pack @fontsource/mukta@<that version>`, and the same for `@fontsource/kalam`.
  2. Extract the archives.
  3. Copy the latin, latin-ext and devanagari WOFF2 files and the licence files into `static/fonts/`.
  4. Write `@font-face` rules, copying their `unicode-range` values from the package CSS.

  If npm is not available, download the TTFs from the google/fonts repository and convert them with fontTools. Both converting to WOFF2 and reading it in `check_fonts.py` need the `brotli` package. If Mukta lacks `tnum`, apply the fallback in `DESIGN.md` section 3.
- **`design_lint.py`.** It must allow `tokens.css`, the marked focus ring and the stamp's capitals, and skip vendored files in `static/js/vendor/`. Each rule needs a passing and a failing sample in its tests.
- **Exit codes.** Every check script exits 0 when clean, 1 when it found problems, and 2 or more on its own errors. The post-edit hook relies on this.
- **Licence file.** Fetch the exact text with `curl -fsSL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE`. Never retype or paraphrase it.
- **`check_contrast.py`.** It reads the YAML front matter of `DESIGN.md` and checks the pairs listed in its section 2 table. The expected values are ink on bond 16.29, hairline-strong on sheet 3.59, and tick on its wash 4.59.
- **CI.** Pin actions by commit SHA, which you can resolve with `git ls-remote https://github.com/actions/checkout refs/tags/v4`. If the network blocks that, pin by tag and log a follow-up.

**T0.10: hook scripts (Claude Code specific)**
1. Write `scripts/hooks/pre_write_guard.py` and `scripts/hooks/post_edit.py` to the specification in Appendix A, standard library only.
2. Test them in `tests/hooks/` by piping sample JSON to each script with `subprocess` and asserting exit codes and messages.
3. Prove they are live:
   - Create `scratch_hook_check.py` that uses an undefined name (ruff F821, which `--fix` cannot repair; an unused import would be fixed silently). Expect PostToolUse feedback, then delete the file.
   - Try to write `.scratch/guard_check.txt` containing `AIza` followed by 35 `x` characters (an obviously fake key). Expect a PreToolUse block from rule G4.
   - Log both results in `docs/PROGRESS.md`.

**Close:** run `/gate 0`; test-auditor reviews `tests/scripts` and `tests/hooks`. Show the tail of `make check` and `uv run python scripts/check_contrast.py` in your reply.

### Gate 1: core domain (T1.1 to T1.8)

- **Read:** `docs/DOMAIN_RULES.md` in full, `docs/TESTING.md` sections 2 and 3, MASTER_PROMPT section 7.
- **Parallel:** a builder may own `ids.py` and its tests while you do `money.py`, `dates.py` and `clock.py`. Everything else in this gate stays sequential.

Work test-first: write the failing test, see it fail, write the code, see it pass.

**Pitfalls**
- **Decimal.** Build Decimals from strings or integers, never from floats. Use `quantize(Decimal(1), rounding=ROUND_HALF_UP)`.
- **Period starts.** Compute each period start as `start + relativedelta(months=k)` from the original start. Never chain month additions, because they drift after a short month.
- **Partial months.** For a partial month, D is the number of days from this period's start to the next period's start.
- **Bank Rate.** For each period, use the rate with the latest `effective_from` on or before the period start. If there is none, raise a typed error that the UI turns into "Add a Bank Rate effective on or before <date>".
- **Golden tests (exact paise).**

  | Case | Expected |
  | --- | --- |
  | 3 months | 2,283,919 |
  | 12 months | 9,780,909 |
  | Demo case: interest | 4,290,370 |
  | Demo case: total | 54,290,370 |
  | Demo case: days late | 177 |

  Also assert closed-form agreement: at most 1 paisa of difference per month.
- **python-stdnum exceptions.**

  | Exception | Rule id |
  | --- | --- |
  | `InvalidLength`, `InvalidFormat` | `GSTIN-FORMAT` |
  | `InvalidComponent` | `GSTIN-STATE` |
  | `InvalidChecksum` | `GSTIN-CHECKSUM` |

  Normalise case, spaces and hyphens before validating, and record the normalisation.
- **Look-alike repair.** Accept only a unique passing candidate, and mark it `needs_review`.
- **Rule sync test.** Rule ids must match across `docs/DOMAIN_RULES.md`, `rules/*.yaml` and the code. Every `message_key` must exist in both language files once they exist. Until Gate 3, assert against a key list in `rules/`.

**Close:** run `/gate 1`; domain-verifier (independent recomputation) and test-auditor. Show the coverage line, the golden test names passing, and the `mypy --strict` result.

### Gate 2: AI layer (T2.1 to T2.8)

- **Read:** `docs/AI_SPEC.md` in full, `docs/TESTING.md` section 4, `docs/SECURITY_PRIVACY.md` sections 4 and 5.
- **Parallel:**
  - A builder owns `scripts/gen_fixtures.py`, `eval/` and `tests/eval/` (generator, ground truth, injected faults, report schema).
  - You own `packages/munim_ai/` (schemas, normalise, imageprep, providers, extract, repair, preflight).

**Pitfalls**
- **Replay keys.** Key replays as in `docs/AI_SPEC.md` section 5.3: the hash of the original uploaded bytes plus paper kind plus prompt version. Re-reads add the field and the box. Never key on re-encoded bytes.
- **Fixture images.** Commit fixture images as JPEGs no larger than 1568 px on the long edge, so `imageprep` does not re-encode them.
- **Labelling recordings.** Mark responses you write by hand `"recorded_from": "synthetic"` and live recordings `"live"`. Reports state which kind they used.
- **Ollama.**
  - Preflight with `GET /api/tags`, then a tiny vision probe and a JSON probe.
  - Use `format` only if the JSON probe passed.
  - Use temperature 0, one request at a time, and a 90 s timeout.
  - Record the model digest if `ollama show` or the API provides it.
- **Gemini.**
  - Use it only with consent and an environment key.
  - Delete the uploaded file after each call.
  - Never log the key; a test checks with a canary key.
  - Tests use a fake client.
- **"Wrong and passed".** Computing it means running the verify rules on the values that were read, against the ground truth.

**Live run.** If Ollama and the model are present:
1. Warm the model.
2. Run a live evaluation on at least 10 synthetic papers.
3. Record live fixtures and log the latency.

Otherwise, log "pending-live" and continue.

**Close:** run `/gate 2`; test-auditor. Show the evaluation summary lines and say which provider produced them.

### Gate 3: web vertical slice (T3.1 to T3.9)

- **Read:** `docs/ARCHITECTURE.md` sections 4 to 10, `docs/API.md`, `docs/SECURITY_PRIVACY.md`, `DESIGN.md` in full, `docs/CONTENT.md` section 1.
- **Before any template:** write `docs/DESIGN_PLAN.md` as item 1 of MASTER_PROMPT section 9 describes, and commit it.
- **Parallel:** a builder owns `packages/munim_web/src/munim_web/i18n/`, the i18n loader and `scripts/check_i18n.py` data (seeded from `docs/CONTENT.md`). You own the app, database, routes, templates and static files.

**Pitfalls**
- **Escaping.** Render through Starlette's `Jinja2Templates`. Write the XSS escaping test (`docs/TESTING.md` section 8) before the first page, not after.
- **htmx under a strict CSP.** Follow MASTER_PROMPT section 8:
  - vendor htmx 2.x: `npm view htmx.org version`, `npm pack htmx.org@<that 2.x version>`, then copy `dist/htmx.min.js` and the licence into `static/js/vendor/`
  - add the `htmx-config` meta with `includeIndicatorStyles`, `allowEval` and `allowScriptTags` all false
  - no `hx-on`, no `js:` values, no bracketed event filters
  - CSRF header code goes in `static/js/csrf.js`
- **CSRF.** Use a cookie plus a meta tag plus a header, compared with `secrets.compare_digest`. Test a missing token and a wrong token.
- **Host allow-list.** Include the port. Test with a forged Host header.
- **Background reads.** Use `asyncio.create_task` with a semaphore and persist each state change. On startup, recover papers stuck in `reading`.
- **Viewer.** Use an SVG overlay with `viewBox="0 0 1000 1000"` and `preserveAspectRatio="none"` inside a box with the image's aspect ratio (MASTER_PROMPT section 8).
- **E2E server.** A pytest fixture starts uvicorn on a free port with `MUNIM_PROVIDER=replay` and a temporary data directory. Wait for readiness with polling, never with fixed sleeps.

**Close:**
1. Run `/design-pass` for every page built so far.
2. Run `/gate 3`: security-reviewer, design-reviewer and test-auditor.
3. Show the result of `make e2e` for E2E-1 and E2E-3 and the axe summary.

### Gate 4: signature moments (T4.1 to T4.6)

- **Read:** `DESIGN.md` sections 4.7 to 4.9 and 5; `docs/DOMAIN_RULES.md` sections 4 to 6; `docs/CONTENT.md` section 2; `docs/DEMO_SCRIPT.md`.

**Pitfalls**
- **Red pen.** Implement the reduced-motion path. Remove `data-animate` after the animation runs. Test that the struck original stays in the DOM.
- **Stamp.** Show the stamp only when the case is confirmed and no blocking finding is unresolved. Decide that on the server and test both states.
- **Clock strip.** The strip must show exactly the core results. An integration test asserts that the demo case renders ₹5,42,903.70, ₹42,903.70 and 177 days.
- **Print.**
  - Use `@page`, and `print-color-adjust: exact` for status washes.
  - PDFs come only from Playwright Chromium (`page.pdf()` works only in Chromium).
  - Use `emulate_media(media="print")` for print screenshots.
- **Golden HTML.** Normalise volatile parts (CSRF tokens, ULIDs, timestamps) before diffing. Bless golden files only after you look at them.
- **Notices.** Notices are plain-text Jinja (`.md.j2`) filled with values already formatted for the language. All wording comes from `docs/CONTENT.md`.

**Close:**
1. Run `/demo-run` and show its summary.
2. Run `/gate 4`: domain-verifier (numbers on the screen, in the working and in the evidence file against core) and design-reviewer (including print screenshots).

### Gate 5: quality pass (T5.1 to T5.7)

- **Read:** `docs/TESTING.md` sections 5 to 7; `DESIGN.md` sections 7, 8 and 12; the Hindi notes in `docs/CONTENT.md`.

**Pitfalls**
- **Devanagari.** Check line-height and clipping at 360 px. Set `lang` attributes on the root and on inline fragments.
- **Accessibility.** Check focus order, `aria-live` for status changes, and 44 px touch targets.
- **Mobile.** The claims table becomes a list on small screens.
- **Firefox.** Check layout and print differences in Firefox.
- **axe and SVG.** Fix accessible names on the SVG boxes; do not silence axe rules.
- **Hindi.** You cannot certify Hindi. Keep the "unreviewed" footer. Check the strings against the glossary, and list awkward strings for the human reviewer under "Follow-ups".

**Close:** run `/gate 5`: design-reviewer, security-reviewer and test-auditor. Show the tail of `make ci`.

### Gate 6: release (T6.1 to T6.5, then stretch tasks T6.6 to T6.9 in order)

- **Read:** `docs/SUBMISSION.md`, `docs/AI_CONTRIBUTION.md`, `README.md`.

**Steps**
1. **Clean-clone test.** Clone the repository into a temporary directory, run `make install` and `make ci` there with the replay provider, and log the commands and results.
2. **Placeholders.** Fill bracketed placeholders only with true values. Leave a visible `[TODO human: ...]` for anything you cannot know: repository URL, maintainer email, Hindi reviewer, video link, and the model digest if you were offline.
3. **`docs/AI_CONTRIBUTION.md`.** Name Claude Code and the model, say what it wrote, say what the humans did (decisions, reviews, device testing), and list the pre-event materials exactly as logged in Step 0.
4. **Final reviewers.** Run a final pass with all four reviewers and fix high and medium findings.
5. **Tag.** Tag `v0.1.0` locally. Do not push.
6. **Finish.** Write the final report (section 9) to `docs/FINAL_REPORT.md`, show it in the conversation, and make `STATUS: DONE` the last line of `docs/PROGRESS.md`.

## 5. Interface craft: making it not look generated

Follow `DESIGN.md` and MASTER_PROMPT section 9. In addition:

1. **Look at what you built.** `/design-pass` produces PNG screenshots. Open each one with the Read tool and write two or three sentences about what you actually see before you judge it. Never approve a page you have not looked at.
2. **Critique each page in this order.** Fix before moving on.
   1. Is the case list a table and not cards?
   2. Is there exactly one primary button?
   3. Are all labels sentence case, with no all-caps eyebrow text?
   4. Is body text left aligned, with no centred paragraphs?
   5. Are there no shadows, gradients, pills or emoji?
   6. Do numbers use tabular figures and right alignment in tables?
   7. Does Devanagari render in Mukta without clipping?
   8. Is a focus ring visible on every control?
   9. Does every empty state name a next action?
   10. Do errors say what happened and what to do?
3. **Remove one thing.** After a page passes, take away one decoration, border or line of copy that is not doing a job.
4. **Keep the drama in one place.** The red pen and the stamp are the only animated moments. No hover lifts, no counters, no entrance animations.
5. **Write copy from the deck.** All copy comes from `docs/CONTENT.md`. A new string goes into both language files in the same commit, in the same voice.

## 6. Live model protocol

- **At Gate 0 preflight:** run `curl -s http://127.0.0.1:11434/api/tags`. If a `gemma4` tag is listed, warm it with one tiny request and log the latency.
- **During development:** tests use the replay provider or the fake Ollama transport. Live tests run only with `MUNIM_LIVE=1`, on 10 papers or fewer, to save time.
- **If Ollama or the model is missing:** mark the live items "pending-live" and keep building on replay. In the final report, give the exact commands for the human: `ollama pull gemma4:e4b`, then `MUNIM_LIVE=1 make eval`, then re-record the demo fixtures.
- **Never present a replay run as a live read**, in the UI, the README or the conversation.

## 7. When things go wrong

| Situation | Do this |
| --- | --- |
| The same test fails three times | Stop editing. Write a minimal reproduction, re-read the relevant doc section, list your assumptions in `docs/PROGRESS.md`, then fix the cause |
| A dependency will not install | Check registry access, try the previous compatible version, log it. Never vendor-modify python-stdnum |
| Playwright browsers will not install | On Linux try `uv run playwright install --with-deps chromium`. If Firefox still fails, run E2E in Chromium and log Firefox as pending |
| A permission rule denies a command | Do not work around it with another program or `sh -c`. Use the allowed alternative, or log BLOCKED if it is essential |
| A hook blocks you | Read its message and fix the cause. If the hook is wrong, fix the hook with a test first |
| Context is getting full | Finish the current task, commit, update `docs/PROGRESS.md`. After compaction, run `/pickup` |
| A flaky E2E test | Wait on conditions with locators and `expect`, never `sleep`. Seed the data and isolate the data directory |
| The model is slow or wrong in a live run | Record it as a finding. Do not tune prompts without re-running the evaluation and bumping `prompt_version` |
| A design or spec contradiction | Pick the safer reading, fix the documents so they agree, and log it |

## 8. Definition of Done

All items of MASTER_PROMPT section 13, plus:
13. The hook scripts are tested, and shown live in `docs/PROGRESS.md`.
14. The final reviewer reports have no open high or medium findings.
15. `/demo-run` passes on the replay provider, and on a live provider if one was available.
16. The last line of `docs/PROGRESS.md` is `STATUS: DONE`.

Before writing `STATUS: DONE`, print an evidence block in the conversation, one line per item: the item, PASS or PENDING, and the command that proved it. Example:
```
1  make ci ..................... PASS  (make ci, exit 0)
5  golden clock values ......... PASS  (pytest -k golden: 5 passed)
...
```
An item may be PENDING only for human-only facts or a missing live model, and each PENDING item names the human action needed.

## 9. Final report

Write it in the format of MASTER_PROMPT section 14, in 400 words or fewer, plain language, with no marketing. Show it in the conversation and save it as `docs/FINAL_REPORT.md`. Include:
- the gate reached
- the Definition of Done lines
- the evaluation numbers and which provider produced them
- the pending-live items
- the human actions: Hindi review, Bank Rate confirmation, pushing to GitHub, video, submission form
- deviations from the documents and why

---

## Appendix A: hook script specifications

Both scripts read the hook JSON from stdin, use only the standard library, and run in under 20 s for typical files. They resolve paths relative to the `CLAUDE_PROJECT_DIR` environment variable, falling back to the `cwd` field in the input. They exit 0 when they have nothing to report.

### A.1 `scripts/hooks/pre_write_guard.py` (PreToolUse on Edit and Write)

**Input.** Read `tool_name` and `tool_input` from stdin.
- `tool_input.file_path` is the path.
- The new text is `tool_input.content` for Write, `tool_input.new_string` for Edit, and the joined `new_string` values in `tool_input.edits` if present.

**Rules.** Block with exit 2 and a one-line reason on stderr when any of these hold:

| Id | Rule |
| --- | --- |
| G1 | The path resolves outside the project directory. The message tells Claude to put scratch files under `.scratch/` in the repository, which git ignores |
| G2 | The file name is `.env`, or matches `.env.*` other than `.env.example` |
| G3 | The path is under `data/`, `eval/real/` or `.git/` |
| G4 | The new text contains a likely secret: `AIza[0-9A-Za-z_\-]{35}`, `-----BEGIN [A-Z ]*PRIVATE KEY-----`, `gh[pousr]_[0-9A-Za-z]{36}`, or `sk-[A-Za-z0-9_\-]{20,}`. The message names the rule, never the matched text |
| G5 | The new text contains a 12-digit number that looks like an Aadhaar number: optionally grouped 4-4-4 with spaces or hyphens, first digit 2 to 9, and passing the Verhoeff checksum (implement Verhoeff in the script). Exception: the path is under `tests/` or `eval/fixtures/` and the same line contains the word `synthetic` |

**Message format:** `Blocked by pre_write_guard <rule id>: <reason>. Fix: <what to do>.`

**Tests:** cover each rule's block and pass cases, plus malformed JSON input (exit 0 with a note in stderr).

### A.2 `scripts/hooks/post_edit.py` (PostToolUse on Edit and Write)

**Input.** Read `tool_input.file_path`. Ignore paths outside the project and under `.git/`, `.venv/`, `node_modules/` or `data/`.

**Before running anything:** if `.venv/` does not exist yet, exit 0 silently. Every `uv run` call in this script uses `--no-sync`, so the hook never installs or updates the environment.

**Checks by path.** Each check is skipped silently if the tool or script does not exist yet.

| Path | Checks |
| --- | --- |
| `*.py` | `uv run --no-sync --quiet ruff format <file>`, then `uv run --no-sync --quiet ruff check --fix --quiet <file>`. Report remaining ruff errors |
| `packages/munim_web/src/munim_web/templates/**`, `.../static/css/**`, `.../static/js/**` (except `static/js/vendor/`) | `uv run --no-sync --quiet python scripts/design_lint.py <file>` |
| `packages/munim_web/src/munim_web/i18n/*.json` | `uv run --no-sync --quiet python scripts/check_i18n.py` |
| `DESIGN.md` | `uv run --no-sync --quiet python scripts/build_tokens.py`, then `uv run --no-sync --quiet python scripts/check_contrast.py` |
| `rules/*.yaml`, `docs/DOMAIN_RULES.md` | the rule sync test, `uv run --no-sync --quiet pytest -q -k rule_sync` |

**Exit codes it relies on.** ruff check: 1 means violations remain. The Munim check scripts: 1 means findings. pytest: 1 means failures and 5 means no tests collected (skip). Any other non-zero code, a timeout, or a missing tool is a tool problem: note it in one stderr line and exit 0. Only findings block.

**Limits.** Each subprocess times out at 45 s. Never run the full test suite here.

**Output.** If any check failed, write a report of 40 lines or fewer to stderr (file, check, first relevant lines, then the line `Fix this before continuing.`) and exit 2. Otherwise exit 0 with no output.

**Tests:** a clean Python file, a file with an unused import (fixed silently, exit 0), a file using an undefined name (exit 2), a template containing `box-shadow` (exit 2), an i18n file missing a key (exit 2), a path outside the project (exit 0), and a missing `.venv/` (exit 0).

## Appendix B: `docs/PROGRESS.md` template

```markdown
# Build log

## Kickoff
- Kickoff (IST): 2026-10-13 HH:MM. Confirmed by: <confirmation block | human message | goal condition>
- Submission deadline (IST): HH:MM
- Machine: <os, RAM>. Live model: <gemma4:e4b present? digest?>. Hosted key present: <yes/no>
- Claude Code model: <id if known>

## Pre-event materials (present before the build started)
- <exact list from Step 0.4>
- These are planning documents and configuration. None is application code.

## Decisions
- <time> <decision>, because <reason>

## Follow-ups
- <low-severity findings, pending-live items, Hindi strings to review, human actions>

## Gates
| Gate | Started (sha, time) | Closed (time) | Exit evidence |
| --- | --- | --- | --- |

## Log
### <time> T<id> <title>
- Changed: <files, briefly>
- Checked with: `<command>`, which gave <key result line>
- Notes: <surprises, if any>

STATUS: IN PROGRESS (Gate 0)
```
Keep the `STATUS:` line last. When you append a log entry, insert it above that line.

## Appendix C: `.gitignore`

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
data/
eval/real/
.scratch/
.env
CLAUDE.local.md
.claude/settings.local.json
node_modules/
test-results/
playwright-report/
*.heic
*.HEIC
.DS_Store
```

## Appendix D: the `/goal` condition (for the human)

Replace HH:MM, then send this in Claude Code. It must stay under 4,000 characters.

```
/goal Kickoff was at HH:MM IST today and this folder was created at the event. Build Munim by following docs/planning/CLAUDE_CODE_PROMPT.md exactly; read it first. The goal is met only when this conversation shows, from commands Claude ran after its last code change: make ci exiting 0; the clock golden tests (2,283,919, 9,780,909 and 4,290,370 paise) passing; every E2E scenario in docs/TESTING.md passing in Chromium, and in Firefox or logged as pending with a reason; git status clean; and docs/PROGRESS.md ending with STATUS: DONE after the evidence block and final report. Also treat the goal as met when docs/PROGRESS.md ends with STATUS: BLOCKED and Claude has stated the reason and the exact human action needed. Never weaken a test or a check to pass, never commit real documents or secrets, never push. Stop after 300 turns.
```
