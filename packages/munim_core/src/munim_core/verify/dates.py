"""DATE-AMBIGUOUS (docs/DOMAIN_RULES.md 3.2): a numeric date with two readings needs a person."""

from __future__ import annotations

from munim_core.verify.common import field_text, finding, parsed_date, present_papers
from munim_core.verify.models import CaseState, FieldRef, Finding, Severity, Status

DATE_FIELDS = {
    "invoice": ("invoice_date",),
    "challan": ("challan_date", "received_date"),
    "po": ("po_date", "delivery_date"),
}
# These dates set the acceptance date, and so the amount owed.
CLOCK_DATES = frozenset({("challan", "challan_date"), ("challan", "received_date")})


def check(state: CaseState) -> list[Finding]:
    out: list[Finding] = []
    for kind, paper in present_papers(state):
        for name in DATE_FIELDS[kind]:
            if name not in paper.fields:
                continue
            ref = (FieldRef(kind, name),)
            severity = Severity.BLOCKING if (kind, name) in CLOCK_DATES else Severity.WARNING
            text = field_text(paper, name)
            parsed = parsed_date(text)
            if text is None or parsed is None:
                out.append(finding("DATE-AMBIGUOUS", Status.SKIPPED, ref, severity=severity))
            elif parsed.ambiguous and parsed.alt is not None:
                params = {
                    "printed": text,
                    "a_date": parsed.value.isoformat(),
                    "b_date": parsed.alt.isoformat(),
                }
                out.append(
                    finding(
                        "DATE-AMBIGUOUS", Status.NEEDS_REVIEW, ref, params=params, severity=severity
                    )
                )
            else:
                out.append(finding("DATE-AMBIGUOUS", Status.PASSED, ref, severity=severity))
    return out
