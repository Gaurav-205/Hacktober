# AI contribution statement

Written in plain language for the Hack Day hosts, for contributors, and for anyone judging the project. Fill the brackets at submission time; do not leave them blank.

## 1. What Munim's model does

Munim uses **Gemma 4** (Google DeepMind; open weights; Apache 2.0 licence per the model card; **paste the exact licence link from the model card here at submission**, do not guess a URL) to look at a photograph of a business paper and write down the fields it can see, with a rectangle showing where each was found. Model used in the demo: **[gemma4:e4b via Ollama, version/digest ___]**. Hosted option: **[gemma-4-31b-it via the Gemini API]** (only if the user opts in).

The model is replaceable: anything that implements the `Provider` interface can be used. The recorded provider exists for tests and a fallback demo and is labelled in the UI.

## 2. What the model does not do

It does not decide whether a paper is correct, calculate what is owed, interpret the law, or write the notice. Those are deterministic code and templates that anyone can read in `packages/munim_core` and `packages/munim_web/src/munim_web/notices`. The model's output is treated as untrusted input, validated, checked, and confirmed by the person.

## 3. Why an open-weight model matters here

Papers stay on the user's computer. The tool works without internet once the model is downloaded. A small shop or an accountant's office can run it without paying per page or sending customer documents to a third party, and anyone can inspect and replace each part.

## 4. How the model is measured

`make eval` produces a report (see the Evaluation page and `docs/EVAL_REAL.md`). The most important number is "wrong and passed": how often the model's value is wrong and every automated check still accepts it. Numbers at submission time: **[fill from eval/reports/latest.json: n, field exact match, wrong-and-passed, repair outcomes, date, model]**. Synthetic results do not predict real-world performance; the real-paper section describes what was tried locally without publishing the papers.

## 5. AI coding assistance used to build the project

MLH requires disclosure of AI coding tools. Complete this table from the real history at submission time; do not guess.

| Tool | Used for | Parts of the repository touched | Human review |
| --- | --- | --- | --- |
| [Claude Code / model name] | [scaffolding, tests, templates...] | [paths] | [who reviewed; how] |
| [other] | | | |

Every commit that includes material AI-generated code carries a trailer `Assisted-by: <tool>`. The planning documents in `docs/` and `DESIGN.md` were drafted with an AI assistant before the event, from research the team reviewed; they contain specifications, not application code. [Confirm this statement is true at submission, and describe exactly what existed before the event.]

## 6. Reused components (libraries, data, fonts)

Allowed by event rules (libraries and public datasets). Full list with licences in `THIRD_PARTY.md`; summary:

| Component | Licence | Used for |
| --- | --- | --- |
| python-stdnum | LGPL-2.1+ | GSTIN, PAN, Aadhaar validation |
| FastAPI, Starlette, Uvicorn, Jinja2, Pydantic | MIT / BSD | Web app and validation |
| htmx | BSD-2-Clause | Partial page updates |
| Pillow, pillow-heif, pypdfium2 | HPND, BSD, Apache-2.0/BSD | Images and PDFs |
| rapidfuzz | MIT | Name similarity |
| Ollama (client and runtime) | MIT | Local model serving |
| google-genai | Apache-2.0 | Optional hosted provider |
| Mukta, Kalam | OFL-1.1 | Fonts |
| razorpay/ifsc data (stretch) | MIT (data public domain per the repository) | IFSC lookup |
| Ideas studied but not copied | gst-einvoice-mcp (MIT), Bahi Kirana Receipt Desk (MIT) | Reference for validation and receipt flows; no code copied unless listed in THIRD_PARTY.md with licence and commit |

## 7. Honest limitations

- Reading quality varies with photo quality and handwriting; some fields will need hand entry.
- The legal rules were summarised from secondary sources; some are marked unverified in `docs/DOMAIN_RULES.md`.
- The Hindi interface text and notice were drafted by an AI assistant and **[reviewed by ___ on ___ / not yet reviewed by a native speaker]**.
- Munim has been tested on **[n]** synthetic papers and **[k]** real papers (not published).
