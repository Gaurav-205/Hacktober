---
description: Re-orient after a compaction, a resumed session or a fresh session in the middle of the Munim build. Rebuilds working context from docs/PROGRESS.md, docs/TASKS.md and git, then continues with the next task. Use first thing after any context reset.
---

# Pick up the build

1. If `docs/PROGRESS.md` does not exist, this is a fresh start. Follow `docs/planning/CLAUDE_CODE_PROMPT.md` from section 0 instead of the steps below.
2. Read the last `STATUS:` line of `docs/PROGRESS.md`, the "Kickoff", "Decisions" and "Follow-ups" sections, the "Gates" table, and the last 5 log entries.
   - If the status is `BLOCKED`, read the reason. Continue only if the blocker is now resolved (for example, the human answered in the conversation). Otherwise restate the blocker in one paragraph and stop.
   - If the status is `DONE`, show the final report from `docs/FINAL_REPORT.md` and stop.
3. Run `date`, `git status --short | head -n 30`, and `git log --oneline -15`. Compare them with the log:
   - Uncommitted changes belong to the task in progress. Decide whether they are complete. If they are, run its verification and commit. If they are not, finish the task.
4. Find the next open task in `docs/TASKS.md` (the first `- [ ]`). Re-create the task list from there if it was lost.
5. Re-read the current gate's section in `docs/planning/CLAUDE_CODE_PROMPT.md` section 4, and the documents it names for that gate.
6. Check the time triggers in section 1.8 of the build prompt against the kickoff and the deadline.
7. Run `make test-fast` (or the closest existing target) to confirm the tree is healthy before continuing. Show the result.
8. Write a log entry "Picked up after <compaction | resume | new session>: next task T<id>". Then continue.
