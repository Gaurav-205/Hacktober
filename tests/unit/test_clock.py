"""Unit tests for munim_core.clock (docs/DOMAIN_RULES.md section 5, docs/TESTING.md section 2)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from munim_core.clock import (
    BankRate,
    ClockInput,
    MissingCreditDaysError,
    NoBankRateError,
    Payment,
    PaymentTooLargeError,
    compute,
    compute_due_date,
)

pytestmark = pytest.mark.unit

FLAT_6 = (BankRate(date(2000, 1, 1), Decimal("6")),)  # 3 x 6% = 18% a year
FLAT_575 = (BankRate(date(2000, 1, 1), Decimal("5.75")),)  # 17.25% a year


def clock(
    *,
    acceptance: date,
    as_on: date,
    principal: int = 50_000_000,
    agreement: str = "written",
    credit_days: int | None = 0,
    rates: tuple[BankRate, ...] = FLAT_6,
    payments: tuple[Payment, ...] = (),
) -> ClockInput:
    return ClockInput(
        acceptance_date=acceptance,
        agreement=agreement,  # type: ignore[arg-type]
        credit_days=credit_days,
        principal_paise=principal,
        as_on=as_on,
        rates=rates,
        payments=payments,
    )


# ---------------------------------------------------------------- due date (DOMAIN 5.2)


@pytest.mark.parametrize(
    ("acceptance", "agreement", "credit_days", "due", "capped", "basis"),
    [
        (date(2026, 3, 20), "written", 30, date(2026, 4, 19), False, "clock.basis.written"),
        (date(2026, 3, 20), "written", 45, date(2026, 5, 4), False, "clock.basis.written"),
        (date(2026, 3, 20), "written", 60, date(2026, 5, 4), True, "clock.basis.capped"),
        (date(2026, 3, 20), "none", None, date(2026, 4, 4), False, "clock.basis.none"),
        (date(2026, 3, 20), "none", 30, date(2026, 4, 4), False, "clock.basis.none"),
        (date(2028, 2, 29), "written", 30, date(2028, 3, 30), False, "clock.basis.written"),
        (date(2026, 1, 31), "written", 30, date(2026, 3, 2), False, "clock.basis.written"),
        (date(2026, 12, 20), "written", 30, date(2027, 1, 19), False, "clock.basis.written"),
        (date(2026, 3, 20), "written", 0, date(2026, 3, 20), False, "clock.basis.written"),
    ],
)
def test_due_date_follows_the_agreement_and_the_45_day_cap(
    acceptance: date,
    agreement: str,
    credit_days: int | None,
    due: date,
    capped: bool,
    basis: str,
) -> None:
    assert compute_due_date(acceptance, agreement, credit_days) == (due, capped, basis)


def test_written_agreement_without_credit_days_must_be_asked() -> None:
    with pytest.raises(MissingCreditDaysError):
        compute_due_date(date(2026, 3, 20), "written", None)


@pytest.mark.parametrize("bad", [-1, -30])
def test_negative_credit_days_are_rejected(bad: int) -> None:
    with pytest.raises(ValueError, match="credit days"):
        compute_due_date(date(2026, 3, 20), "written", bad)


def test_unknown_agreement_is_rejected() -> None:
    with pytest.raises(ValueError, match="agreement"):
        compute_due_date(date(2026, 3, 20), "oral", 30)


# ---------------------------------------------------------------- golden outputs (DOMAIN 5.3)


@pytest.mark.golden
def test_golden_three_whole_months_at_18_percent() -> None:
    # Interest period starts 1 Jan 2026: due 31 Dec 2025 (acceptance + 0 days).
    result = compute(clock(acceptance=date(2025, 12, 31), as_on=date(2026, 4, 1)))
    assert result.interest_paise == 2_283_919
    assert result.total_paise == 52_283_919
    assert [s.kind for s in result.steps] == ["due", "month", "month", "month"]


@pytest.mark.golden
def test_golden_twelve_whole_months_at_18_percent() -> None:
    result = compute(clock(acceptance=date(2025, 12, 31), as_on=date(2027, 1, 1)))
    assert result.interest_paise == 9_780_909
    assert sum(1 for s in result.steps if s.kind == "month") == 12


@pytest.mark.golden
def test_golden_demo_case_at_an_explicit_17_25_percent() -> None:
    result = compute(
        clock(
            acceptance=date(2026, 3, 20),
            credit_days=30,
            as_on=date(2026, 10, 13),
            rates=FLAT_575,
        )
    )
    assert result.due_date == date(2026, 4, 19)
    assert result.days_late == 177
    assert result.interest_paise == 4_290_370
    assert result.total_paise == 54_290_370
    assert result.cap_applied is False
    assert result.basis_key == "clock.basis.written"


def closed_form(principal: int, annual_percent: str, months: int) -> Decimal:
    r = Decimal(annual_percent) / Decimal(1200)
    return Decimal(principal) * ((1 + r) ** months - 1)


@pytest.mark.golden
@pytest.mark.parametrize(("as_on", "months"), [(date(2026, 4, 1), 3), (date(2027, 1, 1), 12)])
def test_monthly_rounding_stays_within_one_paisa_a_month_of_the_closed_form(
    as_on: date, months: int
) -> None:
    result = compute(clock(acceptance=date(2025, 12, 31), as_on=as_on))
    assert abs(result.interest_paise - closed_form(50_000_000, "18", months)) <= months


# ---------------------------------------------------------------- day count (DOMAIN 5.3)


def test_interest_is_zero_before_the_due_date() -> None:
    result = compute(clock(acceptance=date(2026, 3, 20), credit_days=30, as_on=date(2026, 4, 1)))
    assert result.interest_paise == 0
    assert result.days_late == 0
    assert result.total_paise == 50_000_000


def test_interest_is_zero_on_the_due_date() -> None:
    result = compute(clock(acceptance=date(2026, 3, 20), credit_days=30, as_on=date(2026, 4, 19)))
    assert (result.interest_paise, result.days_late) == (0, 0)


def test_interest_is_zero_the_day_after_the_due_date_because_as_on_is_not_counted() -> None:
    result = compute(clock(acceptance=date(2026, 3, 20), credit_days=30, as_on=date(2026, 4, 20)))
    assert result.days_late == 1
    assert result.interest_paise == 0


def test_two_days_after_the_due_date_is_a_one_day_partial_month() -> None:
    result = compute(clock(acceptance=date(2026, 3, 20), credit_days=30, as_on=date(2026, 4, 21)))
    partial = result.steps[-1]
    assert partial.kind == "partial"
    assert (partial.days, partial.period_days) == (1, 30)  # 20 Apr to 20 May 2026
    # 50,000,000 x 18% / 12 x 1/30 = 25,000 paise exactly.
    assert result.interest_paise == 25_000


def test_exactly_one_month_is_one_whole_period() -> None:
    result = compute(clock(acceptance=date(2025, 12, 31), as_on=date(2026, 2, 1)))
    assert [s.kind for s in result.steps] == ["due", "month"]
    assert result.interest_paise == 750_000


def test_periods_starting_on_the_31st_clamp_without_drifting() -> None:
    # Interest from 31 Jan 2027: periods start 31 Jan, 28 Feb, 31 Mar (never 28 Mar).
    result = compute(clock(acceptance=date(2027, 1, 30), as_on=date(2027, 4, 29)))
    months = [s for s in result.steps if s.kind == "month"]
    assert [(s.start, s.end) for s in months] == [
        (date(2027, 1, 31), date(2027, 2, 28)),
        (date(2027, 2, 28), date(2027, 3, 31)),
    ]
    partial = result.steps[-1]
    assert (partial.start, partial.end, partial.days, partial.period_days) == (
        date(2027, 3, 31),
        date(2027, 4, 29),
        29,
        30,
    )


def test_a_period_ending_on_the_as_on_date_is_a_whole_month() -> None:
    result = compute(clock(acceptance=date(2027, 1, 30), as_on=date(2027, 4, 30)))
    assert [s.kind for s in result.steps] == ["due", "month", "month", "month"]


# ---------------------------------------------------------------- Bank Rate table (DOMAIN 5.3)


def test_each_month_uses_the_rate_in_force_at_its_start() -> None:
    rates = (
        BankRate(date(2025, 1, 1), Decimal("6")),
        BankRate(date(2026, 2, 15), Decimal("5")),
    )
    result = compute(clock(acceptance=date(2025, 12, 31), as_on=date(2026, 4, 1), rates=rates))
    months = [s for s in result.steps if s.kind == "month"]
    assert [s.rate_percent for s in months] == [Decimal("18"), Decimal("18"), Decimal("15")]
    assert [s.bank_rate_percent for s in months] == [Decimal("6"), Decimal("6"), Decimal("5")]
    assert months[2].rate_effective_from == date(2026, 2, 15)
    # 1 Jan: 750,000; 1 Feb: 761,250; 1 Mar at 15%: round(51,511,250 x 0.0125) = 643,891.
    assert [s.interest_paise for s in months] == [750_000, 761_250, 643_891]


def test_rate_rows_are_used_whatever_their_order() -> None:
    rates = (
        BankRate(date(2026, 2, 15), Decimal("5")),
        BankRate(date(2025, 1, 1), Decimal("6")),
    )
    ordered = compute(clock(acceptance=date(2025, 12, 31), as_on=date(2026, 4, 1), rates=rates))
    assert ordered.interest_paise == 750_000 + 761_250 + 643_891


def test_a_period_with_no_rate_on_or_before_its_start_raises_a_typed_error() -> None:
    rates = (BankRate(date(2026, 10, 7), Decimal("5.75")),)
    with pytest.raises(NoBankRateError) as raised:
        compute(
            clock(
                acceptance=date(2026, 3, 20), credit_days=30, as_on=date(2026, 10, 13), rates=rates
            )
        )
    assert raised.value.needed_on == date(2026, 4, 20)


def test_no_rate_is_needed_when_nothing_is_late() -> None:
    result = compute(
        clock(acceptance=date(2026, 3, 20), credit_days=30, as_on=date(2026, 4, 1), rates=())
    )
    assert result.interest_paise == 0


def test_demo_case_on_the_seeded_table_uses_5_50_percent_for_every_period() -> None:
    seeded = (
        BankRate(date(2025, 6, 6), Decimal("5.75")),
        BankRate(date(2025, 12, 5), Decimal("5.50")),
        BankRate(date(2026, 10, 7), Decimal("5.75")),
    )
    result = compute(
        clock(acceptance=date(2026, 3, 20), credit_days=30, as_on=date(2026, 10, 13), rates=seeded)
    )
    assert {s.bank_rate_percent for s in result.steps if s.kind != "due"} == {Decimal("5.50")}
    assert result.interest_paise == 4_097_671
    assert result.total_paise == 54_097_671


# ---------------------------------------------------------------- part-payments (DOMAIN 5.3)


def test_payment_on_or_before_the_due_date_reduces_the_principal_without_interest() -> None:
    result = compute(
        clock(
            acceptance=date(2025, 12, 31),
            as_on=date(2026, 2, 1),
            payments=(Payment(date(2025, 12, 31), 10_000_000),),
        )
    )
    assert result.interest_paise == 600_000  # 40,000,000 x 1.5%
    assert result.total_paise == 40_600_000


def test_payment_inside_a_period_restarts_the_monthly_rests_from_the_payment_date() -> None:
    # Hand-computed: interest from 1 Jan 2026 at 18%; Rs 1,00,000 paid on 16 Jan 2026.
    # 1 Jan to 16 Jan is 15 days of a 31-day period: round(50,000,000 x 0.015 x 15/31) = 362,903.
    # Balance 50,362,903 - 10,000,000 = 40,362,903. Rests restart on 16 Jan.
    # 16 Jan to 16 Feb is a whole month: round(40,362,903 x 0.015) = 605,444 -> 40,968,347.
    # 16 Feb to 1 Mar is 13 days of 28: round(40,968,347 x 0.015 x 13/28) = 285,315.
    result = compute(
        clock(
            acceptance=date(2025, 12, 31),
            as_on=date(2026, 3, 1),
            payments=(Payment(date(2026, 1, 16), 10_000_000),),
        )
    )
    assert [s.kind for s in result.steps] == ["due", "partial", "payment", "month", "partial"]
    assert [s.interest_paise for s in result.steps] == [0, 362_903, 0, 605_444, 285_315]
    assert result.interest_paise == 362_903 + 605_444 + 285_315
    assert result.total_paise == 40_968_347 + 285_315
    payment = result.steps[2]
    assert (payment.opening_paise, payment.closing_paise) == (50_362_903, 40_362_903)


def test_payment_equal_to_the_balance_closes_the_account() -> None:
    result = compute(
        clock(
            acceptance=date(2025, 12, 31),
            as_on=date(2026, 6, 1),
            payments=(Payment(date(2026, 2, 1), 50_750_000),),
        )
    )
    assert result.total_paise == 0
    assert result.interest_paise == 750_000


def test_overpayment_is_rejected() -> None:
    with pytest.raises(PaymentTooLargeError):
        compute(
            clock(
                acceptance=date(2025, 12, 31),
                as_on=date(2026, 6, 1),
                payments=(Payment(date(2026, 2, 1), 50_750_001),),
            )
        )


def test_payments_after_the_as_on_date_are_not_part_of_the_figure() -> None:
    late = compute(
        clock(
            acceptance=date(2025, 12, 31),
            as_on=date(2026, 4, 1),
            payments=(Payment(date(2026, 5, 1), 1_000),),
        )
    )
    assert late.interest_paise == 2_283_919


@pytest.mark.parametrize("amount", [0, -5])
def test_non_positive_payments_are_rejected(amount: int) -> None:
    with pytest.raises(ValueError, match="payment"):
        compute(
            clock(
                acceptance=date(2025, 12, 31),
                as_on=date(2026, 4, 1),
                payments=(Payment(date(2026, 2, 1), amount),),
            )
        )


# ---------------------------------------------------------------- steps and invariants


def test_steps_add_up_to_the_result_and_chain_balances() -> None:
    result = compute(
        clock(
            acceptance=date(2026, 3, 20),
            credit_days=30,
            as_on=date(2026, 10, 13),
            rates=FLAT_575,
            payments=(Payment(date(2026, 6, 3), 7_500_000),),
        )
    )
    assert sum(s.interest_paise for s in result.steps) == result.interest_paise
    for before, after in zip(result.steps, result.steps[1:], strict=False):
        assert after.opening_paise == before.closing_paise
    assert result.steps[-1].closing_paise == result.total_paise
    for step in result.steps:
        if step.kind != "payment":
            assert step.closing_paise == step.opening_paise + step.interest_paise


def test_due_step_records_the_basis_and_dates() -> None:
    result = compute(clock(acceptance=date(2026, 3, 20), credit_days=60, as_on=date(2026, 5, 4)))
    due = result.steps[0]
    assert due.kind == "due"
    assert (due.start, due.end) == (date(2026, 3, 20), date(2026, 5, 4))
    assert due.note_key == "clock.basis.capped"
    assert result.cap_applied is True


def test_negative_principal_is_rejected() -> None:
    with pytest.raises(ValueError, match="principal"):
        compute(clock(acceptance=date(2025, 12, 31), as_on=date(2026, 4, 1), principal=-1))


def test_long_delays_complete_quickly() -> None:
    result = compute(clock(acceptance=date(2017, 7, 1), as_on=date(2026, 10, 13)))
    assert result.interest_paise > 0
    assert result.steps[-1].end == date(2026, 10, 13)
    assert result.days_late == (date(2026, 10, 13) - date(2017, 7, 1)).days
    assert date(2017, 7, 1) + timedelta(days=result.days_late) == date(2026, 10, 13)
