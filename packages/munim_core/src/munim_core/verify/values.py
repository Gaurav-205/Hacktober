"""VALUE-FORMAT: amounts, dates and quantities must be readable as numbers and dates.

An unreadable value cannot be checked by any arithmetic or date rule, so it is reported here
instead of silently turning those rules into "skipped". Values that feed the invoice
arithmetic, the cross-paper quantities or the payment clock are blocking.
"""

from __future__ import annotations

from collections.abc import Callable

from munim_core.verify.common import (
    amount,
    finding,
    parsed_date,
    present_papers,
    quantity,
    rate_paise,
    signed_amount,
    text_of,
)
from munim_core.verify.models import CaseState, ClaimValue, FieldRef, Finding, Severity, Status

Reader = Callable[[str | None], object]
# (field, reader, message suffix, severity) per paper kind.
FIELD_KINDS: dict[str, tuple[tuple[str, Reader, str, Severity], ...]] = {
    "invoice": (
        ("taxable_total", amount, "amount", Severity.BLOCKING),
        ("cgst", amount, "amount", Severity.BLOCKING),
        ("sgst", amount, "amount", Severity.BLOCKING),
        ("igst", amount, "amount", Severity.BLOCKING),
        ("round_off", signed_amount, "amount", Severity.BLOCKING),
        ("invoice_total", amount, "amount", Severity.BLOCKING),
        ("invoice_date", parsed_date, "date", Severity.BLOCKING),
    ),
    "challan": (
        ("challan_date", parsed_date, "date", Severity.BLOCKING),
        ("received_date", parsed_date, "date", Severity.BLOCKING),
    ),
    "po": (
        ("po_date", parsed_date, "date", Severity.WARNING),
        ("delivery_date", parsed_date, "date", Severity.WARNING),
        (
            "credit_days",
            lambda t: int(t) if t and t.strip().isdigit() else None,
            "number",
            Severity.WARNING,
        ),
    ),
}
LINE_KINDS: dict[str, tuple[tuple[str, Reader, str, Severity], ...]] = {
    "invoice": (
        ("quantity", quantity, "quantity", Severity.BLOCKING),
        ("rate", rate_paise, "amount", Severity.BLOCKING),
        ("amount", amount, "amount", Severity.BLOCKING),
    ),
    "challan": (("quantity", quantity, "quantity", Severity.BLOCKING),),
    "po": (
        ("quantity", quantity, "quantity", Severity.WARNING),
        ("rate", rate_paise, "amount", Severity.WARNING),
    ),
}


def _one(
    ref: FieldRef, claim: ClaimValue, read: Reader, suffix: str, severity: Severity
) -> Finding | None:
    text = text_of(claim)
    if text is None:
        return None
    if read(text) is None:
        return finding(
            "VALUE-FORMAT",
            Status.FAILED,
            (ref,),
            params={"printed": text},
            message_key=f"rule.VALUE-FORMAT.{suffix}",
            severity=severity,
        )
    return finding("VALUE-FORMAT", Status.PASSED, (ref,), severity=severity)


def _runaway(ref: FieldRef) -> Finding:
    """The model wrote an over-long value that was dropped (AI_SPEC 6): someone must look."""
    return finding(
        "VALUE-FORMAT",
        Status.NEEDS_REVIEW,
        (ref,),
        message_key="rule.VALUE-FORMAT.runaway",
        severity=Severity.WARNING,
    )


def check(state: CaseState) -> list[Finding]:
    out: list[Finding] = []
    for kind, paper in present_papers(state):
        out += [_runaway(FieldRef(kind, n)) for n, c in paper.fields.items() if c.flag == "runaway"]
        for index, line in enumerate(paper.lines):
            out += [
                _runaway(FieldRef(kind, n, index)) for n, c in line.items() if c.flag == "runaway"
            ]
        for name, read, suffix, severity in FIELD_KINDS[kind]:
            if name in paper.fields:
                result = _one(FieldRef(kind, name), paper.fields[name], read, suffix, severity)
                if result:
                    out.append(result)
        for index, line in enumerate(paper.lines):
            for name, read, suffix, severity in LINE_KINDS[kind]:
                if name in line:
                    result = _one(FieldRef(kind, name, index), line[name], read, suffix, severity)
                    if result:
                        out.append(result)
    return out
