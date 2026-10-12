# Munim: product requirements

Status: v1.0 for the Hacktoberfest Hack Day Pune (13 Oct 2026). Owner: Gaurav Khandelwal.
Sources of truth: this file for *what* and *why*; `DESIGN.md` for look; `docs/DOMAIN_RULES.md` for legal and arithmetic rules; `docs/AI_SPEC.md` for the model layer.

> Munim does not give legal advice. It reads papers, checks them against rules a machine can check, calculates what the Micro, Small and Medium Enterprises Development Act, 2006 (MSMED Act) says is owed, and produces a file the supplier can take to an accountant, lawyer or the Micro and Small Enterprises Facilitation Council (MSEFC).

## 1. Problem

A small supplier delivers goods, issues an invoice and waits. The buyer pays late or not at all. When the supplier finally decides to chase, they discover three problems:

1. **The proof is scattered.** The tax invoice, the delivery challan signed or stamped by the receiver, and the purchase order are separate WhatsApp photos, some tilted, some blurred, some in Hindi or mixed scripts.
2. **The papers do not agree with each other.** A GSTIN with a typo, an invoice total that is not the sum of its lines, a challan quantity that differs from the invoice, a date written `04/07` that could be 4 July or 7 April. Each mismatch gives the buyer a reason to dispute.
3. **Nobody has worked out the law's clock.** The MSMED Act sets a payment deadline (at most 45 days from acceptance, 15 if there is no written agreement) and compound interest at three times the RBI Bank Rate for late payment. Most small suppliers do not know the number, so they ask for the principal alone, or do not ask at all.

The result is that the dues stay unpaid because assembling a credible claim is slow, confusing and feels like it needs a professional the supplier cannot afford for a ₹60,000 invoice.

## 2. Product in one paragraph

Munim is an open-source web application that runs on the user's own computer. The user photographs or uploads the invoice, the challan and the purchase order for one dispute. Gemma 4 (an open-weight model with Apache 2.0 licence, run locally through Ollama by default) reads each paper and returns fields with the box on the page where each was found. Deterministic code then checks every field: GSTIN checksum and state code, PAN consistency, GST arithmetic, date logic, cross-paper agreement. When a check fails, Munim crops the marked box and asks Gemma to re-read just that field, and shows the correction as a red-pen strike with the new value in ballpoint handwriting. What cannot be repaired is flagged for the person. After the user confirms the values, Munim computes the due date and the statutory interest to today, and builds a printable dossier with the evidence, the working, and a draft notice in English and Hindi.

## 3. Users

| Persona | Situation | What they need | What they fear |
| --- | --- | --- | --- |
| **Ramesh, supplier** (primary) | Runs a 6-person fabrication unit in the Ghaziabad cluster. Has invoices on his phone. Hindi first, some English. Owed ₹1.8 lakh by a mid-size buyer for four months. | Know in minutes whether his papers hold up and what he is owed under the Act. | Offending the buyer; being told "your GSTIN is wrong" after he files. |
| **Neha, accountant at a cyber cafe / CA's assistant** (secondary) | Helps 30 small clients with GST and notices. Uses Excel and WhatsApp. | A repeatable way to turn a client's photo pile into a checked file. | Retyping, silent errors. |
| **Support worker at an MSME facilitation cell / industry association** (secondary) | Helps members file with the MSEFC. | A consistent evidence format. | Incomplete files bounced back. |

Language: English and Hindi are both first-class. Users read Devanagari and Latin numerals together.

Non-users for v1: buyers, lawyers as authors of final legal documents, large enterprises, and anyone needing e-filing on the Samadhaan portal.

## 4. Goals and non-goals

### Goals (v1, built in one day)
- G1. From three phone photos to a verified evidence table in under 3 minutes on a laptop with the E4B model.
- G2. Every number on the dossier traces to a box on a paper or to a rule with a version.
- G3. The app never claims more than it knows: it says "Passed", "Doesn't match" or "Check by hand", never "Verified" or "Correct".
- G4. Works fully offline with the local model; also works with the Gemini API (Gemma 4 hosted) when the user opts in, and with recorded responses for demos and tests.
- G5. Measured honesty: a published evaluation reporting field accuracy, the rate of wrong values that pass every check, and failure examples.
- G6. A design that does not look like a template (see `DESIGN.md`), usable in Hindi.

