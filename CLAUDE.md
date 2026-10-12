@AGENTS.md

# Munim: Claude Code notes

This file loads in every session. `AGENTS.md` (imported above) holds the project rules. The specification is in `docs/`. The build is driven by `docs/planning/CLAUDE_CODE_PROMPT.md`, which adds Claude Code mechanics to `docs/planning/MASTER_PROMPT.md`.

## Where things are
- What and why: `docs/PRD.md`.
- Rules and golden numbers: `docs/DOMAIN_RULES.md`.
- Structure: `docs/ARCHITECTURE.md`. Routes and headers: `docs/API.md`. Model layer: `docs/AI_SPEC.md`.
- Tests: `docs/TESTING.md`. Threat model: `docs/SECURITY_PRIVACY.md`.
- Look: `DESIGN.md`. Copy in English and Hindi: `docs/CONTENT.md`.
- Order of work: `docs/TASKS.md` (gates 0 to 6, with checkboxes).
- Build state: `docs/PROGRESS.md`. Its last line is the `STATUS:` line.
- After a compaction or a resumed session, run `/pickup` before anything else.

## How we work here
1. **One task at a time.** Take tasks from `docs/TASKS.md` in order. Write tests first in `munim_core` and `munim_ai`. Do not start a gate before the previous gate's exit commands pass.
2. **Evidence, or it didn't happen.** Every claim in `docs/PROGRESS.md` cites a command you ran in this session and its key result. Show the key output lines in your reply too, because a `/goal` evaluator only sees the conversation.
3. **Commits.** One per task, with a conventional prefix and a body that says why. Add the trailer `Assisted-by: Claude Code (<model>)`. Never push, never rewrite history, never use `--no-verify`.
4. **Hooks.** These are set up in `.claude/settings.json` and do nothing until their scripts exist (written in T0.10).
   - A pre-write guard blocks secrets, Aadhaar-like numbers, `.env`, `data/`, `eval/real/` and paths outside the repo.
   - A post-edit hook runs ruff, the design lint, the i18n check or the contrast check on the file you edited.
   - If a hook blocks you, fix the cause. Never edit `.claude/settings.json` or weaken a hook. If a hook is wrong, fix its script with a failing test first, and log it.
5. **Reviewers.** `.claude/agents/` holds `domain-verifier`, `design-reviewer`, `security-reviewer` and `test-auditor`. Use them at every gate close (`/gate N`) and whenever their description matches the change. They report; you fix high and medium findings.
6. **Parallel subagents.** Only on disjoint files, with explicit ownership in the brief. Subagents never commit or add dependencies; you integrate, test and commit.
7. **Lean context.** Use quiet test flags, `| tail -n 60` for long output, section reads of big files, and the Explore subagent for wide searches.
8. **Time.** The kickoff time and deadline are at the top of `docs/PROGRESS.md`. Run `date` at each gate start. Fallback triggers are in section 1.8 of the build prompt.

## Commands
- `make install`, `make run` (http://127.0.0.1:8765), `make check`, `make test`, `make test-fast`, `make e2e`, `make eval`, `make screens`, `make bless`, `make dossier-pdf`, `make fixtures`, `make ci`.
- Skills: `/gate N`, `/check-all`, `/design-pass`, `/demo-run`, `/pickup`, and `/build-log` (for the human).

## Never
- Commit or print real documents, real GSTINs, names, keys or Aadhaar numbers. Fixtures are synthetic and say so.
- Let model output decide a check, a number, or text shown to the user.
- Use floats for money, raw hex outside `tokens.css`, or hard-coded UI strings.
- Use "Verified" in UI copy. Quote an accuracy figure that is not in `eval/reports/latest.json`. Present a replay as a live read.
- Claim a model capability that `docs/AI_SPEC.md` marks unverified, unless you probed it and logged the probe.
