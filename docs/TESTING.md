# Testing strategy

Principle: the parts that decide money and trust are pure code with exhaustive tests; the parts that depend on a model are tested with recorded responses plus an honest evaluation; the parts that people touch are tested through a real browser.

## 1. Pyramid and gates

| Layer | Tooling | Scope | Runs | Gate |
| --- | --- | --- | --- | --- |
| Unit | pytest | money, dates, ids, each verify rule, clock, normalisers, i18n loader | every save (`make test-fast`) | core coverage >= 95% lines and >= 90% branches |
| Property | hypothesis | invariants listed in section 3 | CI + `make test` | 200 examples locally, 1000 in CI |
| Integration | pytest + httpx `AsyncClient`, temp SQLite, `replay` provider | routes, services, repositories, upload validation, delete wipe | CI | overall coverage >= 85% |
| Contract | pytest | provider interface conformance for replay and a fake Ollama HTTP server; Pydantic schema round trips | CI | all pass |
| Golden | pytest + files | dossier HTML for three fixture cases; notice text en and hi; clock working steps | CI | diffs must be reviewed and re-blessed with `make bless` |
| End to end | Playwright (Chromium, Firefox) | full journey on replay provider, in en and hi, keyboard-only variant | CI | all pass, traces on failure |
| Accessibility | axe-playwright-python | every page, every state fixture | CI | zero serious or critical |
| Static | ruff, mypy --strict (core and ai), bandit, pip-audit, import-linter, check_licences | whole repo | pre-commit + CI | all pass |
| Design | `design_lint.py`, `check_contrast.py`, `check_fonts.py`, `check_i18n.py` | templates, CSS, tokens, strings | pre-commit + CI | all pass |
| Evaluation | `eval/run_eval.py` | model quality; not a unit test | manual / nightly; replay in CI | report schema valid; numbers not gated, but the build fails if the report is older than the model or prompt version |
| Mutation (optional) | mutmut on `munim_core.clock` and `verify` | catches weak tests | manual | survivors reviewed |

`make check` = static + design + unit + property + integration (fast, < 90 s). `make e2e` = Playwright. `make ci` = everything except live-model eval.

## 2. Unit test catalogue (minimum)

### money
- Parse: `"12,50,000"`, `"1250000"`, `"12,50,000.50"`, `"₹ 12,50,000/-"`, `"१२,५०,०००"` -> expected paise; reject `"-5"`, `"1.234"`, `""`, `"abc"`, `"1,2,3"`.
- Format: 0, 99, 100, 999_99, 1_00_000_00, 12_50_000_00, 1_00_00_000_00 -> `₹0.00`, `₹0.99`, `₹1.00`, `₹999.99`, `₹1,00,000.00`, `₹12,50,000.00`, `₹1,00,00,000.00`.
- Rounding: half-up cases `0.005 -> 0.01`, `2.675 -> 2.68`.

### ids
- The three published GSTIN vectors pass; each with its last character changed fails `InvalidChecksum`.
- Bad length, bad state code (`99`, `00`), lowercase input normalised, spaces and hyphens stripped.
- PAN extraction equals characters 3 to 12.
- Look-alike repair: `27AAPFU0939F1ZV` with `0` replaced by `O` at position 9 is fixed exactly once; two-error strings are not "fixed"; a string where two candidates pass returns no unique candidate.
- Aadhaar mask: a valid Verhoeff 12-digit number becomes `XXXX XXXX dddd`; an invalid 12-digit run is untouched.

### verify rules (each rule: passing case, failing case, boundary, missing-input -> skipped)
- `INV-TOTAL`: exact, off by 99 paise (pass), off by 100 paise (pass), 101 (fail); round-off larger than ₹1 fails.
- `INV-TAX-SPLIT`: intra-state with IGST present fails; inter-state with CGST present fails; mismatched place of supply -> needs_review.
- `INV-TAX-RATE`: 18% valid on 2026-01-01; 12% valid on 2025-01-01 but `needs_review` on 2026-01-01 (outside slab set); 28% likewise.
- `X-*`: name normalisation (`M/s Shree Ram Fabricators Pvt. Ltd.` vs `Shree Ram Fabricators Private Limited` similar; `Delta Textiles` vs `Delta Textile Mills` below threshold -> needs_review).
- `INV-DATE-AMBIGUOUS`: `04/07/2026` ambiguous, `25/07/2026` not.
- Every rule returns `message_key` present in `en.json` and `hi.json` (checked by `check_i18n.py` and a test).