### Non-goals (v1)
- Filing anything with a court, council or portal.
- Legal advice, outcome predictions, or a "strength of case" score.
- Reading handwriting-only papers, multi-page invoices with more than 12 line items, or non-Indian tax regimes.
- Accounts, login, cloud storage, multi-user. One machine, one user.
- Section 43B(h) income-tax analysis (sources disagree on the first applicable year; out of scope).
- Reminders, WhatsApp sending, payment links.

## 5. Scope and user stories

Priority key: **M** must (v1 demo breaks without it), **S** should, **C** could (stretch).

### Epic A: Cases and papers
| ID | Story | Acceptance criteria | P |
| --- | --- | --- | --- |
| A1 | As a supplier I can create a case naming the buyer and the supplier. | Case has a title, buyer name, supplier name. Appears in the case list. | M |
| A2 | I can add a paper by choosing a file or dropping it. | Accepts JPEG, PNG, WebP, HEIC (converted), PDF (first page read in v1). Rejects others with a message. Max 15 MB. Shows a thumbnail. One paper of each type per case. | M |
| A3 | I choose the paper type (tax invoice, delivery challan, purchase order). | Type is required, colour-coded per `DESIGN.md`. Changing type re-runs the checks. | M |
| A4 | I can delete a paper or the whole case and everything is wiped. | Files and database rows are removed; a test proves no bytes of the original remain in `data/`. | M |
| A5 | I can rotate and crop a photo before reading. | Rotate in 90° steps. Auto-deskew is a should. | S |

### Epic B: Reading
| ID | Story | Acceptance criteria | P |
| --- | --- | --- | --- |
| B1 | When I press "Check this paper", Munim reads the fields for that paper type. | Returns the schema in `docs/AI_SPEC.md` with a box for each field found. Completes or fails visibly within 90 s on E4B CPU-only; progress is shown. | M |
| B2 | I see each field with its box drawn on the photo. | Box coordinates are converted from the model's 1000x1000 grid to the displayed image. Clicking a row highlights the box and vice versa. | M |
| B3 | If the model returns invalid JSON, Munim retries once with a stricter prompt, then shows a clear failure and lets me enter values by hand. | Test with a replay fixture of malformed output. | M |
| B4 | I can choose the model provider (local Ollama, Gemini API, recorded). | Setting persists; cloud use shows a one-time consent line saying the photo leaves this computer. | M |
| B5 | I can edit any value; the original stays visible. | Edit shows original struck through, new value in the hand face, an "edited by you" note. | M |

### Epic C: Checking (the red pen)
| ID | Story | Acceptance criteria | P |
| --- | --- | --- | --- |
| C1 | Munim checks GSTIN structure, state code and checksum. | Uses `python-stdnum`; cases in `docs/DOMAIN_RULES.md` section 3. | M |
| C2 | Munim checks that PAN inside GSTIN matches a PAN printed on the paper, if any. | Mismatch is "Doesn't match". | S |
| C3 | Munim checks GST arithmetic. | Per line: quantity x rate = amount (within 1 paisa tolerance after rounding); taxable total = sum of lines; tax = rate x taxable per rule; invoice total = taxable + tax +/- round-off (at most ₹1). Intra-state uses CGST+SGST, inter-state IGST, decided from the two state codes. | M |
| C4 | Munim checks date logic. | Invoice date not in the future; challan date not before PO date; challan not more than 30 days after the invoice (warn); any numeric date that could be read day-first or month-first is flagged with both readings, and the day-first reading is the default shown to the user. | M |
| C5 | Munim checks the papers against each other. | Buyer and supplier GSTIN equal across papers; invoice number cited on the challan matches; quantities per line item are equal between challan and invoice after unit conversion; PO number cited on invoice matches. | M |
| C6 | On a failed check tied to a single field, Munim crops that box and asks Gemma to re-read only it, then re-runs the check. | At most 2 repair attempts per field. Outcome is one of: **Corrected** (check now passes), **Unchanged** (model returns the same value), **Check by hand**. | M |
| C7 | A repaired value is never accepted silently. | Corrected values appear in ballpoint handwriting with the reason; the user still presses "Confirm these values". | M |
| C8 | IFSC on the invoice bank details is checked against the bundled IFSC dataset. | Unknown code is "Check by hand" (dataset may be out of date). | C |

