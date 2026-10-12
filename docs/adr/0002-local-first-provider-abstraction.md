# ADR 0002: Local-first, with a provider abstraction

Status: accepted. Date: 2026-10-12.

## Context
Papers are private business records. Track 2 of the event rewards open-source AI with an open-weight model. Venue Wi-Fi at hackathons is unreliable and a live model may be slow or unavailable.

## Decision
One `Provider` interface with three implementations: `ollama` (default, local Gemma 4), `gemini` (hosted Gemma 4, explicit consent), `replay` (recorded responses for tests and as a labelled demo fallback). The app binds to loopback, makes no third-party requests, and self-hosts fonts and scripts.

## Consequences
+ Works offline; privacy story is simple and testable (network assertion in E2E).
+ Demo has a safety net that is honest because the UI labels it.
+ The same code runs in CI without a model.
- Local inference speed depends on the laptop; we measure and report latency.
- Ollama behaviour with Gemma 4 vision and JSON output is unverified; preflight probes check at runtime and the code does not rely on `format` unless the probe passes.

## Alternatives rejected
- Hosted-only: weaker privacy claim, depends on network and quota (rate limits unpublished).
- Bundled model weights in the repo: too large, unnecessary.
