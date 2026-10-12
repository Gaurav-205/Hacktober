---
description: Rehearse the Munim demo from docs/DEMO_SCRIPT.md end to end with Playwright on the replay provider, check the reference numbers, and report timings. Use at the end of Gate 4, after any change to the workbench, clock or evidence file, and before release.
---

# Demo rehearsal

1. Make sure `tests/e2e/test_demo_script.py` exists and follows `docs/DEMO_SCRIPT.md` beat by beat:
   - create the demo case and set the as-on date to 13 Oct 2026
   - add the invoice with the misread buyer GSTIN, the challan and the purchase order
   - read all three papers
   - watch the GSTIN row go from "Doesn't match" to "Passed" through the red-pen sequence, with the struck original still present
   - confirm, and see the stamp
   - open "How this is worked out", and confirm the Bank Rate row
   - open the evidence file and switch the notice to Hindi
   - open the Evaluation page

   If the test is missing, write it, marked `e2e`.
2. Assert the reference values from `docs/DOMAIN_RULES.md` section 5.3 on screen:
   - due date 19 Apr 2026
   - 177 days late
   - interest ₹42,903.70
   - amount owed ₹5,42,903.70

   These hold only while the Bank Rate is the seeded placeholder 5.75%; the test sets it explicitly.
3. Run it in Chromium with tracing on: `uv run pytest -q -m e2e -k demo_script --tracing retain-on-failure` (or the equivalent for your setup). Record the duration of each beat.
4. Check the honesty labels: the "Recorded responses" badge is visible on replay, and the "Draft for review. Not legal advice." line appears on the evidence file and the notice.
5. If a live provider is available (`MUNIM_LIVE=1`), run the same flow once live, with no numeric assertions on model output beyond the checks. Record the timings and the provider badge.
6. Show a short summary in your reply: PASS or FAIL per beat, the timings, and any deviation from `docs/DEMO_SCRIPT.md`. Log it in `docs/PROGRESS.md`.