### Epic D: The payment clock
| ID | Story | Acceptance criteria | P |
| --- | --- | --- | --- |
| D1 | I enter or confirm the acceptance date (default: challan receipt date) and whether there is a written agreement and its credit days. | Due date follows `DOMAIN_RULES.md` section 5. If agreed days exceed 45, Munim caps at 45 and explains. | M |
| D2 | I enter the Udyam registration number and date, and confirm that the registration covers the supply date. | Number format validated; the eligibility panel shows the unresolved legal position and the words "check with counsel". | M |
| D3 | Munim computes interest to a chosen date using three times the Bank Rate, compounded monthly. | Matches the golden outputs in `DOMAIN_RULES.md` section 5.3 (₹22,839.19 at 3 months and ₹97,809.09 at 12 months on ₹5,00,000 at 18%, 1 Jan 2026 start). Working steps are shown. | M |
| D4 | I can set the Bank Rate table (rate and effective date) myself. | The seeded rate is shown with a "not yet confirmed by you" marker until edited or confirmed. | M |
| D5 | I can toggle the interest base between taxable value and invoice total. | The working states the base used. | S |

### Epic E: The dossier
| ID | Story | Acceptance criteria | P |
| --- | --- | --- | --- |
| E1 | I can open a dossier with summary, evidence table, working, originals. | Layout per `DESIGN.md` section 5. Prints to A4 cleanly in Chromium and Firefox. | M |
| E2 | The "Checked" stamp appears only after I confirm and no blocking finding remains. | Test: stamp absent if any blocking finding unresolved. | M |
| E3 | A draft notice in English and Hindi is generated from templates (not the model). | Placeholders filled from confirmed values; every statement of law cites the rule id; the notice is marked "Draft for review". | M |
| E4 | I can copy the notice text and the evidence table as plain text. | Clipboard buttons with a "Copied" toast. | S |
| E5 | I can export a ZIP: dossier HTML, JSON of all claims with provenance, originals. | Schema versioned. | C |

### Epic F: Trust and openness
| ID | Story | Acceptance criteria | P |
| --- | --- | --- | --- |
| F1 | A Rules page lists every rule, its version, its source and the date I last checked it. | Rendered from `rules/*.yaml`. | M |
| F2 | An Evaluation page shows the latest accuracy report. | Rendered from `eval/reports/latest.json`; shows the metric "wrong and passed". | S |
| F3 | An About page states licence, model name and its licence, and what leaves the computer. | Matches `docs/SECURITY_PRIVACY.md`. | M |
| F4 | Two reusable outputs: an MCP server and an Agent Skill exposing the verifiers. | `munim-mcp` exposes `check_gstin`, `check_invoice_arithmetic`, `compute_msmed_interest`; `skills/munim-checks/SKILL.md` validates with `skills-ref validate`. | C |

## 6. The signature moment (must work in the demo)

1. The user adds an invoice photo whose buyer GSTIN was misread in the first read (the check character read wrongly, in the recorded demo responses).
2. The claims table shows the GSTIN row in `red-wash` with "Doesn't match: the last character doesn't match the other 14 characters".
3. Munim crops the GSTIN box, asks Gemma to re-read it, and the red-pen strike draws over the wrong value; the corrected value is written beside it in ballpoint handwriting.
4. The checksum now passes; the row turns to "Passed".
5. The user confirms; the rubber stamp lands; the clock strip shows the amount owed to the paisa; the dossier opens.

If steps 2 to 4 do not work live, the recorded provider replays them; the About page and the demo script say honestly which provider is running.

## 7. Success metrics

| Metric | Target for the event | How measured |
| --- | --- | --- |
| Time from three photos to confirmed values | under 3 min with a pre-warmed model | stopwatch in the e2e demo run |
| Field accuracy on the synthetic set (n >= 30 papers) | >= 85% exact match on required fields | `make eval` |
| **Wrong and passed** (model value wrong, every check passes) | reported; target below 3% of fields | `make eval` |
| Repair success on injected single-character GSTIN errors | >= 60% corrected, remainder flagged | `make eval-repair` |
| Real-document check | 5 real papers tested locally by the team (not committed); results published as aggregates and failure descriptions | manual, `docs/EVAL_REAL.md` template |
| Accessibility | zero axe-core serious or critical issues on all pages in en and hi | CI |
| Test health | core coverage >= 95%, overall >= 85%, all gates green | CI |

## 8. Non-functional requirements

