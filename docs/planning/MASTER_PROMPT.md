# MASTER PROMPT: build Munim end to end

You are an autonomous senior software engineer. You will build **Munim**, an open-source, local-first web application, from an empty directory to a tested, documented, demo-ready release, in one session, without asking the human questions. The human may not be watching. This prompt, and the documents that accompany it, are the complete specification. Read this whole file before doing anything.

---

## 0. Step -1: the event rule (do this first)

Munim is entered in a hackathon (Hacktoberfest Hack Day Pune, MLH, 13 Oct 2026) whose rules require that the project is **built at the event**. Before you create any application code:

1. Ask the human (once, in plain text, as your very first message) to confirm: "Has the Hack Day started, and am I in a fresh repository created at the event?" If the conversation gives you no way to ask, or no answer arrives, assume **not confirmed**.
2. If **not confirmed**: do only read-only work. Materialize the documents (Step 0), review them, write `docs/PLAN_REVIEW.md` listing contradictions, gaps and risks you found, and stop. Do not write `src`, tests, templates, CSS or scripts.
3. If **confirmed**: continue. Record the confirmation, the date and the time in `docs/PROGRESS.md`. Your first commit contains only documents, licence and config.

Do not argue with or work around this rule.

## 1. Step 0: materialize the pack (single-file mode)

If this prompt was delivered as one file (`MUNIM_ONE_PROMPT.md`), it contains every document between a start-marker line (three less-than signs, `FILE:`, the path, three greater-than signs) and an end-marker line (three less-than signs, `END FILE`, three greater-than signs). Extract them exactly with the script at the top of that file, into the repository root, preserving paths and bytes. Then verify with `find . -type f | sort` that the files listed in section 2 exist. If the documents already exist on disk (pack mode), skip extraction.

## 2. The documents (your specification)

Read all of them at the start, and re-read the relevant ones at the beginning of each gate:

