# Submission pack

**Event:** Hacktoberfest Hack Day Pune with Cloud Computing Club (MLH), 13 Oct 2026, in person.
**Primary track:** Best Open-Source AI Project. **Also enter:** Best Use of Gemma 4 (the same repository qualifies if the Gemma 4 use is substantial; MLH allows one submission in several challenges).

**Before submitting, re-read the live challenge pages and the event rules.** The Track 2 requirements below were read earlier and could not be re-fetched while this pack was written; treat them as "last known".

## Last known requirements (verify)

| Requirement | Source | Munim's answer |
| --- | --- | --- |
| Public repository with an OSI-approved licence | Track 2 challenge page (read earlier) | Apache-2.0, `LICENSE` at the root |
| Names an open-weight model and links its licence | same | Gemma 4, Apache 2.0, link in README and `docs/AI_CONTRIBUTION.md` |
| Substantial technical work | same | Verification engine, repair loop, payment clock, evaluation harness, accessibility, bilingual UI; shown in `docs/PROGRESS.md` and commit history |
| Plain-language explanation of what the AI contributed | same | `docs/AI_CONTRIBUTION.md` |
| Build at the event; libraries allowed | MLH event rules | History starts at kickoff; `THIRD_PARTY.md` |
| Code public and stays public | MLH rules | Repo public from the first push |
| Disclose AI coding tools | MLH rules | Table in `docs/AI_CONTRIBUTION.md` and `Assisted-by` trailers |
| Demos over pitches | MLH guidance | Working demo; script in `docs/DEMO_SCRIPT.md` |

## Checklist

- [ ] Repo is public; first commit time is after kickoff; no force-pushes rewriting history. **Not met: the build started before the kickoff (owner's decision, recorded in `docs/PROGRESS.md`). No history was rewritten.**
- [x] `LICENSE`, `README.md`, `THIRD_PARTY.md`, `docs/AI_CONTRIBUTION.md` complete with no bracket placeholders.
- [ ] README states: what it is in one paragraph; screenshots; install in under 10 commands; model and licence; privacy; measured results (from `latest.json`); known limits; how to contribute.
- [ ] No real documents, keys or personal data anywhere in the history (`git log -p | grep` for patterns; run secret scanner).
- [ ] CI is green on `main`.
- [ ] `make run` works from a clean clone on a second machine.
- [ ] Demo video (90 to 120 seconds) uploaded; follows DEMO_SCRIPT; shows the provider badge honestly.
- [ ] Devpost (or event form) filled: title, tagline, description, built-with list, links (repo, video), challenges selected.
- [x] Hindi strings reviewed by a native speaker, or the README says they are unreviewed (the README says so).
- [ ] Open the evidence file print preview; confirm the "Draft for review. Not legal advice." line is on every page that states a legal point.

## Short description (paste, then edit with real numbers)

> Small suppliers in India are often paid late and cannot prove it. Munim turns phone photos of a tax invoice, delivery challan and purchase order into a checked evidence file. Gemma 4, running locally, reads the papers; deterministic checks (GSTIN checksum, GST arithmetic, cross-paper agreement) decide what passes; when a check fails Munim re-reads just that field and shows the correction in red pen and ballpoint. It then works out the due date and compound interest under the MSMED Act and prints an evidence file with a draft notice in English and Hindi. Open source, offline-capable, nothing leaves your computer unless you choose the hosted model. No live-model evaluation has been run yet, so no accuracy figure is claimed; the evaluation harness and its failure examples are published and run in CI on recorded responses.

## Longer description outline

1. The problem (one real-feeling scenario, labelled as an illustration, not a testimonial).
2. What Munim does (the five steps).
3. How the model is used and what it is not trusted to do.
4. What we measured and what failed (include one failure example image).
5. Why open source and local matter here.
6. What we built at the event vs what we reused (link to THIRD_PARTY).
7. What's next (real-paper testing with an accountant, Hindi review, Samadhaan export, MCP).

## Built with (list exactly what is used)

Python, FastAPI, Jinja2, htmx, SQLite, Pydantic, python-stdnum, Pillow, rapidfuzz, Ollama, Gemma 4, Playwright, pytest, hypothesis, ruff, mypy, GitHub Actions, Mukta and Kalam fonts. Remove anything not actually used.

## Judge Q&A preparation

| Likely question | Prepared answer (verify against the final build) |
| --- | --- |
| Why not just use a big hosted model? | Papers are private business data; local open-weight keeps them on the machine; the checks make a small model usable; cost per page is zero. |
| What if the model misreads? | The headline metric is "wrong and passed" (no live figure yet; on synthetic recordings the checks caught 13 of 26 deliberately wrong values). Checks catch many; the user sees the box next to every value and must confirm. |
| Is this legal advice? | No. It calculates from stated rules, cites them, flags unsettled points (registration timing), and marks drafts. |
| Is the interest right? | Matches golden vectors; assumptions (day count, base) are listed on the Rules page; an accountant should confirm. |
| What did you build today? | Show the commit history and `PROGRESS.md`. Libraries listed in THIRD_PARTY. |
| Does it work in Hindi? | UI and notice are bilingual; Hindi text is awaiting review by a native reader. |
| How is this different from existing invoice-OCR hackathon projects? | Those extract fields; Munim verifies, repairs, computes the legal clock, and publishes its failure rate. |
| Real users? | Not yet. Testing so far is automated: 30 synthetic papers plus 5 with injected faults, unit, property, integration, golden and browser tests. No real papers and no outside users. |
