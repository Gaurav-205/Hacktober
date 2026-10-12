# Contributing to Munim

Thank you for helping. Munim is small and has strong opinions; this page says what they are.

## Ground rules
- Be kind and specific in reviews. We follow the Contributor Covenant 2.1 (`CODE_OF_CONDUCT.md`).
- Do not add real invoices, real GSTINs, names of real people or businesses, or screenshots of them to issues or pull requests. Describe the problem instead.
- AI coding tools are welcome. Disclose material use in the PR description and with an `Assisted-by:` commit trailer, and be able to explain every line.

## Setup
```
git clone <repo-url> munim && cd munim
make install
ollama pull gemma4:e4b        # optional; or set MUNIM_PROVIDER=replay
make run
```

## Workflow
1. Open an issue first for anything bigger than a bug fix.
2. Branch from `main`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.
3. Write the failing test first when you touch `munim_core` or `munim_ai`.
4. `make check` before pushing; `make e2e` if you touched the UI.
5. Open a PR using the template: what changed, why, how tested, screenshots (360/768/1440, en and hi) for UI, notes on rules or prompts.

## What reviewers look for
- Rules: source cited in `docs/DOMAIN_RULES.md`, golden numbers updated deliberately, both languages.
- UI: tokens only, no shadows or gradients, keyboard operable, axe clean, Hindi tested.
- Model code: output treated as untrusted; evaluation re-run if a prompt changed.
- Privacy: no logging of content; no new network calls.

## Adding a rule, a paper type, a language
See the "Where things go" section in `AGENTS.md`. For a new language, copy `en.json`, translate, have a native reader review, register the language in settings, add an E2E run.

## Reporting security issues
Do not open a public issue. See `SECURITY.md`.

## Licence
By contributing you agree your contribution is licensed under Apache-2.0.
