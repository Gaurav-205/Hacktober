# ADR 0001: The model proposes, deterministic code decides

Status: accepted. Date: 2026-10-12.

## Context
Gemma 4 can read printed fields from photos but can hallucinate digits. A wrong GSTIN or amount in a legal-style file is costly. The problem has many exact rules (checksums, arithmetic, statutory dates).

## Decision
The model only transcribes fields and boxes. All pass/fail decisions, calculations and user-facing sentences come from code and templates. Model output is untrusted input, validated with Pydantic, and shown beside the evidence (the box). The user confirms before anything is stamped.

## Consequences
+ Errors become visible and measurable ("wrong and passed").
+ The core is testable without a model and reusable (MCP server).
+ A smaller local model is usable because checks and a repair loop cover many misreads.
- Some misreads still pass checks. We report that rate rather than hide it.
- More code than a one-shot "LLM does everything" approach.

## Alternatives rejected
- Ask the model to judge validity: not reproducible, cannot be tested to the paisa.
- Fine-tune: no time in one day, no data.
