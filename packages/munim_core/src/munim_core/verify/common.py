"""Helpers shared by the rule families: reading claims and building findings."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import Decimal

from munim_core.dates import DateParseError, ParsedDate, parse_date_dayfirst
from munim_core.money import (
    MoneyParseError,
    parse_inr,
    parse_quantity,
    parse_rate_paise,
    parse_signed_inr,
)
from munim_core.verify.catalog import RULES
from munim_core.verify.models import (
    CaseState,
    ClaimValue,
    FieldRef,
    Finding,
    PaperState,
    Severity,
    Status,
)

PAPER_KEYS = {
    "invoice": "paper.kind.invoice",
    "challan": "paper.kind.challan",
    "po": "paper.kind.po",
}
PAPER_ORDER = ("invoice", "challan", "po")


def finding(
    rule_id: str,
    status: Status,
    fields: Iterable[FieldRef],
    *,
    params: Mapping[str, str] | None = None,
    message_key: str | None = None,
    severity: Severity | None = None,
) -> Finding:
    """Build a finding. Passed and skipped findings use the generic check.* message keys."""
    spec = RULES[rule_id]
    if status is Status.PASSED:
        key = "check.passed"
    elif status is Status.SKIPPED:
        key = "check.skipped"
    else:
        key = message_key or f"rule.{rule_id}"
    return Finding(
        rule_id=rule_id,
        status=status,
        severity=severity or spec.severity,
        message_key=key,
        params=dict(params or {}),
        fields=tuple(fields),
        rule_version=spec.version,
    )


def text_of(claim: ClaimValue | None) -> str | None:
    """The current text of a claim, or None when it is absent or blank."""
    if claim is None or claim.text is None:
        return None
    stripped = claim.text.strip()
    return stripped or None


def field_text(paper: PaperState | None, name: str) -> str | None:
    if paper is None:
        return None
    return text_of(paper.fields.get(name))


def _try[T](parser: Callable[[str], T], text: str | None) -> T | None:
    if text is None:
        return None
    try:
        return parser(text)
    except (MoneyParseError, DateParseError):
        return None


def amount(text: str | None) -> int | None:
    return _try(parse_inr, text)


def signed_amount(text: str | None) -> int | None:
    return _try(parse_signed_inr, text)


def quantity(text: str | None) -> Decimal | None:
    return _try(parse_quantity, text)


def rate_paise(text: str | None) -> Decimal | None:
    return _try(parse_rate_paise, text)


def parsed_date(text: str | None) -> ParsedDate | None:
    return _try(parse_date_dayfirst, text)


def day(text: str | None) -> date | None:
    parsed = parsed_date(text)
    return parsed.value if parsed else None


def present_papers(state: CaseState) -> list[tuple[str, PaperState]]:
    """Papers in a stable order: invoice, challan, purchase order."""
    return [(kind, state.papers[kind]) for kind in PAPER_ORDER if kind in state.papers]
