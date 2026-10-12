---
description: Run Munim's full local quality suite (make ci) and summarise results by layer, then fix failures in order. Use before closing a gate, before release, or when unsure whether the tree is green.
---

# Run the full quality suite

1. Run `make ci 2>&1 | tail -n 120`. If `ci` does not exist yet, run the targets that do exist, in this order: `check`, `e2e`, `eval`.
2. Summarise each layer in a short table with PASS, FAIL or NOT YET BUILT and the first failing item:
   - static: ruff, format, mypy, import-linter, bandit, pip-audit, licences
   - design: design_lint, contrast, fonts, i18n
   - unit and property tests
   - integration and contract tests
   - golden tests
   - e2e and accessibility
   - evaluation on replay
3. Fix failures in this order: static, design, unit and property, integration, golden, e2e, eval. After each fix, re-run only the failing layer, then the whole suite at the end.
4. Never weaken a test, a lint rule or a threshold to get green. If a rule is wrong, fix the rule and its test, and log the decision in `docs/PROGRESS.md`.
5. Show the final summary table and the last lines of the passing run in your reply.
