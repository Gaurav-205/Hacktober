---
paths:
  - "tests/**"
---

# Rules for tests

- Follow the catalogue in `docs/TESTING.md`. Name tests after the behaviour, for example `test_interest_is_zero_on_due_date`.
- Every test asserts content that matters, not just "not None" or a 200 status. Do not mock the unit under test.
- Use markers: `unit`, `property`, `integration`, `contract`, `golden`, `e2e`, `a11y`, `live`. Live tests skip unless `MUNIM_LIVE=1`.
- Tests use a temporary `MUNIM_DATA_DIR` and the replay provider or the fake Ollama transport. They make no network calls except to loopback.
- E2E tests wait on conditions (`expect`, locators), never `sleep`. They start the server on a free port in a fixture. Traces are kept on failure. PDF tests run in Chromium only.
- Golden files are normalised (CSRF tokens, ULIDs, timestamps) and blessed with `make bless` only after a human-readable look at the diff. Say so in the commit.
- Test data is synthetic and labelled. Any 12-digit test number for Aadhaar masking sits on a line containing the word `synthetic`; the pre-write guard requires it.
- Never weaken an assertion, raise a tolerance or add `skip` or `xfail` to get green. A skip needs a reason and a follow-up in `docs/PROGRESS.md`.
