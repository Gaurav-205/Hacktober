---
description: Close a Munim build gate. Runs the gate's exit commands, runs the reviewer subagents for that gate, fixes findings, records evidence in docs/PROGRESS.md and commits. Use when every task of a gate in docs/TASKS.md is done.
argument-hint: "[gate number, 0 to 6]"
---

# Close gate $ARGUMENTS

1. Re-read the Gate $ARGUMENTS section of `docs/TASKS.md`, its row in `docs/planning/MASTER_PROMPT.md` section 10, and its section in `docs/planning/CLAUDE_CODE_PROMPT.md` section 4.
2. Check that every task box in the gate is ticked and has a log entry with evidence in `docs/PROGRESS.md`. If one is missing, finish that task first.
3. Run the gate's exit commands exactly. Show the last lines of each output in your reply; a `/goal` evaluator only sees the conversation.
4. Brief and run the reviewers for this gate, using the brief template in section 1.6 of the build prompt. Use the gate-start sha from `docs/PROGRESS.md` as the diff base.

   | Gate | Reviewers |
   | --- | --- |
   | 0 | test-auditor (tests for scripts and hooks) |
   | 1 | domain-verifier, test-auditor |
   | 2 | test-auditor |
   | 3 | security-reviewer, design-reviewer (after `/design-pass`), test-auditor |
   | 4 | domain-verifier, design-reviewer (including print), test-auditor |
   | 5 | design-reviewer, security-reviewer, test-auditor |
   | 6 | all four, as a final pass |

   Reviewers that do not depend on each other can run in parallel.
5. Fix every high and medium finding. Add a test first where the finding is a behaviour. Log low findings under "Follow-ups". If you disagree with a finding, record why under "Decisions".
6. Re-run the exit commands after the fixes and show the results.
7. Update the records:
   - Tick the gate's boxes in `docs/TASKS.md`.
   - Fill the gate's row in the "Gates" table of `docs/PROGRESS.md`: close time and exit evidence.
   - Append a log entry "Gate $ARGUMENTS complete" with the commands and outcomes.
   - Update the `STATUS:` line to the next gate.
8. Commit with `chore(gate): close gate $ARGUMENTS`, a body listing the exit commands and results, and the `Assisted-by` trailer.
9. Record the new gate-start sha (`git rev-parse --short HEAD`) and the time (`date`) for the next gate.
