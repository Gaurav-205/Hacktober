"""A case as the rules and the evidence file see it, built from the database.

Pure decisions live in munim_core (verify, clock, dossier_model). This module only gathers the
inputs: claims as ClaimValues, acceptances that have not lapsed (D8: an acceptance is tied to
the versions of the claims it names), the clock inputs the person gave, and the Bank Rate rows.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from munim_core.clock import BankRate, ClockInput, Payment
from munim_core.dates import DateParseError, parse_date_dayfirst
from munim_core.dossier_model import (
    Acceptance,
    ClaimInput,
    ClockOutcome,
    DossierModel,
    RateRow,
    build_dossier,
    field_statuses,
    run_clock,
    unresolved_blocking,
)
from munim_core.money import MoneyParseError, parse_inr
from munim_core.verify.models import CaseState, ClaimValue, FieldRef, Finding, PaperState, Status
from munim_core.verify.registry import run_all
from munim_web.db import Database

__all__ = ["CaseSnapshot", "ClockView", "load_case", "ref_of"]


def ref_of(row: sqlite3.Row) -> FieldRef:
    index = int(row["line_index"])
    return FieldRef(str(row["kind"]), str(row["field"]), None if index < 0 else index)


def _box(row: sqlite3.Row) -> tuple[int, int, int, int] | None:
    values = (row["box_y1"], row["box_x1"], row["box_y2"], row["box_x2"])
    if any(v is None for v in values):
        return None
    y1, x1, y2, x2 = (int(v) for v in values)
    return (y1, x1, y2, x2)


def _parse_day(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return parse_date_dayfirst(text).value
    except DateParseError:
        return None


@dataclass(frozen=True)
class ClockView:
    """What the clock strip shows: an outcome, or the inputs that are missing (D18)."""

    outcome: ClockOutcome | None
    missing: tuple[str, ...]
    delivered: date | None
    delivered_from: str | None  # "case" (typed by the person), "received_date" or "challan_date"
    principal_paise: int | None
    as_on: date
    provisional: bool
    interest_off: bool


@dataclass
class CaseSnapshot:
    case: sqlite3.Row
    papers: list[sqlite3.Row]
    claims: list[sqlite3.Row]
    state: CaseState
    findings: list[Finding]
    acceptances: list[Acceptance]
    acceptance_rows: list[sqlite3.Row]
    clock: ClockView
    payments: list[sqlite3.Row]
    rates: list[RateRow]
    by_ref: dict[FieldRef, sqlite3.Row] = field(default_factory=dict)

    @property
    def unresolved(self) -> list[Finding]:
        return unresolved_blocking(self.findings, self.acceptances)

    @property
    def confirmed(self) -> bool:
        return self.case["confirmed_at"] is not None

    def statuses(self) -> dict[FieldRef, Status]:
        return field_statuses(self.findings)

    def findings_for(self, ref: FieldRef) -> list[Finding]:
        order = {Status.FAILED: 0, Status.NEEDS_REVIEW: 1, Status.PASSED: 2, Status.SKIPPED: 3}
        return sorted((f for f in self.findings if ref in f.fields), key=lambda f: order[f.status])

    def accepted(self, finding: Finding) -> bool:
        return any(
            a.rule_id == finding.rule_id and set(a.fields) == set(finding.fields)
            for a in self.acceptances
        )

    def dossier(self) -> DossierModel:
        claims = [
            ClaimInput(
                ref=ref_of(c),
                value=c["value_current"],
                value_read=c["value_read"],
                source=c["source"],
                box=_box(c),
            )
            for c in self.claims
        ]
        return build_dossier(
            claims=claims,
            findings=self.findings,
            acceptances=self.acceptances,
            confirmed=self.confirmed,
            clock=self.clock.outcome,
            interest_base=str(self.case["interest_base"]),
            has_payments=bool(self.payments),
        )

    def value(self, kind: str, name: str) -> str | None:
        row = self.by_ref.get(FieldRef(kind, name))
        return None if row is None else row["value_current"]

    def versions(self, refs: Sequence[FieldRef]) -> dict[str, int]:
        out = {}
        for ref in refs:
            row = self.by_ref.get(ref)
            out[_ref_key(ref)] = int(row["version"]) if row is not None else 0
        return out


def _ref_key(ref: FieldRef) -> str:
    return f"{ref.paper_kind}:{ref.field}:{'' if ref.index is None else ref.index}"


def _state(case: sqlite3.Row, claims: list[sqlite3.Row], as_on: date) -> CaseState:
    papers: dict[str, dict[str, Any]] = {}
    for c in claims:
        paper = papers.setdefault(c["kind"], {"fields": {}, "lines": {}})
        value = ClaimValue(
            raw=c["value_read"], text=c["value_current"], source=c["source"], flag=c["review_flag"]
        )
        if int(c["line_index"]) < 0:
            paper["fields"][c["field"]] = value
        else:
            paper["lines"].setdefault(int(c["line_index"]), {})[c["field"]] = value
    return CaseState(
        papers={
            kind: PaperState(
                kind=kind,
                fields=p["fields"],
                lines=tuple(p["lines"][i] for i in sorted(p["lines"])),
            )
            for kind, p in papers.items()
        },
        as_on=as_on,
        udyam_number=case["udyam_number"],
    )


def _acceptances(rows: list[sqlite3.Row], snapshot_versions: dict[str, int]) -> list[Acceptance]:
    """Acceptances whose claims have not changed since the person accepted them (D8)."""
    valid = []
    for row in rows:
        versions: dict[str, int] = json.loads(row["versions_json"])
        if any(snapshot_versions.get(k, 0) != v for k, v in versions.items()):
            continue
        fields = tuple(FieldRef(k, f, i) for k, f, i in json.loads(row["fields_json"]))
        valid.append(Acceptance(rule_id=row["rule_id"], fields=fields, reason=row["reason"]))
    return valid


def _clock(
    case: sqlite3.Row,
    *,
    values: dict[FieldRef, sqlite3.Row],
    rates: list[RateRow],
    payments: list[sqlite3.Row],
    as_on: date,
    confirmed: bool,
) -> ClockView:
    def claim(kind: str, name: str) -> str | None:
        row = values.get(FieldRef(kind, name))
        return None if row is None else row["value_current"]

    missing: list[str] = []
    delivered: date | None = None
    delivered_from: str | None = None
    if case["acceptance_date"]:
        delivered, delivered_from = date.fromisoformat(case["acceptance_date"]), "case"
    elif received := _parse_day(claim("challan", "received_date")):
        delivered, delivered_from = received, "received_date"
    elif challan := _parse_day(claim("challan", "challan_date")):
        delivered, delivered_from = challan, "challan_date"
    if case["objection_removed_on"]:
        delivered, delivered_from = date.fromisoformat(case["objection_removed_on"]), "case"
    if delivered is None:
        missing.append("acceptance_date")
    agreement = case["agreement"]
    if agreement is None:
        missing.append("agreement")
    elif agreement == "written" and case["credit_days"] is None:
        missing.append("credit_days")
    base = str(case["interest_base"])
    principal: int | None = None
    try:
        text = claim("invoice", base)
        principal = parse_inr(text) if text else None
    except MoneyParseError:
        principal = None
    if principal is None:
        missing.append(base)
    interest_off = case["enterprise_size"] == "medium"
    outcome = None
    if not missing and delivered is not None and principal is not None:
        inp = ClockInput(
            acceptance_date=delivered,
            agreement=_agreement(agreement),
            credit_days=case["credit_days"],
            principal_paise=principal,
            as_on=as_on,
            rates=tuple(r.rate for r in rates),
            payments=tuple(
                Payment(date.fromisoformat(p["paid_on"]), int(p["amount_paise"])) for p in payments
            ),
        )
        outcome = run_clock(inp, rates)
    return ClockView(
        outcome=outcome,
        missing=tuple(missing),
        delivered=delivered,
        delivered_from=delivered_from,
        principal_paise=principal,
        as_on=as_on,
        provisional=not confirmed,
        interest_off=interest_off,
    )


def _agreement(value: str | None) -> Literal["written", "none"]:
    return "written" if value == "written" else "none"


def load_case(db: Database, case_id: str, today: date) -> CaseSnapshot | None:
    case = db.case(case_id)
    if case is None:
        return None
    papers = db.papers(case_id)
    claims = db.claims_for_case(case_id)
    as_on = date.fromisoformat(case["as_on_date"]) if case["as_on_date"] else today
    state = _state(case, claims, as_on)
    findings = run_all(state, today)
    by_ref = {ref_of(c): c for c in claims}
    versions = {_ref_key(r): int(c["version"]) for r, c in by_ref.items()}
    acceptance_rows = db.acceptances(case_id)
    rates = [
        RateRow(
            BankRate(date.fromisoformat(r["effective_from"]), Decimal(r["percent"])),
            bool(r["confirmed"]),
        )
        for r in db.bank_rates()
    ]
    payments = db.payments(case_id)
    clock = _clock(
        case,
        values=by_ref,
        rates=rates,
        payments=payments,
        as_on=as_on,
        confirmed=case["confirmed_at"] is not None,
    )
    return CaseSnapshot(
        case=case,
        papers=papers,
        claims=claims,
        state=state,
        findings=findings,
        acceptances=_acceptances(acceptance_rows, versions),
        acceptance_rows=acceptance_rows,
        clock=clock,
        payments=payments,
        rates=rates,
        by_ref=by_ref,
    )


def ref_key(ref: FieldRef) -> str:
    return _ref_key(ref)
