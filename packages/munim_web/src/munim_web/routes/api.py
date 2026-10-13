"""The small JSON surface (docs/API.md "/api/v1"). Pure endpoints need no stored data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from munim_core.clock import BankRate, ClockError, ClockInput, Payment, compute
from munim_core.ids import check_gstin
from munim_core.verify.catalog import RULES
from munim_web.services.case_service import load_case, ref_of

router = APIRouter(prefix="/api/v1")


class GstinIn(BaseModel):
    gstin: str = Field(max_length=64)


class RateIn(BaseModel):
    effective_from: date
    percent: str


class PaymentIn(BaseModel):
    paid_on: date
    amount_paise: int = Field(gt=0)


class ClockIn(BaseModel):
    acceptance_date: date
    agreement: Literal["written", "none"]
    credit_days: int | None = Field(default=None, ge=0)
    principal_paise: int = Field(ge=0)
    as_on: date
    rates: list[RateIn]
    payments: list[PaymentIn] = []


def problem(status: int, title: str, key: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"type": "about:blank", "title": title, "status": status, "message_key": key},
    )


@router.post("/verify/gstin")
async def verify_gstin(body: GstinIn) -> dict[str, Any]:
    result = check_gstin(body.gstin)
    return {
        "valid": result.ok,
        "state_code": result.state_code,
        "pan": result.pan,
        "errors": list(result.errors),
    }


@router.post("/clock")
async def clock(body: ClockIn) -> dict[str, Any]:
    try:
        rates = tuple(BankRate(r.effective_from, Decimal(r.percent)) for r in body.rates)
    except InvalidOperation as exc:
        raise problem(422, "A rate is not a number", "rules.bank.err") from exc
    inp = ClockInput(
        acceptance_date=body.acceptance_date,
        agreement=body.agreement,
        credit_days=body.credit_days,
        principal_paise=body.principal_paise,
        as_on=body.as_on,
        rates=rates,
        payments=tuple(Payment(p.paid_on, p.amount_paise) for p in body.payments),
    )
    try:
        result = compute(inp)
    except ClockError as exc:
        raise problem(422, str(exc), "clock.error") from exc
    return {
        "due_date": result.due_date.isoformat(),
        "days_late": result.days_late,
        "interest_paise": result.interest_paise,
        "total_paise": result.total_paise,
        "steps": [
            {
                "kind": s.kind,
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "rate_percent": str(s.rate_percent),
                "opening_paise": s.opening_paise,
                "interest_paise": s.interest_paise,
                "closing_paise": s.closing_paise,
            }
            for s in result.steps
        ],
    }


@router.get("/rules")
async def rules() -> list[dict[str, str]]:
    return [
        {
            "id": spec.rule_id,
            "version": spec.version,
            "family": spec.family,
            "severity": str(spec.severity),
        }
        for spec in RULES.values()
    ]


@router.get("/cases/{case_id}/claims")
async def claims(request: Request, case_id: str) -> dict[str, list[dict[str, Any]]]:
    snap = load_case(request.app.state.db, case_id, date.today())
    if snap is None:
        raise problem(404, "No such case", "case.notfound")
    out: dict[str, list[dict[str, Any]]] = {}
    for c in snap.claims:
        ref = ref_of(c)
        box = [c["box_y1"], c["box_x1"], c["box_y2"], c["box_x2"]]
        out.setdefault(c["paper_id"], []).append(
            {
                "id": c["id"],
                "field": ref.field,
                "index": ref.index,
                "value_read": c["value_read"],
                "value_current": c["value_current"],
                "source": c["source"],
                "box": None if None in box else box,
                "findings": [
                    {"rule_id": f.rule_id, "status": str(f.status), "message_key": f.message_key}
                    for f in snap.findings_for(ref)
                ],
            }
        )
    return out
