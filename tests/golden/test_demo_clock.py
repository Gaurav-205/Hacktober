"""Golden file for the demo case's working (docs/DOMAIN_RULES.md 5.3, docs/DEMO_SCRIPT.md).

tests/golden/demo_clock.json holds the inputs and every step. The totals in it are the ones
DOMAIN_RULES 5.3 states (4,290,370 paise at an explicit 17.25%; 4,097,671 on the seeded table),
so the file cannot drift from the document unnoticed. Re-bless with `make bless` only after
reading the diff.
"""

from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from munim_core.clock import BankRate, ClockInput, ClockResult, compute

pytestmark = pytest.mark.golden

GOLDEN = Path(__file__).with_name("demo_clock.json")
CASES = {
    "explicit_17_25": (BankRate(date(2000, 1, 1), Decimal("5.75")),),
    "seeded_table": (
        BankRate(date(2025, 6, 6), Decimal("5.75")),
        BankRate(date(2025, 12, 5), Decimal("5.50")),
        BankRate(date(2026, 10, 7), Decimal("5.75")),
    ),
}
DOCUMENTED = {
    "explicit_17_25": {"interest_paise": 4_290_370, "total_paise": 54_290_370},
    "seeded_table": {"interest_paise": 4_097_671, "total_paise": 54_097_671},
}


def run(rates: tuple[BankRate, ...]) -> ClockResult:
    return compute(
        ClockInput(
            acceptance_date=date(2026, 3, 20),
            agreement="written",
            credit_days=30,
            principal_paise=50_000_000,
            as_on=date(2026, 10, 13),
            rates=rates,
        )
    )


def as_json(result: ClockResult) -> dict[str, object]:
    return {
        "due_date": result.due_date.isoformat(),
        "days_late": result.days_late,
        "interest_paise": result.interest_paise,
        "total_paise": result.total_paise,
        "steps": [
            {
                "kind": s.kind,
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "rate_percent": str(s.rate_percent),
                "days": s.days,
                "period_days": s.period_days,
                "opening_paise": s.opening_paise,
                "interest_paise": s.interest_paise,
                "closing_paise": s.closing_paise,
            }
            for s in result.steps
        ],
    }


def test_demo_clock_matches_the_reviewed_golden_file() -> None:
    current = {name: as_json(run(rates)) for name, rates in CASES.items()}
    if os.environ.get("MUNIM_BLESS") == "1":
        GOLDEN.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    assert json.loads(GOLDEN.read_text(encoding="utf-8")) == current


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden_file_totals_are_the_documented_ones(name: str) -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))[name]
    assert golden["interest_paise"] == DOCUMENTED[name]["interest_paise"]
    assert golden["total_paise"] == DOCUMENTED[name]["total_paise"]
    assert (golden["due_date"], golden["days_late"]) == ("2026-04-19", 177)
