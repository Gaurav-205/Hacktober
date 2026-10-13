"""Builders for verification tests. All values are synthetic."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from munim_core.verify.models import CaseState, ClaimValue, Finding, PaperState, Status

# Synthetic, checksum-valid GSTINs: supplier in Uttar Pradesh (09), buyer in Maharashtra (27).
SUPPLIER_GSTIN = "09AAAPZ1234Z1ZN"
BUYER_GSTIN = "27AAAPZ5678Z1Z1"
TODAY = date(2026, 10, 13)


def claim(text: str | None, *, flag: str | None = None, source: str = "model") -> ClaimValue:
    return ClaimValue(raw=text, text=text, source=source, flag=flag)


def paper(
    kind: str, fields: Mapping[str, str | None], lines: Iterable[Mapping[str, str | None]] = ()
) -> PaperState:
    return PaperState(
        kind=kind,
        fields={k: claim(v) for k, v in fields.items()},
        lines=tuple({k: claim(v) for k, v in line.items()} for line in lines),
    )


def invoice(**overrides: str | None) -> dict[str, str | None]:
    """The demo invoice from docs/CONTENT.md section 3 (inter-state, IGST 18%)."""
    base: dict[str, str | None] = {
        "supplier_name": "Sample Fabricators Pvt Ltd",
        "supplier_gstin": SUPPLIER_GSTIN,
        "buyer_name": "Demo Textiles Ltd",
        "buyer_gstin": BUYER_GSTIN,
        "invoice_number": "SF/2025-26/0412",
        "invoice_date": "21/03/2026",
        "place_of_supply": "27-Maharashtra",
        "taxable_total": "4,23,729.00",
        "cgst": None,
        "sgst": None,
        "igst": "76,271.22",
        "round_off": "-0.22",
        "invoice_total": "5,00,000.00",
        "po_reference": "PO-2026-0117",
        "challan_reference": "CH-0412",
    }
    base.update(overrides)
    return base


def clean_invoice_lines() -> list[dict[str, str | None]]:
    return [
        {
            "description": "MS angle 40x40x5",
            "quantity": "1,200",
            "unit": "kg",
            "rate": "250.00",
            "amount": "3,00,000.00",
            "hsn_sac": "7216",
        },
        {
            "description": "MS flat 50x6",
            "quantity": "1",
            "unit": "lot",
            "rate": "1,23,729.00",
            "amount": "1,23,729.00",
            "hsn_sac": "7211",
        },
    ]


def challan(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        "supplier_name": "Sample Fabricators Private Limited",
        "supplier_gstin": SUPPLIER_GSTIN,
        "buyer_name": "Demo Textiles Limited",
        "buyer_gstin": BUYER_GSTIN,
        "challan_number": "CH-0412",
        "challan_date": "20/03/2026",
        "invoice_reference": "SF/2025-26/0412",
        "po_reference": "PO-2026-0117",
        "receiver_stamp_present": "yes",
        "receiver_signature_present": "unknown",
        "received_date": None,
    }
    base.update(overrides)
    return base


def challan_lines() -> list[dict[str, str | None]]:
    return [
        {"description": "M.S. Angle 40x40x5", "quantity": "1200", "unit": "kgs"},
        {"description": "MS Flat 50 x 6", "quantity": "1", "unit": "lot"},
    ]


def po(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        "buyer_name": "M/s Demo Textiles Ltd.",
        "buyer_gstin": BUYER_GSTIN,
        "po_number": "PO-2026-0117",
        "po_date": "02 Mar 2026",
        "supplier_name": "Sample Fabricators Pvt. Ltd.",
        "supplier_gstin": SUPPLIER_GSTIN,
        "credit_days": "30",
    }
    base.update(overrides)
    return base


def case(
    *,
    inv: Mapping[str, str | None] | None = None,
    inv_lines: Iterable[Mapping[str, str | None]] | None = None,
    ch: Mapping[str, str | None] | None = None,
    ch_lines: Iterable[Mapping[str, str | None]] | None = None,
    order: Mapping[str, str | None] | None = None,
    as_on: date | None = TODAY,
    udyam: str | None = None,
    extra: Mapping[str, str] = (),
) -> CaseState:
    papers: dict[str, PaperState] = {}
    if inv is not None:
        papers["invoice"] = paper(
            "invoice", inv, inv_lines if inv_lines is not None else clean_invoice_lines()
        )
    if ch is not None:
        papers["challan"] = paper(
            "challan", ch, ch_lines if ch_lines is not None else challan_lines()
        )
    if order is not None:
        papers["po"] = paper("po", order)
    return CaseState(papers=papers, as_on=as_on, udyam_number=udyam, extra=dict(extra))


def only(findings: Iterable[Finding], rule_id: str, field: str | None = None) -> list[Finding]:
    """Findings of one rule, optionally about one field name."""
    return [
        f
        for f in findings
        if f.rule_id == rule_id and (field is None or any(r.field == field for r in f.fields))
    ]


def statuses(findings: Iterable[Finding]) -> list[Status]:
    return [f.status for f in findings]
