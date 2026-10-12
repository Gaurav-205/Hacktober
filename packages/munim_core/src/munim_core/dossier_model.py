"""The evidence file's content, decided in pure code (docs/ARCHITECTURE.md 5.3 and 5.4).

The web layer formats; this module decides: each field's status, whether the case may be
confirmed, whether the stamp shows, which assumptions apply, and the clock outcome with any
error turned into a message key. Nothing here formats for display.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from munim_core.clock import (
    BankRate,
    ClockInput,
    ClockResult,
    MissingCreditDaysError,
    NoBankRateError,
    PaymentTooLargeError,
    compute,
)
from munim_core.verify.models import FieldRef, Finding, Status

__all__ = [
    "Acceptance",
    "ClaimInput",
    "ClaimRow",
    "ClockOutcome",
    "DossierModel",
    "RateRow",
    "build_dossier",
    "can_confirm",
    "field_statuses",
    "is_accepted",
    "run_clock",
    "stamp_visible",
    "unresolved_blocking",
]

# Worst first: a field shows the most serious outcome of any rule that names it.
_RANK = {Status.FAILED: 0, Status.NEEDS_REVIEW: 1, Status.PASSED: 2, Status.SKIPPED: 3}


@dataclass(frozen=True)
class Acceptance:
    """A finding a person accepted with a typed reason. The web layer drops lapsed ones."""

    rule_id: str
    fields: tuple[FieldRef, ...]
    reason: str


@dataclass(frozen=True)
class RateRow:
    rate: BankRate
    confirmed: bool


@dataclass(frozen=True)
class ClaimInput:
    ref: FieldRef
    value: str | None
    value_read: str | None
    source: str
    box: tuple[int, int, int, int] | None


@dataclass(frozen=True)
class ClaimRow:
    ref: FieldRef
    value: str | None
    value_read: str | None
    source: str
    box: tuple[int, int, int, int] | None
    status: Status | None  # None: no rule looks at this field
    rule_ids: tuple[str, ...]
    accepted_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ClockOutcome:
    result: ClockResult | None
    error_key: str | None = None
    error_params: dict[str, str] = field(default_factory=dict)
    rates_used: tuple[RateRow, ...] = ()
    rates_unconfirmed: bool = False


@dataclass(frozen=True)
class DossierModel:
    rows: tuple[ClaimRow, ...]
    unresolved: tuple[Finding, ...]
    confirmed: bool
    stamp_visible: bool
    clock: ClockOutcome | None
    assumptions: tuple[str, ...]


def field_statuses(findings: Iterable[Finding]) -> dict[FieldRef, Status]:
    """The worst status of the findings that name each field."""
    out: dict[FieldRef, Status] = {}
    for finding in findings:
        for ref in finding.fields:
            current = out.get(ref)
            if current is None or _RANK[finding.status] < _RANK[current]:
                out[ref] = finding.status
    return out


def is_accepted(finding: Finding, acceptances: Iterable[Acceptance]) -> bool:
    return any(
        a.rule_id == finding.rule_id and set(a.fields) == set(finding.fields) for a in acceptances
    )


def unresolved_blocking(
    findings: Iterable[Finding], acceptances: Sequence[Acceptance]
) -> list[Finding]:
    """Blocking findings that are failed or need review and are not accepted with a reason."""
    return [f for f in findings if f.blocks and not is_accepted(f, acceptances)]


def can_confirm(findings: Iterable[Finding], acceptances: Sequence[Acceptance]) -> bool:
    return not unresolved_blocking(findings, acceptances)


def stamp_visible(
    confirmed: bool, findings: Iterable[Finding], acceptances: Sequence[Acceptance]
) -> bool:
    """The stamp exists only for a confirmed case with nothing blocking (DESIGN.md 4.7)."""
    return confirmed and can_confirm(list(findings), acceptances)


def run_clock(inp: ClockInput, rows: Sequence[RateRow]) -> ClockOutcome:
    """Compute the clock, turning expected errors into message keys with ISO-date params."""
    try:
        result = compute(inp)
    except NoBankRateError as exc:
        return ClockOutcome(None, "clock.error.no_rate", {"needed_date": exc.needed_on.isoformat()})
    except MissingCreditDaysError:
        return ClockOutcome(None, "clock.error.credit_days")
    except PaymentTooLargeError as exc:
        params = {
            "paid_on_date": exc.paid_on.isoformat(),
            "amount_paise": str(exc.amount_paise),
            "balance_paise": str(exc.balance_paise),
        }
        return ClockOutcome(None, "clock.error.payment_too_large", params)
    used_dates = {s.rate_effective_from for s in result.steps if s.rate_effective_from is not None}
    used = tuple(r for r in rows if r.rate.effective_from in used_dates)
    return ClockOutcome(
        result=result,
        rates_used=used,
        rates_unconfirmed=any(not r.confirmed for r in used),
    )


def build_dossier(
    *,
    claims: Sequence[ClaimInput],
    findings: Sequence[Finding],
    acceptances: Sequence[Acceptance],
    confirmed: bool,
    clock: ClockOutcome | None,
    interest_base: str,
    has_payments: bool,
) -> DossierModel:
    statuses = field_statuses(findings)
    rows = tuple(
        ClaimRow(
            ref=c.ref,
            value=c.value,
            value_read=c.value_read,
            source=c.source,
            box=c.box,
            status=statuses.get(c.ref),
            rule_ids=tuple(sorted({f.rule_id for f in findings if c.ref in f.fields})),
            accepted_reasons=tuple(
                a.reason
                for a in acceptances
                if c.ref in a.fields
                and any(f.rule_id == a.rule_id and set(f.fields) == set(a.fields) for f in findings)
            ),
        )
        for c in claims
    )
    assumptions = ["assumption.registration", "assumption.acceptance"]
    if clock is not None and clock.result is not None:
        assumptions += [
            "assumption.rate_month_start",
            "assumption.partial_month",
            f"assumption.interest_base.{interest_base}",
        ]
        if has_payments:
            assumptions.append("assumption.part_payments")
        if clock.rates_unconfirmed:
            assumptions.append("assumption.bank_rate_unconfirmed")
    return DossierModel(
        rows=rows,
        unresolved=tuple(unresolved_blocking(findings, acceptances)),
        confirmed=confirmed,
        stamp_visible=stamp_visible(confirmed, findings, acceptances),
        clock=clock,
        assumptions=tuple(assumptions),
    )
