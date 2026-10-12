# AI specification

What the model does, what it must never do, and how we measure it. Read with `ARCHITECTURE.md` section 6.

## 1. Model facts used (and what is not known)

| Fact | Source | Status |
| --- | --- | --- |
| Gemma 4 is an open-weight family under the Apache 2.0 licence | Gemma 4 model card | verified (Oct 2026) |
| Sizes: E2B, E4B, 12B, 26B A4B, 31B; image input on all; audio on E2B, E4B, 12B only | model card; Ollama library page | verified |
| Object boxes use `box_2d = [y1, x1, y2, x2]` on a 1000 x 1000 grid | model card (vision section) | verified; **always test on our images** |
| Thinking can be configured | model card; Gemini API docs (`thinking_level`: `high`, `minimal`) | verified |
| Ollama tags: `gemma4:e2b`, `gemma4:e4b` (latest), `gemma4:12b`, `gemma4:26b`, `gemma4:31b` | Ollama library page | verified |
| Gemini API model ids: `gemma-4-31b-it`, `gemma-4-26b-a4b-it` | Gemma on Gemini API docs | verified; rate limits are not published |
| Ollama structured output (`format` parameter with a JSON schema) works with Gemma 4 | not verified | **unverified**: use prompt-enforced JSON plus Pydantic; probe at preflight and use `format` only if the probe passes |
| Gemma 4 accepts inline image bytes through the Gemini API | not verified | use `client.files.upload` (documented) and fall back to it |
| Reading accuracy on Indian invoices and challans | unknown | **measured by `make eval`; the number in the README comes from there and nowhere else** |

Never state a capability in the README, the demo or the submission that the evaluation has not measured.

## 2. Role boundaries

The model does:
- Transcribe printed fields from a photo of a tax invoice, delivery challan or purchase order.
- Say where on the page each field is (box).
- Re-read a single cropped field when asked.
- Report, as yes/no/unknown, whether a receiver's stamp or signature is visible on a challan.

The model never:
- Decides whether a check passed, whether a claim is valid, what is owed, or what the law says.
- Writes any text shown to the user as an explanation or notice. (All user-facing text is from templates and i18n.)
- Sees more than one paper at a time (no cross-paper reasoning in the model; cross-paper checks are code).
- Receives personal data beyond the photo itself (no case notes, no names typed by the user).

## 3. Schemas (Pydantic, in `munim_ai/schemas.py`)

```python
class Box(BaseModel):                       # 0..1000 grid, [y1, x1, y2, x2]
    y1: int = Field(ge=0, le=1000); x1: int = Field(ge=0, le=1000)
    y2: int = Field(ge=0, le=1000); x2: int = Field(ge=0, le=1000)
    @model_validator(mode="after")
    def ordered(self): assert self.y1 < self.y2 and self.x1 < self.x2; return self

class Field_(BaseModel):                    # name avoids clashing with pydantic.Field
    value: str | None                       # exactly as printed; null if absent
    box_2d: list[int] | None = None         # model emits a list; we validate into Box
    note: str | None = None                 # free text, <= 120 chars, never shown as a score

class LineItem(BaseModel):
    description: Field_; hsn_sac: Field_ | None = None
    quantity: Field_ | None = None; unit: Field_ | None = None
    rate: Field_ | None = None; amount: Field_ | None = None

class InvoiceRead(BaseModel):
    kind: Literal["invoice"]
    supplier_name: Field_; supplier_gstin: Field_
    buyer_name: Field_; buyer_gstin: Field_
    invoice_number: Field_; invoice_date: Field_
    place_of_supply: Field_ | None
    line_items: list[LineItem] = Field(max_length=12)
    taxable_total: Field_ | None; cgst: Field_ | None; sgst: Field_ | None; igst: Field_ | None
    round_off: Field_ | None; invoice_total: Field_
    po_reference: Field_ | None; challan_reference: Field_ | None; bank_ifsc: Field_ | None
```
`ChallanRead` and `PORead` follow `DOMAIN_RULES.md` section 2. `ChallanRead` additionally has `receiver_stamp_present` and `receiver_signature_present`: `Literal["yes","no","unknown"]`.

Post-processing in `munim_ai/normalize.py` (pure, tested):
- Strip whitespace; convert Devanagari digits to ASCII digits; remove thousands separators for amounts; keep the raw string in `value_read`.
- Dates: parse with day-first assumption; keep both readings if ambiguous.
- Mask any 12-digit run that passes Verhoeff (Aadhaar) as `XXXX XXXX dddd` before anything is stored or logged.
- Reject values longer than 200 characters (likely a runaway generation).

