---
description: Give the human a short status of the Munim build covering gate, recent commits, checks, blockers and next tasks. For the human to run when checking in.
disable-model-invocation: true
---

# Build status for the human

Read `docs/PROGRESS.md` (the `STATUS:` line, the Gates table, Follow-ups, and the last 5 log entries) and `docs/TASKS.md`. Run `git log --oneline -10` and `date`.

Reply in 15 lines or fewer, in plain language:
- The current gate and status, and the time since kickoff (and the time left to the deadline, if one is set).
- What was finished since the last check-in (from the log and commits).
- The last verification result, with the command.
- Anything blocked or pending-live, with the exact human action needed.
- The next three tasks.

Do not start new work in this turn unless the human asks.