- **Offline first.** After installation and model download, no network is needed in local mode. Fonts are self-hosted. The app makes zero third-party requests (tested by a Playwright network assertion).
- **Privacy.** See `docs/SECURITY_PRIVACY.md`. Originals never leave the machine unless the user selects the Gemini provider; Aadhaar numbers are masked on detection and never stored.
- **Performance.** First paint under 1 s on localhost; JS under 60 KB gzipped (no framework); extraction progress shown within 500 ms of pressing the button.
- **Accessibility.** WCAG 2.2 AA target. Keyboard-only flow completes the whole journey. Reduced motion respected.
- **Internationalisation.** `en` and `hi`; Devanagari fonts self-hosted; strings in JSON; numbers in Indian grouping.
- **Reliability.** A model or network failure never loses user edits; all state is committed to SQLite on each change.
- **Portability.** Linux, macOS, Windows. Python 3.12 via `uv`. One command to run: `make run`.
- **Licence.** Application code Apache-2.0 (matches Gemma's licence and gives patent grant). Third-party components in `THIRD_PARTY.md`.

## 9. Constraints and assumptions

- C1. Built during the one-day event; only libraries, models, fonts and data listed in `THIRD_PARTY.md` and the docs in this pack exist beforehand. No application code is pre-written. (If you are reading this before the event, do not start implementation; see `MASTER_PROMPT.md` Step -1.)
- C2. Hardware: a laptop with 16 GB RAM is assumed for Gemma 4 E4B. If the laptop is slower, use the Gemini API provider or the recorded one, and say so.
- C3. Test data are synthetic. The team may test real papers locally but commits none.
- A1. The user knows their documents are Indian GST invoices (post-July 2017).
- A2. The acceptance date defaults to the challan's received date if one is printed, else the challan date, unless the user overrides it; objection within 15 days changes acceptance (see `DOMAIN_RULES.md` 5.1); Munim asks, it does not infer.
- A3. The RBI Bank Rate rows seeded in `rules/bank_rate.yaml` come from the RBI home page (12 Oct 2026) and press reports of the 2025 and 2026 policy changes; none is confirmed against an RBI notification, and the UI says so until the user confirms them.

## 10. Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Gemma 4 E4B is slow or inaccurate on photos | Medium | High | Provider abstraction; Gemini API and replay fallbacks; test image sizes; resize to 1568 px long edge |
| Structured output is unreliable via Ollama | Medium | Medium | Prompt-enforced JSON, Pydantic validation, one retry, hand-entry fallback; preflight check at startup |
| Box coordinates are poor | Medium | Medium | Boxes are optional; the table still works; evaluation measures box IoU separately |
| Legal wording misleads | Medium | High | Every legal statement cites a rule id; draft marked; "check with counsel"; Hindi reviewed by a native reader before the demo |
| Bank Rate value is stale | Medium | High | Seeded value flagged; user-editable table; Rules page cites the source and date |
| Scope too large for one day | High | High | Gated plan (`docs/TASKS.md`); Gate 3 is a complete vertical slice; fallback below |
| Looks templated | Medium | Medium | `DESIGN.md` lint, custom icons and stamp, review at Gate 5 |

**Fallback ("Khata-Proof").** If Gate 3 is not green by hour 4, drop the payment clock's UI polish and Hindi notice, keep reading and checking, and present Munim as an invoice and challan consistency checker; the dossier still prints. The clock is a pure function that can be shown in the CLI.

## 11. Out-of-scope but recorded questions (open)

1. Is registration under Section 8 a precondition for Section 18 claims? The Supreme Court in *NBCC (India) Ltd v State of West Bengal* (Jan 2025) held not mandatory, but referred the question to a larger bench; *Silpi Industries* (2021) and *Mahakali Foods* (2023) held the opposite. Munim asks for the Udyam number and date, and shows the uncertainty.
2. Which Bank Rate applies when it changes mid-dispute? v1 applies the rate in force at the start of each monthly period.
3. Is interest payable on the GST component? v1 offers a toggle and defaults to the invoice total; confirm with an accountant.
4. Partial-month convention: v1 uses actual days over the length of that monthly period.
5. Hindi legal terminology needs review by a native reader with legal familiarity.

## 12. Release definition

v1 is releasable for the event when: Gates 0 to 4 are green, the demo script runs start to finish on the replay provider and on at least one live provider, `README.md` instructions work from a clean clone, and `docs/SUBMISSION.md` is filled in.
