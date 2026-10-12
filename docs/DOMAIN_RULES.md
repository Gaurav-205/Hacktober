# Domain rules

Every rule has an id, a version, a source and a status. The application loads these from `rules/*.yaml`; this document is the human-readable specification and the YAML is generated from the tables here (the agent must keep them in sync; a test compares rule ids in both).

Status values: **verified** (read from a primary or reputable secondary source, test vector computed), **assumed** (a modelling choice stated openly), **unverified** (seen once; user must confirm).

Munim does not give legal advice. Statements of law below are summaries for software behaviour, not an opinion.

## 1. Money

- Amounts are stored as integer paise. Floating point is never used for money.
- Rounding: round half up to the nearest paisa (`decimal.ROUND_HALF_UP`) at the points specified in each rule.
- Display: `₹` + Indian digit grouping (lakhs, crores) + two decimals. `format_inr(1250000_00) == "₹12,50,000.00"`.
- Input parsing accepts `12,50,000`, `1250000`, `12,50,000.50`, `₹ 12,50,000/-`, and rejects negative values and more than two decimals.

Property tests: `parse(format(x)) == x`; formatting is monotonic in length; sums of paise are exact.

## 2. Document types and expected fields

| Type | Required fields | Optional fields |
| --- | --- | --- |
| Tax invoice | supplier_name, supplier_gstin, buyer_name, buyer_gstin, invoice_number, invoice_date, place_of_supply (state), line_items[], taxable_total, cgst, sgst, igst, round_off, invoice_total | hsn_sac per line, po_reference, challan_reference, bank_ifsc, irn, due_terms_text |
| Delivery challan | supplier_name, supplier_gstin, buyer_name, challan_number, challan_date, line_items[] (description, quantity, unit) | buyer_gstin, invoice_reference, po_reference, receiver_stamp_present (bool), receiver_signature_present (bool), received_date, vehicle_number |
| Purchase order | buyer_name, buyer_gstin, po_number, po_date, line_items[] (description, quantity, unit, rate) | supplier_name, supplier_gstin, payment_terms_text, credit_days, delivery_date |

Each extracted field has: `value` (string as read), `normalized` (typed), `box_2d` ([y1,x1,y2,x2] on a 0 to 1000 grid, or null), `confidence_note` (optional free text from the model, never shown as a percentage), `source` (`model`, `repair`, `user`).

## 3. Verification rules

All rules are pure functions in `munim_core.verify` returning `Finding(rule_id, status, severity, message_key, params, fields)`.

- `status`: `passed`, `failed`, `needs_review`, `skipped` (inputs missing).
- `severity` (only meaningful when not passed): `blocking` or `warning`.
- `message_key` indexes into the i18n files; `params` fill the message. No English strings in `munim_core`.

### 3.1 Identifier rules

| Id | Applies to | Check | On failure | Notes |
| --- | --- | --- | --- | --- |
| `GSTIN-FORMAT` | any GSTIN field | `stdnum.in_.gstin.validate` raises `InvalidLength` or `InvalidFormat` | blocking | Strip spaces, hyphens, convert lowercase to upper before checking, record the normalisation |
| `GSTIN-STATE` | any GSTIN | First two digits are a valid state or UT code (stdnum `InvalidComponent`) | blocking | |
| `GSTIN-CHECKSUM` | any GSTIN | Last character equals the computed check character (stdnum `InvalidChecksum`) | blocking | Algorithm below; used by the repair loop |
| `GSTIN-PAN` | GSTIN + PAN field | `to_pan(gstin) == pan` | blocking | Positions 3 to 12 of a GSTIN are the PAN |
| `PAN-FORMAT` | PAN field | `stdnum.in_.pan.validate` | warning | |
| `AADHAAR-MASK` | any text matching 12-digit Aadhaar pattern with Verhoeff checksum | Not a check: the value is masked to `XXXX XXXX 1234` on read and never stored or shown | n/a | Security rule |
| `UDYAM-FORMAT` | Udyam number | Matches `UDYAM-XX-00-0000000` (state code letters, two digits, seven digits) | warning | Format only; Munim cannot verify the registration |
| `IFSC-KNOWN` | bank IFSC | 4 letters + `0` + 6 alphanumerics, and present in bundled dataset | warning | Dataset from razorpay/ifsc (MIT); may be out of date; stretch |

