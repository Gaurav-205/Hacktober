---
description: Screenshot every Munim page at 360, 768 and 1440 px in English and Hindi, look at each image, run the design-reviewer subagent against DESIGN.md, and fix violations. Use after building or changing any page or template, and at the end of Gates 3, 4 and 5.
---

# Design pass

1. Make sure `make screens` exists. It runs a Playwright script that does the following:
   - starts the app on a free port with `MUNIM_PROVIDER=replay` and a temporary data directory
   - seeds the synthetic demo case in the states listed below
   - writes `docs/screens/<page>-<state>-<lang>-<width>.png` for widths 360, 768 and 1440 and languages en and hi

   If it does not exist, build it first, together with a test that it produces the expected file list.

   States:
   - case list: empty, and with rows
   - workbench: no papers, reading, read with failures, after repair, confirmed
   - evidence file: screen and print media
   - rules, evaluation, settings and about pages
2. Run `make screens`.
3. Open each new or changed PNG with the Read tool. For each one, write one or two sentences on what you actually see. Note anything wrong against the critique list in section 5 of `docs/planning/CLAUDE_CODE_PROMPT.md`.
4. Brief the `design-reviewer` subagent with:
   - the list of screenshots
   - the changed templates, CSS and JS (from `git diff --name-only <gate-start-sha>..HEAD`)
   - your own notes
5. Fix every high and medium finding. Re-run `make screens` for the affected pages and look again.
6. Run `uv run python scripts/design_lint.py` and `uv run python scripts/check_contrast.py`. Both must pass.
7. Do one removal pass: take away one decoration, border or line of copy that is not doing a job, and re-check.
8. Log in `docs/PROGRESS.md` what changed and why. Commit the code. Commit the screenshots only to `docs/screens/`, and only the ones the README and submission use.