## 4. Prompts

Stored as files in `munim_ai/prompts/` (`invoice.system.md`, `challan.system.md`, `po.system.md`, `reread.system.md`, `strict_suffix.md`), versioned by a header line `prompt_version: 1`. The version is saved on every read.

**System prompt skeleton (invoice):**
```
You read photographs of Indian business papers. You are given one image of a GST tax invoice.
Return one JSON object and nothing else: no prose, no code fences.
Copy each value exactly as printed, including spelling errors. Do not correct, complete, translate or infer.
If a field is not on the paper, use null. Never guess a digit.
For every field you return, also return box_2d as [y1, x1, y2, x2] on a 1000 by 1000 grid
measured from the top-left of the image, enclosing the printed value only.
Amounts are numbers as printed, without currency symbols. Dates exactly as printed.
The JSON must follow this shape: <schema rendered from Pydantic, compact>.
```
User turn: the image, then "Read this tax invoice."

**Re-read prompt (single field):**
```
This image is a crop of one field from an Indian business paper. The field is: <field_label>.
Return JSON: {"value": "<exactly as printed>", "box_2d": null}.
Characters often confused in print: 0 and O, 1 and I, 5 and S, 8 and B, 2 and Z.
For a GSTIN, the value is 15 characters: 2 digits, 5 letters, 4 digits, 1 letter, 1 letter or digit, the letter Z, 1 letter or digit.
Do not use any other knowledge. Copy what is printed.
```
The prompt gives the format of the field (this is allowed; it is public format knowledge, not the answer) but never the previously read value (avoid anchoring).

**Strict retry suffix:** "Your last answer was not valid JSON for the schema. Return only the JSON object."

**Thinking:** Gemini provider: `thinking_level="minimal"` for extraction (speed), `"high"` for re-read. Ollama: default; record any parameter that proves useful in `docs/AI_NOTES.md` after measuring. Do not claim a thinking benefit without a measurement.

## 5. Providers

### 5.1 `ollama`
- Python package `ollama`; `AsyncClient(host=MUNIM_OLLAMA_URL)`.
- `chat(model=..., messages=[{role:'system',...},{role:'user', content:'Read this tax invoice.', images:[jpeg_bytes]}], options={'temperature': 0}, format=<schema or omitted>)`.
- Preflight: `GET /api/tags` to see whether the model is pulled; then a tiny probe on a bundled 200x60 test image ("INV-0042") to confirm vision works, and a JSON-format probe. Result stored in `PreflightReport(model_present, vision_ok, json_format_ok, latency_ms)`. The Settings page shows the report with plain-language fixes ("Run `ollama pull gemma4:e4b`").
- Timeouts: 90 s read, 45 s re-read.
- One request at a time (semaphore) to avoid memory pressure.

### 5.2 `gemini`
- `google-genai`: `client = genai.Client(api_key=...)`; `file = client.files.upload(file=path)`; `client.models.generate_content(model="gemma-4-31b-it", contents=[file, prompt], config=types.GenerateContentConfig(system_instruction=..., temperature=0, thinking_config=types.ThinkingConfig(thinking_level="minimal")))`.
- Enabled only after the user ticks the cloud-consent box (SECURITY_PRIVACY section 4). The uploaded file is deleted after the call (`client.files.delete`).
- If a 429 or quota error occurs, show the message and suggest the local provider.
- Function calling is **not** used for extraction in v1 (keep the interface identical across providers).

### 5.3 `replay`
- Fixture format: `eval/fixtures/replay/<key>.json` containing `{text, provider, model, recorded_at, recorded_from}`.
- Key for a full read: `sha256(original uploaded bytes) + ":" + paper kind + ":" + prompt_version`. Key for a re-read: the same plus `":" + field + ":" + box`. Never key on re-encoded or resized bytes: JPEG encoders differ between Pillow versions and platforms, so such keys break in CI.
- Committed fixture images are JPEGs already within the size limit (long edge <= 1568 px) so `imageprep` leaves them as they are.
- `MUNIM_PROVIDER=replay` returns the recorded text for the image hash and prompt kind or raises `ReplayMiss` (never silently falls back).
- A `record` mode wraps a live provider and writes fixtures. Fixtures contain only synthetic documents (CI checks the file list).
- The UI shows a persistent label "Recorded responses" when this provider is active. Honesty rule: the demo must not pass off replay as a live read.