**GSTIN check-character algorithm** (verified against stdnum and three published vectors):
1. Take the first 14 characters. Map `0-9` to 0-9 and `A-Z` to 10-35.
2. Multiply each value by a weight alternating 1, 2, 1, 2, ... starting with 1 at position 1.
3. For each product p add `p // 36 + p % 36` to a running total.
4. Check value = `(36 - total % 36) % 36`; map back to a character.
Vectors: `27AAPFU0939F1Z` -> `V`; `27AABCU9603R1Z` -> `N`; `09AAACT2727Q1Z` -> `U`. (Full 15-character GSTINs: `27AAPFU0939F1ZV`, `27AABCU9603R1ZN`, `09AAACT2727Q1ZU`.)

Implementation: call `stdnum`. A pure Python re-implementation lives in `tests/` only, to cross-check stdnum in a hypothesis test.

**Candidate generation for repair (deterministic aid).** Before asking the model again, try single-character confusions on the GSTIN (`0/O`, `1/I`, `5/S`, `8/B`, `2/Z`, `6/G`) and accept a candidate only when exactly one single substitution makes the checksum pass. If exactly one candidate passes, present it as "A single look-alike letter fixes the checksum"; still mark the finding as `needs_review` because the checksum can pass for a wrong string. If zero or several pass, fall back to the model re-read.

### 3.2 Arithmetic rules (tax invoice)

Tolerance: 1 paisa per line for rate x quantity; ₹1.00 total for round-off.

| Id | Check |
| --- | --- |
| `INV-LINE-AMOUNT` | For each line with quantity, rate and amount: `round(quantity * rate) == amount` within 1 paisa. If a discount column is present, rate x quantity - discount |
| `INV-TAXABLE-SUM` | Sum of line taxable amounts equals `taxable_total` |
| `INV-TAX-SPLIT` | If supplier and buyer state codes (first two GSTIN digits) are equal, intra-state: `igst == 0` and `cgst == sgst`. If they differ, inter-state: `cgst == sgst == 0`. Place of supply wins over buyer state when the invoice states it differently (status `needs_review`) |
| `INV-TAX-RATE` | Tax amount / taxable total corresponds to an allowed rate for the invoice date: from 22 Sep 2025 the slabs are 0, 5, 18, 40 (and 3 for gold, 0.25 for rough stones); before that 0, 5, 12, 18, 28 plus cess. Mixed-rate invoices are `needs_review` unless every line carries a rate. Source note: GST 2.0 effective 22 Sep 2025 (earlier research; re-check before relying) |
| `INV-TOTAL` | `taxable_total + cgst + sgst + igst + round_off == invoice_total` within ₹1.00; and `abs(round_off) < 1.00` |
| `INV-NUMBER-FORMAT` | Invoice number is at most 16 characters of letters, digits, `/` and `-` (GST rule 46). Violation is a warning because older papers vary |
| `INV-DATE-SANE` | Invoice date on or before today and not before 1 Jul 2017 |
| `INV-DATE-AMBIGUOUS` | If the printed date has day <= 12 and the day-first reading differs from the month-first reading, add a `needs_review` finding showing both readings; the UI shows the day-first reading by default |

### 3.3 Cross-paper rules

| Id | Check |
| --- | --- |
| `X-SUPPLIER-GSTIN` | Supplier GSTIN equal on invoice, challan, PO (where present) |
| `X-BUYER-GSTIN` | Buyer GSTIN equal across papers |
| `X-NAME-SIMILAR` | Buyer and supplier names have normalised token-set similarity >= 0.8 across papers (`rapidfuzz` ratio after lowercasing and stripping `pvt`, `ltd`, `limited`, `private`, `m/s`, punctuation). Below is `needs_review`, never `failed`, because trade names vary |
| `X-INVOICE-REF` | Invoice number quoted on the challan equals the invoice number (normalise leading zeros and separators) |
| `X-PO-REF` | PO number quoted on invoice or challan equals the PO number |
| `X-QTY` | For each pair of lines matched by description similarity >= 0.7 or by HSN, challan quantity >= invoice quantity is acceptable only if equal; otherwise `failed` with both numbers shown. Unit mismatch (kg vs g) converts if a conversion is known, otherwise `needs_review` |
| `X-DATE-ORDER` | PO date <= challan date <= (invoice date + 30 days). Violations are warnings except challan date after the clock end date, which is blocking |
| `X-RECEIVER-ACK` | Challan shows a receiver stamp or signature (model-reported boolean). If false or unknown: `needs_review`, severity warning, message "No receiver's stamp or signature found; the delivery date may be disputed" |

