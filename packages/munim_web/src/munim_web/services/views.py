"""Turn a case snapshot into what the templates show. Formatting only; decisions are in core."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from munim_core.verify.models import Finding, Status
from munim_web.services.case_service import CaseSnapshot, _box, ref_of
from munim_web.translate import Translator

YES_NO = {"yes": "value.yes", "no": "value.no", "unknown": "value.unknown"}
FLAG_FIELDS = ("receiver_stamp_present", "receiver_signature_present")


@dataclass
class Row:
    id: str
    field: str
    index: int | None
    label: str
    value: str | None
    value_read: str | None
    source: str
    status: str  # passed, failed, review, skipped, none, accepted
    messages: list[str]
    accept_rule: str | None
    accepted: list[str]
    repair_reason: str | None
    repair_outcome: str | None
    repair_via: str | None
    animate: bool
    version: int
    box: tuple[int, int, int, int] | None
    blocking: bool
    rereadable: bool
    display: str | None = None
    display_read: str | None = None
    gstin: bool = False

    @property
    def corrected(self) -> bool:
        return self.source in ("repair", "user") and self.value != self.value_read


@dataclass
class PaperView:
    row: sqlite3.Row
    rows: list[Row] = field(default_factory=list)


STATUS_NAME = {
    Status.PASSED: "passed",
    Status.FAILED: "failed",
    Status.NEEDS_REVIEW: "review",
    Status.SKIPPED: "skipped",
}


def _display(t: Translator, name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if name in FLAG_FIELDS:
        key = YES_NO.get(value.strip().casefold())
        return t(key) if key else value
    return value


def rows_for(snapshot: CaseSnapshot, paper_id: str, t: Translator) -> list[Row]:
    out: list[Row] = []
    for claim in snapshot.claims:
        if claim["paper_id"] != paper_id:
            continue
        ref = ref_of(claim)
        findings = snapshot.findings_for(ref)
        open_: list[Finding] = [
            f
            for f in findings
            if f.status in (Status.FAILED, Status.NEEDS_REVIEW) and not snapshot.accepted(f)
        ]
        accepted = [a.reason for a in snapshot.acceptances if ref in a.fields]
        if open_:
            status = STATUS_NAME[open_[0].status]
        elif any(f.status in (Status.FAILED, Status.NEEDS_REVIEW) for f in findings):
            status = "accepted"
        elif findings:
            status = STATUS_NAME[findings[0].status]
        else:
            status = "none"
        blocking_open = [f for f in open_ if f.blocks]
        label = t(f"field.{ref.field}")
        if ref.index is not None:
            label = f"{t('claims.line', n=ref.index + 1)}: {label}"
        outcome = claim["repair_outcome"]
        out.append(
            Row(
                id=claim["id"],
                field=ref.field,
                index=ref.index,
                label=label,
                value=claim["value_current"],
                value_read=claim["value_read"],
                source=claim["source"],
                status=status,
                messages=[t(f.message_key, dict(f.params)) for f in open_],
                accept_rule=(blocking_open or open_)[0].rule_id if open_ else None,
                accepted=accepted,
                repair_reason=t(claim["repair_reason"]) if claim["repair_reason"] else None,
                repair_outcome=outcome,
                repair_via=claim["repair_via"],
                animate=bool(claim["animate"]),
                version=int(claim["version"]),
                box=_box(claim),
                blocking=bool(blocking_open),
                rereadable=bool(open_)
                and _box(claim) is not None
                and int(claim["repair_attempts"]) < 2,
                display=_display(t, ref.field, claim["value_current"]),
                display_read=_display(t, ref.field, claim["value_read"]),
                gstin=ref.field.endswith("_gstin"),
            )
        )
    return out


def counts(rows: list[Row]) -> dict[str, int | str]:
    failed = sum(r.status == "failed" for r in rows)
    review = sum(r.status == "review" for r in rows)
    passed = sum(r.status == "passed" for r in rows)
    if failed:
        overall = "failed"
    elif review:
        overall = "review"
    elif passed:
        overall = "passed"
    else:
        overall = "none"
    return {
        "passed": passed,
        "open": failed + review,
        "failed": failed,
        "review": review,
        "total": len(rows),
        "overall": overall,
    }


def clock_context(snapshot: CaseSnapshot, t: Translator) -> dict[str, Any]:
    clock = snapshot.clock
    outcome = clock.outcome
    ctx: dict[str, Any] = {
        "clock": clock,
        "missing": ", ".join(t(f"clock.missing.{m}") for m in clock.missing),
        "result": outcome.result if outcome else None,
        "clock_error": t(outcome.error_key, outcome.error_params)
        if outcome and outcome.error_key
        else None,
        "unconfirmed": bool(outcome and outcome.rates_unconfirmed),
    }
    result = ctx["result"]
    if result is not None:
        case = snapshot.case
        if result.basis_key == "clock.basis.capped":
            ctx["basis"] = t(result.basis_key, entered=case["credit_days"])
        else:
            ctx["basis"] = t(result.basis_key, days=result.credit_days_used)
        rates = {
            (s.bank_rate_percent, s.rate_percent)
            for s in result.steps
            if s.bank_rate_percent is not None
        }
        ctx["rates"] = [t("clock.rate", bank_rate=str(b), rate=str(r)) for b, r in sorted(rates)]
    return ctx


def step_label(step: Any, t: Translator) -> str:
    kind = step.kind
    if kind == "partial":
        return t("working.step.partial", days=step.days, period_days=step.period_days)
    if kind == "payment":
        return t("working.step.payment", amount=t.money(step.payment_paise))
    if kind == "month":
        return t("working.step.month")
    return t("working.step.due")
