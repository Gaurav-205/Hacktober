# ADR 0005: Apache-2.0 licence for the code

Status: accepted. Date: 2026-10-12.

## Context
Track 2 requires an OSI-approved licence. The model (Gemma 4) is Apache 2.0 per its model card. python-stdnum is LGPL-2.1-or-later and is used as an unmodified, dynamically imported library.

## Decision
License Munim's code under Apache-2.0 (explicit patent grant, compatible with the model's licence). Fonts remain under OFL-1.1 with their licence files. htmx is BSD-2-Clause. `THIRD_PARTY.md` lists every dependency, version and licence, and `scripts/check_licences.py` enforces an allow-list.

## Consequences
+ Permissive for users and contributors; clear for judges.
- LGPL library must remain replaceable: do not vendor-modify it; document in `THIRD_PARTY.md`.

## Alternatives rejected
- MIT: acceptable, but lacks the patent grant.
- AGPL: would discourage use by accountants' offices and associations.