### 3.4 Confidence and the Passed word

- `passed` means the rule's computation succeeded on the value as read. It does not mean the value is true. UI copy and the dossier say "Passed" or "Doesn't match", never "Verified".
- The model's own comment about certainty is never converted to a number. The UI does not show percentages that imply calibration.
- A field is **blocking-clear** when every blocking finding about it is `passed`, or the user has edited it and the re-run passes, or the user has explicitly accepted it with a typed reason ("I checked the paper by hand").

## 4. Eligibility panel (not a rule engine)

Munim does not decide whether a claim qualifies. The panel collects and shows:
- Supplier is a registered micro or small enterprise? Udyam number, registration date (user input).
- Date of supply (default: challan date).
- Text shown: "The Act's protection applies to micro and small suppliers. Courts have taken different views on whether the registration must exist on the date the contract was made. The Supreme Court in NBCC (India) Ltd v State of West Bengal (January 2025) held that prior registration is not mandatory for a Section 18 reference, and referred the point to a larger bench. Earlier decisions (Silpi Industries, 2021; Mahakali Foods, 2023) took the opposite view. Check with a lawyer or your industry association before filing."
- Status: `assumed`. Source: LiveLaw report of the NBCC order (read during research; re-check before the event).
- Medium enterprises are not covered by Sections 15 to 24 in the way micro and small ones are. If the user selects "medium", show an explanatory note and disable the interest computation (the computation is still available behind "Calculate anyway" for information).

## 5. Payment clock (MSMED Act, Sections 15 and 16)

Rule ids: `CLOCK-ACCEPT`, `CLOCK-DUE`, `CLOCK-INTEREST`. Status: **verified** as to structure from secondary sources (IIFL, Vinod Kothari) and the Act's wording as summarised in them; re-read the Act text on indiacode.nic.in before relying on it. Ambiguities are listed in section 7.

### 5.1 Acceptance date

- Default acceptance date = the date of actual delivery of the goods = challan received date if shown, else challan date.
- If the buyer objected in writing within 15 days of delivery, acceptance is the day the objection is removed (user supplies that date and checks "objection removed"). Munim shows the two dates side by side and asks; it never infers an objection.

### 5.2 Due date

Inputs: acceptance date `A`, `agreement` in {`written`, `none`}, `credit_days` (integer, if written).

```
if agreement == none:       days = 15
elif credit_days is None:   ask the user (blocking)
else:                       days = min(credit_days, 45)
due = A + days            # calendar days
```
If `credit_days > 45`, the cap applies and the working states "The Act limits agreed credit to 45 days."
Interest runs from `due + 1 day`.
Edge cases tested: leap day, month end, year boundary, `credit_days = 0`.

### 5.3 Interest

- Annual rate `R = 3 x BankRate` where BankRate is from `rules/bank_rate.yaml` (percent per annum). Example 3 x 5.75 = 17.25.
- Compound interest with monthly rests: the unpaid amount (principal + interest to date) is the base for the next month. Monthly rate `r = R / 12`.
- Period boundaries: month `k` (k = 0, 1, ...) starts on `S + k months` where `S = due + 1 day`, using calendar months (`relativedelta`); month-end clamping: if `S` is the 31st, month starts clamp to the last day of shorter months.
- For a complete month: `balance_next = balance + round(balance * r)`; the rounding happens each month at paise using ROUND_HALF_UP. A test also checks the unrounded closed form within 1 paisa per month.
- For the final partial month with `d` days elapsed out of `D` days in that period: `interest = round(balance * r * d / D)`.
- If the Bank Rate changes (table has more than one entry), the rate used for month `k` is the rate with the latest effective date on or before the month's start date.
- Interest base `P`: `invoice_total` (default) or `taxable_total` (toggle).
- **Part-payments (should-have).** Compute interest up to the payment date (using the partial-month rule if it falls inside a period), add it to the balance, subtract the payment (the balance is a single running amount, so interest-first or principal-first allocation does not change the total owed; the working labels the split as principal paid / interest paid with interest first, `assumed`), then **restart the monthly rests from the payment date** with the reduced balance. Restarting the rests is an `assumed` simplification and is stated on the working page. A payment larger than the balance is rejected. If part-payments are not implemented in time, the UI shows "Part-payments are not included in this figure" whenever the user records one (or hides the form) rather than silently ignoring them.
- Interest ends on the chosen "as on" date or the date of full payment.

