---
paths:
  - "packages/munim_ai/**"
  - "eval/**"
  - "scripts/gen_fixtures.py"
  - "tests/contract/**"
---

# Rules for the model layer and evaluation

- The model only transcribes fields and boxes (`docs/AI_SPEC.md` section 2). Validate every response with Pydantic. Treat model text as untrusted data; it never reaches templates unescaped and never decides a check.
- Boxes are `[y1, x1, y2, x2]` on a 0 to 1000 grid. Store them as returned and convert only for display or cropping. Crop from the prepared image.
- Prompts live in files with a `prompt_version` header. Changing a prompt means bumping the version, re-running `make eval` and updating the report.
- Replay keys: `sha256(original uploaded bytes)` + paper kind + prompt version (re-reads add field and box). Never key on re-encoded bytes. Hand-written recordings are `"recorded_from": "synthetic"`; live ones are `"live"`.
- Providers: Ollama is the default and is probed before relying on JSON `format` or vision. Gemini runs only with consent and an environment key, and the uploaded file is deleted after each call. Replay never falls back silently (`ReplayMiss`).
- Mask Aadhaar-like numbers during normalisation, before anything is stored or logged. Never log field values or document text.
- Fixtures are synthetic, seeded and deterministic. Real papers stay in `eval/real/` (gitignored), and only aggregate results are published.
- The headline metric is "wrong and passed". Never quote a number that is not in `eval/reports/latest.json`, and always say which provider and model produced it.
