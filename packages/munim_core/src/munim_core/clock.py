"""The MSMED Act payment clock: due date and compound interest (docs/DOMAIN_RULES.md section 5).

- Due date (5.2): acceptance + 15 days without a written agreement, else the agreed credit
  days capped at 45.
- Interest (5.3): three times the Bank Rate a year, compounded with monthly rests. Month k
  starts on S + k months, where S is the day after the due date (never chained month by
  month). A whole month adds round(balance x r); a final partial month of d days out of a
  period of D days adds round(balance x r x d / D). Rounding is half up, to the paisa, each
  period. Interest accrues over [S, as_on): the as-on day itself is not counted.
- Each period uses the Bank Rate row with the latest effective date on or before its start.
  A period with no such row is an error the person resolves by adding a row.
- Part-payments: interest to the payment date is added, the payment is subtracted, and the
  monthly rests restart from the payment date (an assumed simplification, DOMAIN 7.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Literal

from munim_core.dates import add_months
from munim_core.money import round_half_up

__all__ = [
    "BankRate",
    "ClockError",
    "ClockInput",
    "ClockResult",
    "MissingCreditDaysError",
    "NoBankRateError",
    "Payment",
    "PaymentTooLargeError",
    "Step",
    "compute",
    "compute_due_date",
]

NO_AGREEMENT_DAYS = 15
CREDIT_CAP_DAYS = 45
BANK_RATE_MULTIPLE = 3
StepKind = Literal["due", "month", "partial", "payment"]


class ClockError(ValueError):
    """The clock cannot be computed from these inputs."""


class MissingCreditDaysError(ClockError):
    """A written agreement was chosen but no credit days were given; ask the person."""


class NoBankRateError(ClockError):
    """No Bank Rate row is effective on or before a period start."""

    def __init__(self, needed_on: date) -> None:
        super().__init__(f"no Bank Rate effective on or before {needed_on.isoformat()}")
        self.needed_on = needed_on


class PaymentTooLargeError(ClockError):
    """A payment is larger than the balance owed on its date."""

    def __init__(self, paid_on: date, amount_paise: int, balance_paise: int) -> None:
        super().__init__(f"payment on {paid_on.isoformat()} is larger than the balance")
        self.paid_on = paid_on
        self.amount_paise = amount_paise
        self.balance_paise = balance_paise


@dataclass(frozen=True)
class BankRate:
    effective_from: date
    percent: Decimal


@dataclass(frozen=True)
class Payment:
    paid_on: date
    amount_paise: int


@dataclass(frozen=True)
class ClockInput:
    acceptance_date: date
    agreement: Literal["written", "none"]
    credit_days: int | None
    principal_paise: int
    as_on: date
    rates: tuple[BankRate, ...]
    payments: tuple[Payment, ...] = ()


@dataclass(frozen=True)
class Step:
    """One line of the working. For a payment step, closing = opening - payment."""

    kind: StepKind
    start: date
    end: date
    rate_percent: Decimal  # annual interest rate used: 3 x the Bank Rate
    opening_paise: int
    interest_paise: int
    closing_paise: int
    note_key: str
    bank_rate_percent: Decimal | None = None
    rate_effective_from: date | None = None
    days: int = 0  # d: days counted in a partial period
    period_days: int = 0  # D: length of that period
    payment_paise: int = 0


@dataclass(frozen=True)
class ClockResult:
    due_date: date
    days_late: int
    cap_applied: bool
    basis_key: str
    steps: tuple[Step, ...]
    interest_paise: int
    total_paise: int
    credit_days_used: int = 0


def compute_due_date(
    acceptance: date, agreement: str, credit_days: int | None
) -> tuple[date, bool, str]:
    """Return (due date, whether the 45-day cap applied, the i18n key of the basis)."""
    if agreement == "none":
        return acceptance + timedelta(days=NO_AGREEMENT_DAYS), False, "clock.basis.none"
    if agreement != "written":
        raise ValueError(f"unknown agreement {agreement!r}; expected 'written' or 'none'")
    if credit_days is None:
        raise MissingCreditDaysError("a written agreement needs its credit days")
    if credit_days < 0:
        raise ValueError("credit days cannot be negative")
    if credit_days > CREDIT_CAP_DAYS:
        return acceptance + timedelta(days=CREDIT_CAP_DAYS), True, "clock.basis.capped"
    return acceptance + timedelta(days=credit_days), False, "clock.basis.written"


def _rate_on(rates: tuple[BankRate, ...], day: date) -> BankRate:
    in_force = [r for r in rates if r.effective_from <= day]
    if not in_force:
        raise NoBankRateError(day)
    return max(in_force, key=lambda r: r.effective_from)


def _interest(balance: int, bank_rate: Decimal, days: int = 1, period_days: int = 1) -> int:
    """round(balance x (3 x bank rate / 100 / 12) x days / period_days), half up, in paise."""
    with localcontext() as ctx:
        ctx.prec = 60
        numerator = Decimal(balance) * BANK_RATE_MULTIPLE * bank_rate * days
        return round_half_up(numerator / (Decimal(1200) * period_days))


class _Ledger:
    """Accumulates steps and the running balance."""

    def __init__(self, balance: int) -> None:
        self.balance = balance
        self.steps: list[Step] = []

    def accrue(
        self, kind: StepKind, start: date, end: date, *, rate: BankRate, d: int, big_d: int
    ) -> None:
        interest = _interest(self.balance, rate.percent, d, big_d)
        self.steps.append(
            Step(
                kind=kind,
                start=start,
                end=end,
                rate_percent=rate.percent * BANK_RATE_MULTIPLE,
                opening_paise=self.balance,
                interest_paise=interest,
                closing_paise=self.balance + interest,
                note_key=f"working.step.{kind}",
                bank_rate_percent=rate.percent,
                rate_effective_from=rate.effective_from,
                days=d,
                period_days=big_d,
            )
        )
        self.balance += interest

    def pay(self, payment: Payment) -> None:
        if payment.amount_paise > self.balance:
            raise PaymentTooLargeError(payment.paid_on, payment.amount_paise, self.balance)
        self.steps.append(
            Step(
                kind="payment",
                start=payment.paid_on,
                end=payment.paid_on,
                rate_percent=Decimal(0),
                opening_paise=self.balance,
                interest_paise=0,
                closing_paise=self.balance - payment.amount_paise,
                note_key="working.step.payment",
                payment_paise=payment.amount_paise,
            )
        )
        self.balance -= payment.amount_paise

    def run_rests(self, anchor: date, stop: date, rates: tuple[BankRate, ...]) -> None:
        """Monthly rests from anchor up to (not including) stop."""
        k = 0
        while self.balance > 0:
            start, end = add_months(anchor, k), add_months(anchor, k + 1)
            if start >= stop:
                return
            rate = _rate_on(rates, start)
            if end <= stop:
                length = (end - start).days
                self.accrue("month", start, end, rate=rate, d=length, big_d=length)
                k += 1
                continue
            self.accrue(
                "partial", start, stop, rate=rate, d=(stop - start).days, big_d=(end - start).days
            )
            return


def compute(inp: ClockInput) -> ClockResult:
    """Compute the due date, days late, interest to the as-on date and every step of the working."""
    if inp.principal_paise < 0:
        raise ValueError("the principal cannot be negative")
    for payment in inp.payments:
        if payment.amount_paise <= 0:
            raise ValueError("a payment must be more than zero")
    due, capped, basis = compute_due_date(inp.acceptance_date, inp.agreement, inp.credit_days)
    ledger = _Ledger(inp.principal_paise)
    ledger.steps.append(
        Step(
            kind="due",
            start=inp.acceptance_date,
            end=due,
            rate_percent=Decimal(0),
            opening_paise=inp.principal_paise,
            interest_paise=0,
            closing_paise=inp.principal_paise,
            note_key=basis,
        )
    )
    interest_from = due + timedelta(days=1)
    payments = sorted((p for p in inp.payments if p.paid_on <= inp.as_on), key=lambda p: p.paid_on)
    anchor = interest_from
    for payment in payments:
        if payment.paid_on > anchor:
            ledger.run_rests(anchor, payment.paid_on, inp.rates)
            anchor = payment.paid_on
        ledger.pay(payment)
    ledger.run_rests(anchor, inp.as_on, inp.rates)
    interest = sum(step.interest_paise for step in ledger.steps)
    credit_days = (due - inp.acceptance_date).days
    return ClockResult(
        due_date=due,
        days_late=max(0, (inp.as_on - due).days),
        cap_applied=capped,
        basis_key=basis,
        steps=tuple(ledger.steps),
        interest_paise=interest,
        total_paise=ledger.balance,
        credit_days_used=credit_days,
    )
