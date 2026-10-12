# ADR 0007: A dev-only transitive dependency outside the licence allow-list

Status: accepted. Date: 2026-10-12.

## Context
`scripts/check_licences.py` enforces the allow-list in `THIRD_PARTY.md`. `pytest-playwright` (Apache-2.0, the standard pytest plugin for Playwright) depends on `python-slugify` (MIT), which depends on `text-unidecode`. `text-unidecode` is dual-licensed under the Artistic License or the GPL.

## Decision
Allow `text-unidecode` as a named exception in `scripts/check_licences.py`, used unmodified under the Artistic License. It is installed only in the dev dependency group for the test runner. Munim's code never imports it, and it is not part of the application.

## Consequences
+ The browser test suite keeps the maintained Playwright plugin instead of hand-written fixtures.
- One package needs a written reason. The checker still fails on any new package outside the allow-list.

## Alternatives rejected
- Replacing `pytest-playwright` with our own fixtures: more test code to maintain for no change to what ships.
