# Third-party components

Maintained by hand and checked by `scripts/check_licences.py`. Versions come from `uv.lock`; fill the version column when the lock file exists. Do not add a dependency without a row here.

| Component | Version | Licence | Used for | Modified? |
| --- | --- | --- | --- | --- |
| Gemma 4 weights (Google DeepMind) | [tag/digest] | Apache 2.0 (per model card; link at submission) | Reading photos of papers | No |
| Ollama | [version] | MIT | Local model runtime | No |
| python-stdnum | 2.2 | LGPL-2.1-or-later | GSTIN, PAN, Aadhaar validation | No (dynamically imported) |
| FastAPI / Starlette / Uvicorn | [ ] | MIT / BSD-3 | Web framework and server | No |
| Jinja2 / MarkupSafe | [ ] | BSD-3 | Templates | No |
| Pydantic / pydantic-settings | [ ] | MIT | Validation, settings | No |
| python-multipart | [ ] | Apache-2.0 | Uploads | No |
| python-dateutil | [ ] | Apache-2.0 / BSD-3 | Month arithmetic | No |
| rapidfuzz | [ ] | MIT | Name similarity | No |
| Pillow / pillow-heif | [ ] | HPND / BSD-3 | Images | No |
| pypdfium2 | [ ] | Apache-2.0 / BSD-3 | PDF to image | No |
| httpx | [ ] | BSD-3 | HTTP client | No |
| ollama (python client) | [ ] | MIT | Provider | No |
| google-genai (optional) | [ ] | Apache-2.0 | Hosted provider | No |
| structlog | [ ] | MIT / Apache-2.0 | Logging | No |
| PyYAML | [ ] | MIT | Rule files | No |
| python-ulid | [ ] | MIT | IDs | No |
| htmx | 2.0.11 | 0BSD (Zero-Clause BSD) | Partial updates (vendored file `static/js/vendor/htmx.min.js` with `htmx.LICENSE`) | No |
| Mukta (Ek Type) | [ ] | OFL-1.1 | UI font, Latin + Devanagari | No (WOFF2 conversion only) |
| Kalam (Indian Type Foundry) | [ ] | OFL-1.1 | Handwriting face for corrections | No (WOFF2 conversion only) |
| IBM Plex Sans (+ Devanagari) | [ ] | OFL-1.1 | Fallback UI font, only if Mukta lacks `tnum` | No |
| Dev: pytest, pytest-asyncio, pytest-cov, hypothesis, playwright (pinned 1.56.0 for Chromium build 1194), pytest-playwright, axe-playwright-python, ruff, mypy, types-pyyaml, types-python-dateutil, bandit, pip-audit, import-linter, pre-commit, detect-secrets, reportlab, fonttools, brotli, jsonschema, pypdf | see `uv.lock` | MIT, BSD, Apache-2.0, MPL-2.0 (checked by `scripts/check_licences.py`) | Quality tooling, fixture generation, report schema validation (jsonschema), PDF text checks in E2E-10 (pypdf) | No |
| text-unidecode (transitive, dev only, via pytest-playwright and python-slugify) | see `uv.lock` | Artistic License or GPL (dual); used under the Artistic License | Not used by Munim directly | No; exception recorded in `docs/adr/0007-dev-only-licence-exception.md` |
| razorpay/ifsc data (stretch) | [commit] | MIT (data stated public domain by the repository) | IFSC check | No |

## Ideas studied, no code copied
- VoltAgent/awesome-design-md (MIT): the DESIGN.md format. See `DESIGN.md` provenance paragraph.
- gst-einvoice-mcp (MIT), Bahi Kirana Receipt Desk (MIT): reference for validation and receipt flows. If any code is copied later, list file, commit and licence here and keep the licence header.

## Rules
Allowed licences: MIT, BSD-2/3, Apache-2.0, ISC, MPL-2.0, PSF, HPND, OFL-1.1 (fonts), LGPL-2.1+ (python-stdnum only, unmodified). Anything else needs a written exception in `docs/adr/`.