## 6. Failure handling

| Failure | Detection | Response |
| --- | --- | --- |
| Not JSON | `json.loads` fails after stripping fences | Retry once with strict suffix; then fail soft |
| JSON valid but schema invalid | Pydantic error | Retry once; keep valid fields if at least `invoice_total` and one GSTIN parsed, else fail soft |
| Boxes outside 0..1000 or unordered | validator | Drop that box only; value remains |
| Runaway text | length > 200 | Drop value; mark `needs_review` |
| Hallucinated field (value not visible) | cannot be detected directly | Mitigation: re-read crop for any field that is in a blocking finding; cross-paper rules; evaluation measures "wrong and passed" |
| Language mix | Hindi/English labels | Prompt says copy exactly; normalisation handles Devanagari digits |
| Image too dark/blurred | Laplacian variance and mean brightness thresholds in `imageprep.quality()` | Warn before reading with the reason and what to do |

## 7. Repair loop specification

```
for finding in findings where finding.repairable (GSTIN-*, amount rules touching one field):
    attempts = 0
    while attempts < 2 and finding.status == failed:
        attempts += 1
        if field is GSTIN and (c := single_lookalike_fix(value)):
            propose(c, via="lookalike")
        else:
            crop = crop(original, box expanded 8%, min 64 px each side)
            new = provider.reread(crop, field_spec)
            if normalize(new) == normalize(current): outcome = unchanged; break
            propose(new, via="model")
        rerun verify for the field
    outcome = corrected if finding now passed else check_by_hand
```
- A proposal changes `value_current`, sets `source='repair'`, keeps `value_read`.
- The UI shows corrections only through the red-pen sequence; the user still confirms.
- Repair never edits more than the one field; it never changes totals to make arithmetic balance.

## 8. Evaluation (the credibility engine)

### 8.1 Data
- **Synthetic set (committed):** `scripts/gen_fixtures.py` renders at least 30 papers (12 invoices, 10 challans, 8 POs) with ReportLab from random but seeded data using valid GSTINs (constructed via the checksum algorithm), then applies photo degradations with Pillow: rotation of +/- 6 degrees, perspective warp, Gaussian blur, JPEG compression, uneven lighting, a coffee-ring stain overlay, partial shadow. Fonts: DejaVu and Noto Sans Devanagari to include Hindi labels. A ground-truth JSON per paper.
- **Injected faults (committed):** variants with a single mutated character in a GSTIN, a wrong total, a swapped day/month, a quantity mismatch. These test the checks, not the model.
- **Real documents (not committed):** a local folder `eval/real/` in `.gitignore`. `run_eval.py --real` computes the same metrics. Only aggregate numbers and short failure descriptions without personal data go into `docs/EVAL_REAL.md`.

### 8.2 Metrics (`eval/run_eval.py`)
| Metric | Definition |
| --- | --- |
| Field exact match | normalised value equals ground truth, over required fields |
| Amount exact match | numeric equality in paise |
| Identifier exact match | GSTIN/PAN/invoice no. after normalisation |
| Box IoU >= 0.5 | fraction of fields with a box whose IoU with the truth box is at least 0.5 |
| Invalid-JSON rate | fraction of calls needing the retry; fraction failing after retry |
| **Wrong and passed** | fields where value != truth **and** all rules touching the field passed |
| Detected and flagged | fields where value != truth and some rule failed or needs_review |
| Repair outcome | corrected / unchanged / check_by_hand for injected GSTIN faults and for model misreads |
| Latency | median and p95 per paper, by provider and model |

Report JSON schema in `eval/reports/schema.json`; `latest.json` is rendered on the Evaluation page with the model name, provider, date, n, and a plain-language reading ("In 7 of 100 fields the value was wrong; the checks caught 5 of those 7").

### 8.3 Honesty rules
1. Headline number is **wrong and passed**, not accuracy.
2. Include at least five failure examples with the cropped image and what went wrong.
3. State that synthetic results do not predict real-world accuracy.
4. If the evaluation was run on replay fixtures, say so; re-record against a live provider before submission.

## 9. Disclosure for the hosts (Track 2 expects a plain-language account)

`docs/AI_CONTRIBUTION.md` explains in plain language what the model does and does not do, the model name and licence link, which AI coding tools wrote which parts, and what is reused (see that file).