### clock
- Due date: written 30 days, 45 days, 60 days (capped to 45), none (15); leap-year Feb 29 acceptance; 31 Jan + 30 days; year boundary.
- Interest: the two golden outputs; as_on before due (0); as_on equal to due (0); one day after due (partial month of 1 day); exactly one month; month-end clamping starting 31 Jan (periods 31 Jan to 28 Feb in 2027).
- Rate change midway: table with two rows; month before change uses old, after uses new.
- Part payment: balance reduced at the payment date and rests restart from that date (hand-computed example in the test); payment equal to the full balance closes the account; overpayment rejected.
- Steps list is complete: the sum of step interests equals the total.

### normalisers
- Devanagari digits, thousand separators, trailing `/-`, trailing full stop, unicode minus.
- Dates `04-07-26`, `4 Jul 2026`, `04/07/2026`, `२०२६-०७-०४`.

## 3. Property tests (hypothesis)

1. `parse_inr(format_inr(x)) == x` for x in 0..10^12 paise.
2. Interest is non-negative, non-decreasing in `as_on`, and monotonic in principal.
3. `interest(as_on = due) == 0`; `interest(as_on < due) == 0`.
4. Closed-form agreement: for whole months, `abs(computed - closed_form) <= months` paise.
5. Restart invariance: computing to month k, then restarting with the new balance for the remaining months equals computing straight through.
6. GSTIN: for any generated valid 14-character prefix, appending the computed check char passes; changing any single character of a valid GSTIN fails (the checksum detects single-character substitutions with weights 1 and 2 except where the substitution leaves the same residue; assert instead that `validate` result equals the pure-Python reference implementation in `tests/ref_gstin.py` for arbitrary strings).
7. Box conversion: `to_pixels(to_grid(box, w, h), w, h)` is within 1 px of the original for any box inside the image.
8. Normalisers are idempotent: `normalise(normalise(x)) == normalise(x)`.
9. Verify functions never raise on arbitrary strings or None; they return `skipped` or a failure.

## 4. Integration and contract tests

- Upload: valid JPEG/PNG/PDF accepted; a `.jpg` that is really a PE executable rejected; 16 MB rejected; decompression bomb rejected; filename traversal (`../../x`) ignored (names are generated); EXIF GPS stripped from the derived copy.
- Read: replay fixtures for a clean invoice, a malformed-JSON response (retry then hand-entry path), a runaway-length value, a `ReplayMiss`.
- Repair: replay of a GSTIN misread -> look-alike candidate path; replay of a model re-read path; an unrepairable one -> `check_by_hand` and the row says so.
- Confirm: 409 while a blocking finding is unresolved; 200 after acceptance with reason; stamp flag false before and true after.
- Delete: after deleting a case, no file under `data/uploads` remains, no rows remain (`PRAGMA foreign_key_check` clean), the SQLite file does not contain the original filename or any claim value (scan bytes after `VACUUM`).
- CSRF: POST without token -> 403.
- i18n: every route renders in `en` and `hi` without missing-key markers (`⟦key⟧` placeholder in dev mode fails the test).
- Provider contract: the same test suite runs against `ReplayProvider` and a `FakeOllama` (an httpx mock transport that returns canned JSON and also simulates timeouts and 500s).
- Network assertion: during the e2e journey, Playwright records all requests and asserts every one targets `127.0.0.1`.

## 5. End-to-end scenarios (Playwright)

| Id | Scenario | Key assertions |
| --- | --- | --- |
| E2E-1 | Happy path (en): create case, add three papers, read, all pass, confirm, open dossier | stamp visible only after confirm; clock strip shows expected owed amount for fixture dates; dossier has 5 sections |
| E2E-2 | Red-pen: invoice with misread GSTIN | row starts red; after repair, strike element and handwriting element appear; row ends Passed; the original value is still in the DOM (struck) |
| E2E-3 | Unrepairable field | row ends "Check by hand"; Confirm button disabled until user accepts with reason |
| E2E-4 | Hindi: same as E2E-1 with `hi` | no clipped text (bounding boxes within container), Devanagari font loaded (`document.fonts.check`), numbers use Indian grouping |
| E2E-5 | Keyboard only | tab order logical; focus ring visible; claims table navigable with arrows; Escape cancels edit; all completed without a pointer |
| E2E-6 | Reduced motion | with `prefers-reduced-motion: reduce` the strike and write states appear immediately; computed `animation-duration` is 0 |
| E2E-7 | Mobile 360px | no horizontal scroll; claims table becomes a list; clock strip reduced; touch targets >= 44 px |
| E2E-8 | Delete case | confirmation dialog; list empty after; subsequent GET of its URL -> 404 |
| E2E-9 | Provider failure | stop the fake Ollama; message with the exact fix command; hand-entry still works |
| E2E-10 | Print (Chromium only: Playwright generates PDFs only in Chromium) | `page.pdf()` of the dossier: 4+ pages, A4, text contains the case name, the stamp text, and no page has overflow (checked via pdf text extraction) |