**Test vectors (computed, closed form, verified):**

| Principal | Annual rate | Months | Interest (rounded to rupee) |
| --- | --- | --- | --- |
| ₹5,00,000 | 18% | 3 | ₹22,839 |
| ₹5,00,000 | 18% | 12 | ₹97,809 |

Derivation: monthly 1.5%; closed form `500000 x (1.015^3 - 1) = 22,839.19` and `500000 x (1.015^12 - 1) = 97,809.08`.

**Golden outputs of the reference algorithm in this section** (executed and checked while writing this pack; principal 50,000,000 paise, interest period starting 1 Jan 2026):

| as_on | interest in paise | rupees |
| --- | --- | --- |
| 1 Apr 2026 (3 whole months) | 2,283,919 | ₹22,839.19 |
| 1 Jan 2027 (12 whole months) | 9,780,909 | ₹97,809.09 |

Third golden case, the demo case (principal 50,000,000 paise; rate 17.25%; interest period starts 20 Apr 2026, i.e. due date 19 Apr 2026 plus one day; as_on 13 Oct 2026): days late 177, interest **4,290,370 paise (₹42,903.70)**, total 54,290,370 paise (₹5,42,903.70).

The 12-month figure is one paisa above the closed form because rounding happens each month; the tests therefore assert the exact paise above **and** `abs(result - closed_form) <= 1 paisa x months`.

Hypothesis properties: interest is non-negative; non-decreasing in days; zero when `as_on <= due`; monotonic in principal; splitting a computation at a month boundary and restarting with the new balance gives the same result.

### 5.4 Bank Rate table

`rules/bank_rate.yaml`:
```yaml
- effective_from: "2026-10-01"      # PLACEHOLDER: the real effective date is not verified
  percent: 5.75
  source: "RBI home page, read 12 Oct 2026"
  verified: false
```
Until the user confirms the table in the UI, the dossier prints a line "Bank Rate used: 5.75% (to be confirmed against RBI notification)". The agent must not invent historical entries; the user can add rows in the UI.

## 6. Notice template rules

- Templates live in `app/notices/notice.en.md.j2` and `notice.hi.md.j2`.
- Structure: parties and addresses (user input), reference to the supply (invoice number, date, amount), delivery details (challan number and date), due date and its basis, interest basis and amount to date, demand for payment within a stated number of days (user input, default 15), statement that the supplier reserves rights under the MSMED Act including reference to the Facilitation Council, signature line. Every legal sentence is tagged with a rule id in a comment.
- The model does not write notices.
- The header says "Draft for review. Not legal advice." in both languages.

## 7. Open questions (record, do not resolve silently)

1. **Registration timing** (section 4).
2. **Bank Rate selection** when it changes during the delay: month-start rate assumed.
3. **Interest on GST**: toggle; default invoice total.
4. **Partial month**: days over period length assumed.
5. **Part-payments**: balance is reduced at the payment date and monthly rests restart from that date; interest-first split for labelling only; both assumed.
6. **Deemed acceptance** wording around "objection within 15 days" simplified.
7. **Section 43B(h)** deliberately excluded.
8. **Section 19 pre-deposit** (buyer must deposit 75% before appealing an award) is mentioned in the dossier as information only if the user opts in; the text cites the Act and is marked `unverified` until read from indiacode.
9. **GST rate history**: slabs per the Sept 2025 reform; re-check against CBIC before relying.

## 8. Sources

| Topic | Source | Read | Status |
| --- | --- | --- | --- |
| MSMED payment deadline and interest | IIFL explainer; Vinod Kothari note on MSMED Act | Oct 2026 | secondary, consistent |
| Registration eligibility | LiveLaw on NBCC v State of West Bengal | Oct 2026 | secondary; matter referred to larger bench |
| Bank Rate | RBI home page | 12 Oct 2026 | primary; effective date unknown |
| GSTIN algorithm | python-stdnum 2.2 source and tests | Oct 2026 | primary |
| GST slabs | Press coverage of GST 2.0, 22 Sep 2025 | earlier research | secondary; re-check |