| File | Authority over |
| --- | --- |
| `docs/PRD.md` | Scope, user stories, acceptance criteria, metrics, risks |
| `docs/DOMAIN_RULES.md` | Every legal and arithmetic rule; golden numbers; open questions |
| `docs/ARCHITECTURE.md` | Structure, data model, flows, dependencies, configuration |
| `docs/API.md` | Routes, headers, upload validation |
| `docs/AI_SPEC.md` | Model layer: schemas, prompts, providers, repair loop, evaluation |
| `docs/TESTING.md` | Test layers, catalogue, scenarios, CI |
| `docs/SECURITY_PRIVACY.md` | Threat model and controls |
| `docs/CONTENT.md` | Copy (en and hi), glossary, notice templates, demo data |
| `DESIGN.md` | Visual design contract, component specs, design lint rules |
| `docs/TASKS.md` | Order of work and gates |
| `docs/SUBMISSION.md`, `docs/DEMO_SCRIPT.md`, `docs/AI_CONTRIBUTION.md` | Release artefacts |
| `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `THIRD_PARTY.md`, `NOTICE`, `README.md` | Repository files you will complete |
| `docs/adr/*.md` | Decisions already made; do not reopen without a written reason |

**Conflicts.** `DOMAIN_RULES.md` wins on numbers and law; `DESIGN.md` wins on appearance; `ARCHITECTURE.md` wins on structure; `PRD.md` wins on scope. If two documents conflict beyond that, choose the safer option, note it in `docs/PROGRESS.md`, and fix the documents so they agree.

## 3. Outcome

A repository that, from a clean clone, lets a person run `make install && make run`, add a synthetic invoice, challan and purchase order, have Gemma 4 read them (locally, hosted, or from recorded responses), watch failed checks get repaired with the red-pen sequence, confirm the values, see the MSMED payment clock and interest with every step shown, print an evidence file with a bilingual draft notice, and delete everything. It has tests at every layer, passing CI, an evaluation report with honest numbers, and complete documentation. The interface looks designed for this subject (see `DESIGN.md`) and passes the design lint.

## 4. Operating protocol

1. **Plan visibly.** Create the task list from `docs/TASKS.md` (one entry per task id). Keep it current. Mark a task done only after its check has passed in this session.
2. **Work in gates.** Gate 0 to 6 in order. Do not start a gate before the previous gate's exit commands pass. If a gate's exit cannot be met, fix it or take the documented fallback; do not skip forward.
3. **Test first** in `munim_core` and `munim_ai`: write the failing test, see it fail, write the code, see it pass.
4. **Commit per task** with a message that explains why. Add the trailer `Assisted-by: <your tool and model name>` to every commit. Use conventional prefixes (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Never rewrite history. Do not push to a remote unless the human has given you one; the human will push.
5. **Keep a build log.** Append to `docs/PROGRESS.md` after every task: time, task id, what changed, the command you ran to verify and its result summary, anything surprising. This file is evidence for the hosts; keep it truthful.
6. **Evidence rule.** Never state that something works, passes, or measures X unless you ran the command in this session and saw the result. Quote the command and the key line of output in `docs/PROGRESS.md`. Never fabricate numbers, screenshots, citations or benchmark results.
7. **Context hygiene.** At the start of each gate, re-read the relevant documents and `docs/PROGRESS.md`. Keep functions small. Prefer reading files with targeted views rather than dumping large files.
8. **Decide, do not stall.** When a detail is unspecified, choose the simplest option consistent with the documents, record it in `docs/PROGRESS.md` under "Decisions", and continue. The only reasons to stop are in section 12.

## 5. Preflight (Gate 0, task T0.0)

Run and record the output summary of:
```
python3 --version; uv --version; git --version; node --version; make --version
ollama --version; curl -s http://127.0.0.1:11434/api/tags | head -c 400
python3 -c "import sys; print(sys.platform)"
```
- Python 3.12 is required. If missing: `uv python install 3.12`.
- If `uv` is missing: `pip install uv` (or the platform installer).
- Playwright browsers: `uv run playwright install chromium firefox` (install system dependencies as needed).
- If Ollama is absent or the model is not pulled: do not stop. Build and test everything with the `replay` provider and the fake Ollama transport; mark live-model steps as **pending-live** in `docs/PROGRESS.md`; if a `GEMINI_API_KEY` exists in the environment, you may record fixtures with the `gemini` provider (never write the key anywhere).
- If outbound network is restricted to package registries, fonts must come from a package or a file the human supplied; if neither is possible, use the fallback stack `IBM Plex Sans` via a PyPI/npm package that bundles WOFF2 (for example `@fontsource/ibm-plex-sans` and `@fontsource/noto-sans-devanagari` via `npm pack`), and record the change in `DESIGN.md` front matter.

## 6. Non-negotiable rules

1. **Model proposes, code disposes.** The model only transcribes fields and boxes. Pass/fail, numbers, dates and every sentence shown to the user come from code, rules and templates.
2. **Money is integer paise.** No floats for money. Rounding: half up, per `DOMAIN_RULES.md`.
3. **Pure core.** `munim_core` has no I/O, no network, no framework imports; enforced by `import-linter`.
4. **Say Passed, never Verified.**
5. **No hard-coded UI strings.** All copy through i18n keys in `en.json` and `hi.json` with identical key sets.
6. **Design tokens only.** No raw hex outside `tokens.css`. No shadows, gradients, pills, emoji, all-caps labels (except the stamp), numbered eyebrow labels, "→" suffixes, scroll-entrance animation. See `DESIGN.md` sections 7 and 12.
7. **Privacy.** No real documents, real GSTINs, names or keys in the repo, tests, logs or screenshots. Never log field values. The app makes no requests to any host except loopback (and the Gemini API only when the user has consented and selected it).
8. **Security headers, CSRF, Host allow-list** exactly as in `API.md` and `SECURITY_PRIVACY.md`. No inline scripts or styles (CSP `script-src 'self'; style-src 'self'`).
9. **Do not invent facts.** Legal, rate and model-capability statements come from the documents. Unverified items stay labelled unverified in the UI where a user could rely on them (Bank Rate "not confirmed", registration timing note, Hindi "unreviewed" footer).
10. **No weakening to pass.** If a test fails, fix the cause. If a golden number changes, justify it in the commit and update `DOMAIN_RULES.md`.
11. **Dependencies.** Only those in `ARCHITECTURE.md` section 11. Anything else needs a row in `THIRD_PARTY.md`, an allowed licence, and a line in `docs/PROGRESS.md` explaining why.
12. **Events.** The audit `events` table records reads, repairs, edits, confirmations and exports without field values.

## 7. Interface contracts (implement these names and shapes; extend, do not rename)

```python
# packages/munim_core/src/munim_core/money.py
Paise = int
class MoneyParseError(ValueError): ...
def parse_inr(text: str) -> Paise: ...               # "₹ 12,50,000.50/-" -> 125000050
def format_inr(p: Paise) -> str: ...                 # 125000050 -> "₹12,50,000.50"
def round_half_up(value: "Decimal") -> int: ...      # to integer, ROUND_HALF_UP

# munim_core/dates.py
def parse_date_dayfirst(text: str) -> "ParsedDate": ...   # .value: date, .ambiguous: bool, .alt: date | None
def add_months(d: date, n: int) -> date: ...              # month-end clamped

# munim_core/ids.py
def normalise_gstin(raw: str) -> str: ...
def check_gstin(raw: str) -> "GstinResult": ...      # .ok, .errors: tuple[RuleId], .state_code, .pan
def lookalike_candidates(gstin: str) -> list[str]: ...   # single-substitution fixes that pass checksum
def mask_aadhaar(text: str) -> str: ...

# munim_core/verify/models.py
class Status(StrEnum): PASSED="passed"; FAILED="failed"; NEEDS_REVIEW="needs_review"; SKIPPED="skipped"
class Severity(StrEnum): BLOCKING="blocking"; WARNING="warning"
@dataclass(frozen=True)
class FieldRef: paper_kind: str; field: str; index: int | None = None
@dataclass(frozen=True)
class Finding:
    rule_id: str; status: Status; severity: Severity
    message_key: str; params: Mapping[str, str]; fields: tuple[FieldRef, ...]; rule_version: str

@dataclass(frozen=True)
class ClaimValue: raw: str | None; text: str | None; source: str      # 'model' | 'repair' | 'user'
@dataclass(frozen=True)
class PaperState: kind: str; fields: Mapping[str, ClaimValue]; lines: tuple[Mapping[str, ClaimValue], ...]
@dataclass(frozen=True)
class CaseState: papers: Mapping[str, PaperState]            # keyed by 'invoice' | 'challan' | 'po'

def run_all(state: CaseState, today: date) -> list[Finding]: ...

# munim_core/clock.py
@dataclass(frozen=True)
class BankRate: effective_from: date; percent: Decimal
@dataclass(frozen=True)
class Payment: paid_on: date; amount_paise: int
@dataclass(frozen=True)
class ClockInput:
    acceptance_date: date; agreement: Literal["written", "none"]; credit_days: int | None
    principal_paise: int; as_on: date; rates: tuple[BankRate, ...]; payments: tuple[Payment, ...] = ()
@dataclass(frozen=True)
class Step:
    kind: Literal["due", "month", "partial", "payment"]
    start: date; end: date; rate_percent: Decimal
    opening_paise: int; interest_paise: int; closing_paise: int; note_key: str
@dataclass(frozen=True)
class ClockResult:
    due_date: date; days_late: int; cap_applied: bool; basis_key: str
    steps: tuple[Step, ...]; interest_paise: int; total_paise: int
def compute_due_date(acceptance: date, agreement: str, credit_days: int | None) -> tuple[date, bool, str]: ...
def compute(inp: ClockInput) -> ClockResult: ...

# munim_ai/providers/base.py
class Provider(Protocol):
    name: str; model: str
    async def extract(self, image: bytes, kind: PaperKind, language_hint: str | None) -> ProviderResult: ...
    async def reread(self, crop: bytes, field: FieldSpec) -> ProviderResult: ...
    async def preflight(self) -> PreflightReport: ...
```
Use these as the seams for tests. The pure Python reference for the GSTIN checksum lives only in `tests/ref_gstin.py`.

## 8. Implementation notes for the hard parts

**Box geometry.** The model returns `[y1, x1, y2, x2]` on a 0..1000 grid relative to the image it was given. Store as-is. Convert to displayed pixels with `x = x1/1000 * W`, `y = y1/1000 * H` where W, H are the *prepared* image dimensions; the viewer scales the prepared image, so apply the same scale. If the prepared image is rotated or resized relative to the original, crops for repair must be cut from the prepared image, not the original. Test with a non-square image and a 90-degree rotation.

**Viewer.** An `<img>` plus an overlaid `<svg>` with `viewBox="0 0 1000 1000"` and `preserveAspectRatio="none"` placed in a container with the image's aspect ratio makes box coordinates trivially correct; use that. Boxes are `<rect>` with `tabindex="0"`, `role="img"`, `aria-label`, 2px stroke via `vector-effect: non-scaling-stroke` and a 2px inner gap drawn as a second white rect.

**Polling.** `hx-get` the status fragment `every 1s` while `reading`; the fragment for `read` omits the trigger so polling stops. Reserve row heights to avoid layout shift.

**Red-pen sequence.** The server returns the row with `data-state="corrected"`, the old value in `<s class="strike">` and the new value in `<span class="hand">`. `redpen.js` runs only for rows with `data-animate="1"`, draws the strike by animating `stroke-dashoffset` on an inline SVG path (wavy via a quadratic path), then reveals the handwriting with `clip-path: inset(0 100% 0 0)` to `inset(0)` using `steps()` timing. Under `prefers-reduced-motion: reduce` skip to the final state. The animation attribute is removed after it runs so a reload shows the final state without motion.

**Stamp.** An inline SVG, `rotate(-2deg)`, text as `<text>`, double border via two `<rect>`s, `aria-label` "Checked on {date}". It exists in the DOM only when the case is confirmed and no blocking finding is unresolved; compute that on the server.

**Print.** `@page { size: A4; margin: 18mm }`, `break-inside: avoid` on evidence rows and sheets, no background images, backgrounds for status washes allowed only with `print-color-adjust: exact`. Hide navigation. Verify through `make dossier-pdf` and the E2E-10 test.

**htmx under a strict CSP.** Vendor htmx 2.x into `static/js/` with its licence. Add `<meta name="htmx-config" content='{"includeIndicatorStyles": false, "allowEval": false, "allowScriptTags": false}'>` so htmx neither injects an inline `<style>` nor evaluates code. Do not use `hx-on`, `js:` values or bracketed event filters (they need eval). Put small glue code (CSRF header, language toggle) in `static/js/` modules.

**Escaping.** Render HTML through Starlette's `Jinja2Templates` and prove escaping early with the XSS test in `TESTING.md` section 8. If you create any other Jinja environment (for example for the plain-text notices), set `autoescape` explicitly and test it.

**CSRF and Host.** Middleware rejects any `Host` other than `127.0.0.1:{port}` or `localhost:{port}`. A random token is set in a cookie and also rendered in a `<meta name="csrf">`; htmx sends it in the `X-CSRF-Token` header via a tiny `htmx:configRequest` listener; forms include a hidden input; compare with `secrets.compare_digest`.

**Background reads.** Use `asyncio.create_task` with a module-level semaphore of 1 for Ollama; persist state transitions in SQLite so a page reload during reading shows truth. On startup, mark papers stuck in `reading` as `failed` with a clear error.

**Interest computation.** Implement exactly `DOMAIN_RULES.md` section 5: per-month rounding half up, partial month `round(balance * r * d / D)`, calendar-month periods from the day after the due date with `relativedelta`, rate chosen by the latest effective date on or before each period's start. Build `steps` as you go; the working page renders them; `sum(step.interest)` must equal the result. Golden outputs: 2,283,919 and 9,780,909 paise for the two vectors, and 4,290,370 paise for the demo case. Add `tests/golden/demo_clock.json`.

**Repair and look-alikes.** Per `AI_SPEC.md` section 7. For GSTIN, try the look-alike substitution map first; accept only a *unique* passing candidate; mark it `needs_review`; otherwise re-read the cropped box with the model. A repair never changes more than the single field.

**Replay fixtures.** Key a full read by `sha256(original uploaded bytes)` + paper kind + prompt version, and a re-read by the same plus field and box (`AI_SPEC.md` section 5.3). Never key on re-encoded bytes; JPEG encoding differs across platforms and the keys would break in CI. The generator script must produce the demo set including: an invoice whose buyer GSTIN has a `0` read as `O`, with the corresponding recorded model responses (first read has `O`; re-read returns the correct GSTIN), a malformed-JSON response, a runaway-length response. These recorded responses are *synthetic test fixtures written by you*, not model output; label them so in the fixture metadata (`"recorded_from": "synthetic"`) and in the README. When a live model is available, additionally record real responses under `"recorded_from": "live"` and use those for evaluation numbers.

**Fonts.** Follow `DESIGN.md` section 3. Use `font-display: swap` and preload the UI face. Check `document.fonts.check` in E2E.

**Hindi.** Add `lang="hi"` to the root when the language is Hindi, and to any inline Devanagari fragment in an English page. Check clipping at 360px. Numerals stay Latin.

## 9. Building the interface so it does not look generated

1. Before writing templates, write `docs/DESIGN_PLAN.md`: 8 to 12 lines restating palette, type, layout and the single memorable element from `DESIGN.md`, then list five generic defaults you will *not* use and why. Review it against section 7 of `DESIGN.md`. Keep it.
2. Build real components from the macros listed in `DESIGN.md` section 4. Do not use a UI kit.
3. After each page works, screenshot it with Playwright at 360, 768 and 1440 in English and Hindi, view the images, and fix: clipped text, orphaned labels, inconsistent spacing, centred body text, any card-grid, any decorative gradient or shadow. Record what you changed in `docs/PROGRESS.md`.
4. The first screen is the case list or the workbench, never a marketing hero. The product name appears in the header only. No taglines in the UI; the About page is plain prose.
5. Write all copy from `docs/CONTENT.md`. If you need a new string, add it to both language files in the same commit, in the same voice: sentence case, plain verbs, no apologies, no marketing words.
6. One memorable moment (red pen and stamp). Everything else stays quiet. If you are tempted to add a hover lift, a gradient, a counter animation or an icon library, stop.
7. Run `scripts/design_lint.py` and `scripts/check_contrast.py` before every UI commit. They must pass.

## 10. Gate checklist (what to run, in this order, for each gate)

| Gate | Build | Exit commands |
| --- | --- | --- |
| 0 | Tasks T0.0 to T0.9 | `make check`; `python scripts/check_contrast.py`; `python scripts/check_fonts.py`; first CI run green (or local `make ci` if no remote) |
| 1 | Tasks T1.1 to T1.8 | `uv run pytest tests/unit tests/property tests/golden -q --cov=munim_core --cov-branch --cov-fail-under=95`; `uv run mypy --strict packages/munim_core`; `uv run lint-imports` |
| 2 | Tasks T2.1 to T2.8 | `uv run pytest tests -q -m "not e2e and not live" --cov=munim_core --cov=munim_ai`; `make fixtures && make eval`; `jsonschema` validation of the report |
| 3 | Tasks T3.1 to T3.9 | `make check`; `make e2e -k "E2E-1 or E2E-3"`; axe results; screenshot review |
| 4 | Tasks T4.1 to T4.6 | `make e2e -k "E2E-2 or E2E-10"`; golden tests; run the whole `DEMO_SCRIPT.md` on replay and walk through it with Playwright |
| 5 | Tasks T5.1 to T5.7 | `make ci`; every E2E scenario in Chromium and Firefox; design lint |
| 6 | Tasks T6.1 to T6.5 (+ stretch) | clean-clone install test in a temp directory; `make ci`; secrets scan; licences check |

At the end of each gate: update `docs/TASKS.md` checkboxes, commit, and append a "Gate N complete" entry to `docs/PROGRESS.md` listing the exit commands and their outcome.

## 11. Evaluation and honesty

- Generate the synthetic set, run `make eval`, publish `eval/reports/latest.json`, render it on the Evaluation page.
- Report "wrong and passed" as the headline. Include failure examples with crops.
- State in the README which provider and model produced the numbers, and whether any were recorded from `synthetic` fixtures (those prove the harness, not the model).
- If no live model was available, say "No live-model results yet" in the README table instead of numbers, and keep the pending-live items in `docs/PROGRESS.md`.
- Fill the bracketed placeholders in `README.md`, `docs/AI_CONTRIBUTION.md`, `docs/SUBMISSION.md` only with true values; leave a visible `[TODO human: ...]` marker for anything you cannot know (maintainer email, Hindi reviewer name, model digest if offline, final repo URL).

## 12. When to stop and when not to

**Do not stop for:** missing optional tools, a failing network call, uncertainty about a detail, a flaky test (fix the flake), a lint failure, a dependency licence you can swap.

**Stop and report (after writing the state to `docs/PROGRESS.md`) only if:**
1. The event rule in section 0 is not confirmed.
2. Continuing would require committing a real personal document, a secret, or breaking a rule in section 6.
3. A gate's exit cannot be met after two genuine attempts and the documented fallback is exhausted. Then deliver what is green, say precisely what is not, and why.
4. A decision is irreversible and could reasonably go either way (for example deleting the human's existing data).

## 13. Definition of Done

All of the following, each verified in this session and recorded in `docs/PROGRESS.md`:

1. `make ci` passes locally (static, design, unit, property, integration, e2e in Chromium and Firefox, eval on replay).
2. Core coverage >= 95% lines and >= 90% branches; overall >= 85%.
3. Zero axe serious or critical issues on every page and state, in English and Hindi.
4. The demo in `docs/DEMO_SCRIPT.md` runs to completion on the replay provider, and on a live provider if one was available.
5. The three golden clock outputs match exactly.
6. A case can be deleted and no bytes of its content remain in `data/` after `VACUUM` (test).
7. The E2E network assertion shows only loopback requests in local mode.
8. `design_lint`, `check_contrast`, `check_fonts`, `check_i18n`, `check_licences`, secret scan: clean.
9. README, THIRD_PARTY, AI_CONTRIBUTION, SUBMISSION filled with true values and visible TODO markers for human-only facts.
10. A clean clone installs and runs using only the README (tested in a temp directory).
11. `git log` shows small commits, each with `Assisted-by`, from the event start only.
12. No `TODO`/`FIXME` in code without an issue-style reference; no commented-out code; no unused dependencies.

## 14. Final report (your last message)

Plain text, under 400 words, no marketing language:
- What was built and the gate reached.
- Commands run for the Definition of Done and their outcomes (pass/fail per item).
- Measured numbers copied from `eval/reports/latest.json` (or "none yet").
- What is **pending-live** or unverified, and the exact human actions needed (Hindi review, Bank Rate confirmation, live model run, repository push, video, submission form).
- Known limitations and deviations from the documents, each with the reason.

## 15. Things you must never claim

- That Munim is legal advice, gives a legal opinion, or "verifies" a document.
- Real-world accuracy, or any accuracy figure not in `latest.json`.
- That the RBI Bank Rate shown is current unless the human confirmed it in the UI.
- That the Hindi is reviewed unless a human reviewer name and date were supplied.
- That any model capability exists that `AI_SPEC.md` marks unverified, unless you probed it and recorded the probe.
- That work was done before the event if it was not, or that it was done at the event if it was not.
