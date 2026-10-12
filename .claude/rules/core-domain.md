---
paths:
  - "packages/munim_core/**"
  - "rules/**"
  - "tests/unit/**"
  - "tests/property/**"
  - "tests/golden/**"
---

# Rules for the pure core (money, dates, ids, verify, clock)

- Pure code only: no I/O, network, filesystem, framework or model imports. `import-linter` enforces this, so keep the contract green.
- Money is integer paise. Build Decimals from strings or ints. Round with `ROUND_HALF_UP`, each month, exactly as in `docs/DOMAIN_RULES.md` section 5.3.
- Golden values (exact paise): 2,283,919; 9,780,909; demo case 4,290,370 interest and 54,290,370 total, 177 days late. Never change a golden value without updating `docs/DOMAIN_RULES.md` and explaining why in the commit.
- Monthly periods start at `start + relativedelta(months=k)`; never chain. The partial-month day count D is the length of that period.
- Findings carry `rule_id`, `status`, `severity`, `message_key`, string `params` (`*_paise` as digits, `*_date` as ISO) and `rule_version`. No English text in core.
- Use "passed" or "failed", never "verified". A passed check does not prove a value is true.
- Test first: write the failing test, see it fail, implement, see it pass. Every rule needs pass, fail, boundary and skipped tests. Use hypothesis for the properties in `docs/TESTING.md` section 3.
- After changes here, ask the `domain-verifier` subagent to recompute independently.
