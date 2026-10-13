"""Tests for Section 43B(h) Income Tax disallowance calculation."""

from datetime import date

from munim_core.tax_disallowance import (
    compute_43b_disallowance,
    financial_year_for_date,
    format_fy,
)


def test_financial_year_boundaries() -> None:
    # April 1st starts new FY
    fy_start, fy_end = financial_year_for_date(date(2024, 4, 1))
    assert fy_start == date(2024, 4, 1)
    assert fy_end == date(2025, 3, 31)
    assert format_fy(fy_start) == "2024-25"

    # March 31st belongs to previous FY
    fy_start, fy_end = financial_year_for_date(date(2024, 3, 31))
    assert fy_start == date(2023, 4, 1)
    assert fy_end == date(2024, 3, 31)
    assert format_fy(fy_start) == "2023-24"

    # January belongs to FY starting previous year
    fy_start, fy_end = financial_year_for_date(date(2024, 1, 15))
    assert fy_start == date(2023, 4, 1)
    assert fy_end == date(2024, 3, 31)


def test_disallowed_when_unpaid_after_fy_end() -> None:
    # Invoice was due on 10 Feb 2024 (FY 2023-24), still unpaid on 15 April 2024 (FY 2024-25)
    result = compute_43b_disallowance(
        invoice_total_paise=100_000_00,  # ₹1,00,000.00
        due_date=date(2024, 2, 10),
        as_on=date(2024, 4, 15),
        paid_on=None,
    )
    assert result.is_disallowed is True
    assert result.financial_year == "2023-24"
    assert result.disallowed_amount_paise == 100_000_00
    assert result.estimated_tax_penalty_paise == 25_000_00  # 25% of 1,00,000
    assert result.tax_penalty_at_30_percent_paise == 30_000_00
    assert result.interest_non_deductible is True


def test_allowed_when_paid_within_same_fy() -> None:
    # Invoice due 10 Feb 2024, paid 25 March 2024 (before March 31)
    result = compute_43b_disallowance(
        invoice_total_paise=50_000_00,
        due_date=date(2024, 2, 10),
        as_on=date(2024, 4, 1),
        paid_on=date(2024, 3, 25),
    )
    assert result.is_disallowed is False
    assert result.disallowed_amount_paise == 0
    assert result.estimated_tax_penalty_paise == 0


def test_disallowed_when_paid_in_next_fy_after_due_date() -> None:
    # Invoice due 10 Feb 2024, paid 15 April 2024 (after FY 2023-24 closed)
    result = compute_43b_disallowance(
        invoice_total_paise=50_000_00,
        due_date=date(2024, 2, 10),
        as_on=date(2024, 5, 1),
        paid_on=date(2024, 4, 15),
    )
    # Disallowed in FY 2023-24 because it was unpaid on 31 March 2024 and beyond due date
    assert result.is_disallowed is True
    assert result.financial_year == "2023-24"
    assert result.disallowed_amount_paise == 50_000_00
    assert result.estimated_tax_penalty_paise == 12_500_00


def test_at_risk_when_overdue_before_fy_end() -> None:
    # Invoice due 10 Jan 2025, evaluated on 15 Feb 2025 (FY 2024-25 end is 31 March 2025)
    result = compute_43b_disallowance(
        invoice_total_paise=200_000_00,
        due_date=date(2025, 1, 10),
        as_on=date(2025, 2, 15),
        paid_on=None,
    )
    assert result.is_disallowed is False
    assert result.is_at_risk is True
    assert result.disallowed_amount_paise == 200_000_00
    assert result.estimated_tax_penalty_paise == 50_000_00


def test_not_at_risk_when_not_yet_due() -> None:
    # Invoice due 10 March 2025, evaluated on 1 March 2025 (not overdue yet)
    result = compute_43b_disallowance(
        invoice_total_paise=200_000_00,
        due_date=date(2025, 3, 10),
        as_on=date(2025, 3, 1),
        paid_on=None,
    )
    assert result.is_disallowed is False
    assert result.is_at_risk is False