Screenshots from E2E-1/2/4/7 at 360, 768, 1440 are saved to `docs/screens/` for the README and the submission (generated, not hand-edited).

## 6. Accessibility

- axe-core run on: cases (empty and with rows), workbench in states (no papers, reading, read with failures, confirmed), dossier, rules, evaluation, settings, about, in `en` and `hi`.
- Manual checklist in `docs/A11Y_CHECKLIST.md`: keyboard, screen reader labels on SVG boxes (each box has `role="img"` and `aria-label="Total amount, box on the invoice"`), focus order, zoom 200%, high-contrast mode, `lang` attributes, error messages tied via `aria-describedby`, live regions for status updates (`aria-live="polite"`).
- The status marks have text equivalents; colour is never the sole signal.

## 7. Design tests

- `design_lint.py` unit-tested with a fixture of violations (each rule has one failing sample and one passing sample).
- `check_contrast.py` parses `DESIGN.md` front matter, computes WCAG ratios for the declared pairs and fails below the thresholds; its own test uses the known values (ink on bond 16.29, hairline-strong on sheet 3.59, tick on tickw 4.59).
- `check_fonts.py` asserts the font files exist, licence files exist, Devanagari glyph coverage for a sample string, and `tnum` presence for the UI face.

## 8. Security tests

- `bandit -r packages` clean (or documented suppressions).
- `pip-audit` clean or documented.
- Header test: every response carries the CSP and the other headers in API.md.
- Template injection: a claim value `<img src=x onerror=alert(1)>` renders escaped (Jinja autoescape on); a test asserts the response body contains the escaped form.
- Path traversal on `/papers/{id}/image` impossible by construction (ids only); test with crafted ids.
- Secrets: `gitleaks` (or `detect-secrets`) in pre-commit and CI.
- The Gemini key never appears in logs: a test sets a canary key and greps the captured logs.

## 9. Test data rules

- Synthetic only in the repository. `scripts/gen_fixtures.py` is deterministic (seeded).
- Names are plainly fictional ("Sample Fabricators Pvt Ltd"); GSTINs are checksum-valid strings constructed by the generator and do not belong to real businesses (note: a constructed string can coincide with a real registered GSTIN; the README states that fixtures are synthetic and not intended to identify anyone). Use state code `27` and PANs of the pattern `AAAPZ####Z` that are obviously invented.
- No real photo ever enters `git`. `.gitignore` includes `eval/real/`, `data/`, `*.heic`, and a pre-commit hook rejects image files outside `eval/fixtures/` and `docs/screens/`.

## 10. CI (GitHub Actions, `.github/workflows/ci.yml`)

Jobs: `static` (ruff, mypy, bandit, pip-audit, import-linter, licences), `design` (lints, contrast, fonts, i18n), `test` (matrix: ubuntu, macos; Python 3.12; unit, property, integration, coverage upload as an artifact), `e2e` (ubuntu; Playwright with Chromium and Firefox; traces and screenshots as artifacts), `eval-replay` (runs the evaluation on replay fixtures and validates the report schema). Caching with `uv` and Playwright browsers. Workflow permissions `contents: read`. Actions pinned by commit SHA.

## 11. Definition of done for any change

1. Tests added or updated; `make check` green.
2. If UI changed: lint, contrast, axe, screenshots at 360/768/1440 in en and hi.
3. If rules changed: `DOMAIN_RULES.md`, `rules/*.yaml`, golden outputs updated together.
4. If a model prompt changed: bump `prompt_version`, re-run eval, update the report.
5. Commit message explains why; AI assistance disclosed in the commit trailer when material.
