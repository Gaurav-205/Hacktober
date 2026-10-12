# ADR 0006: Legal modelling assumptions are explicit and editable

Status: accepted. Date: 2026-10-12.

## Context
The MSMED Act's deadlines and interest rule are clear in structure but leave modelling choices (day count in a partial month, interest base, which Bank Rate applies when it changes, part-payment allocation) and legal questions (whether registration must predate the supply). Sources read were secondary. The RBI Bank Rate value (5.75%) was read from the RBI home page on 12 Oct 2026 but its effective date and history were not verified.

## Decision
- Implement the rule structure in `munim_core.clock` with each assumption named (see `DOMAIN_RULES.md` section 7) and shown on the working page.
- Keep the Bank Rate in an editable table seeded with one unverified row; the UI shows "not confirmed by you" until the user confirms.
- Offer the interest-base toggle; default to invoice total.
- Show eligibility uncertainty with the cited cases; never compute a verdict on eligibility.
- Exclude Section 43B(h).
- Every legal sentence in the notice has a rule id; the notice is marked draft and not legal advice.

## Consequences
+ Honest, reviewable, and easy to correct by an accountant.
- The tool asks the user to confirm more things; accepted as the price of not overclaiming.

## Alternatives rejected
- Hard-code a single interpretation silently.
- Refuse to compute until counsel confirms (makes the tool useless).
