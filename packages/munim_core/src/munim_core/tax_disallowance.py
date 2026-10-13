"""Section 43B(h) Income Tax disallowance calculation (Finance Act 2023).

Under Section 43B(h) of the Income-tax Act, 1961, any sum payable by an assessee (buyer)
to a micro or small enterprise beyond the time limit specified in Section 15 of the
MSMED Act, 2006 (15 days or agreed up to 45 days) shall be allowed as a deduction only
in the previous year in which such sum is actually paid.

If an invoice is unpaid by March 31 of the financial year in which it fell due, the buyer
cannot claim the expense in that financial year, leading to added taxable income and tax.
Furthermore, compound interest under Section 16 of the MSMED Act is non-deductible under
Section 23 of the MSMED Act and Section 40(a) of the Income-tax Act.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from munim_core.money import Paise, round_half_up

__all__ = [
    "DisallowanceResult",
    "compute_43b_disallowance",
    "financial_year_for_date",
    "format_fy",
]


@dataclass(frozen=True, slots=True)
class DisallowanceResult:
    """The Section 43B(h) income tax disallowance assessment."""

    is_disallowed: bool
    is_at_risk: bool
    financial_year: str
    fy_end_date: date
    disallowed_amount_paise: Paise
    estimated_tax_penalty_paise: Paise
    tax_penalty_at_30_percent_paise: Paise
    interest_non_deductible: bool
    citation: str


def financial_year_for_date(d: date) -> tuple[date, date]:
    """Return the (start_date, end_date) of the Indian Financial Year containing d.

    April 1 to March 31.
    """
    if d.month >= 4:
        return date(d.year, 4, 1), date(d.year + 1, 3, 31)
    return date(d.year - 1, 4, 1), date(d.year, 3, 31)


def format_fy(fy_start: date) -> str:
    """Format FY starting date as 'YYYY-YY', e.g. 2024 -> '2024-25'."""
    start_yr = fy_start.year
    end_yr_short = (start_yr + 1) % 100
    return f"{start_yr}-{end_yr_short:02d}"


def compute_43b_disallowance(
    invoice_total_paise: Paise,
    due_date: date,
    as_on: date,
    paid_on: date | None = None,
    tax_rate_percent: Decimal = Decimal("25.0"),
) -> DisallowanceResult:
    """Assess whether an invoice is disallowed or at risk under Section 43B(h).

    - If paid on or before the due date's FY March 31: allowed in that FY.
    - If unpaid or paid after the FY March 31, and due date <= March 31: disallowed in that FY.
    - If due date has passed but FY March 31 has not yet arrived: at risk of disallowance.
    """
    fy_start, fy_end = financial_year_for_date(due_date)
    fy_name = format_fy(fy_start)

    is_overdue = as_on > due_date

    # Did the payment occur on or before the end of the financial year?
    paid_within_fy = paid_on is not None and paid_on <= fy_end

    # Has the financial year ended as of the evaluation date?
    fy_has_ended = as_on > fy_end

    is_disallowed = False
    is_at_risk = False

    if paid_within_fy:
        # Paid within the same financial year: allowable deduction in that FY
        is_disallowed = False
        is_at_risk = False
        disallowed_amount = 0
    elif fy_has_ended:
        # FY ended and either unpaid or paid after FY end
        is_disallowed = True
        disallowed_amount = invoice_total_paise
    elif is_overdue:
        # Overdue under MSMED Act, but FY has not ended yet
        is_at_risk = True
        disallowed_amount = invoice_total_paise
    else:
        # Not overdue yet
        disallowed_amount = 0

    penalty_25 = round_half_up(Decimal(disallowed_amount) * (tax_rate_percent / Decimal(100)))
    penalty_30 = round_half_up(Decimal(disallowed_amount) * (Decimal("30.0") / Decimal(100)))

    return DisallowanceResult(
        is_disallowed=is_disallowed,
        is_at_risk=is_at_risk,
        financial_year=fy_name,
        fy_end_date=fy_end,
        disallowed_amount_paise=disallowed_amount,
        estimated_tax_penalty_paise=penalty_25,
        tax_penalty_at_30_percent_paise=penalty_30,
        interest_non_deductible=True,
        citation="Income-tax Act, 1961 s.43B(h) read with MSMED Act, 2006 s.15 & s.23",
    )
