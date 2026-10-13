"""MSME Samadhaan portal packet builder (pure core).

Builds pre-formatted, character-length-safe form data for filing a delayed payment
application on the MSME Samadhaan portal (msme.gov.in) under Section 18 of the
MSMED Act, 2006.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

from munim_core.money import Paise, format_inr

__all__ = [
    "SamadhaanField",
    "SamadhaanInput",
    "SamadhaanPacket",
    "build_samadhaan_packet",
]


@dataclass(frozen=True, slots=True)
class SamadhaanField:
    """A field to be filled in the MSME Samadhaan application portal."""

    key: str
    label_en: str
    value: str
    max_length: int | None
    is_truncated: bool
    field_group: str  # "supplier" | "buyer" | "order" | "invoice" | "claim"


@dataclass(frozen=True, slots=True)
class SamadhaanInput:
    """Inputs required to assemble the Samadhaan filing packet."""

    supplier_name: str
    supplier_udyam: str
    supplier_gstin: str
    supplier_state: str
    buyer_name: str
    buyer_gstin: str
    buyer_type: str
    po_number: str | None
    po_date: date | None
    invoice_number: str
    invoice_date: date
    invoice_amount_paise: Paise
    delivery_date: date | None
    due_date: date
    as_on_date: date
    principal_claimed_paise: Paise
    interest_claimed_paise: Paise


@dataclass(frozen=True, slots=True)
class SamadhaanPacket:
    """Complete application packet tailored for the MSME Samadhaan portal."""

    supplier_udyam: str
    supplier_name: str
    supplier_gstin: str
    supplier_state: str
    buyer_name: str
    buyer_gstin: str
    buyer_type: str
    invoice_number: str
    invoice_date: str
    invoice_amount_paise: Paise
    delivery_date: str
    due_date: str
    principal_claimed_paise: Paise
    interest_claimed_paise: Paise
    total_claimed_paise: Paise
    statement_of_claim: str
    fields: tuple[SamadhaanField, ...]
    csv_export: str


def _safe_str(val: str, max_len: int | None = None) -> tuple[str, bool]:
    s = val.strip()
    if max_len is not None and len(s) > max_len:
        return s[:max_len], True
    return s, False


def _make_field(
    key: str,
    label_en: str,
    val: str,
    max_len: int | None,
    group: str,
) -> SamadhaanField:
    safe_val, truncated = _safe_str(val, max_len)
    return SamadhaanField(
        key=key,
        label_en=label_en,
        value=safe_val,
        max_length=max_len,
        is_truncated=truncated,
        field_group=group,
    )


def build_samadhaan_packet(inp: SamadhaanInput) -> SamadhaanPacket:
    """Assemble a Samadhaan application packet with exact field constraints."""
    total_claimed = inp.principal_claimed_paise + inp.interest_claimed_paise
    principal_fmt = format_inr(inp.principal_claimed_paise)
    interest_fmt = format_inr(inp.interest_claimed_paise)
    total_fmt = format_inr(total_claimed)

    po_num_str = inp.po_number or "N/A"
    po_dt_str = inp.po_date.isoformat() if inp.po_date else "N/A"
    inv_dt_str = inp.invoice_date.isoformat()
    deliv_dt_str = inp.delivery_date.isoformat() if inp.delivery_date else "N/A"
    due_dt_str = inp.due_date.isoformat()
    as_on_str = inp.as_on_date.isoformat()

    # Statement of claim (portal maximum 1000 characters)
    statement_raw = (
        f"Application under Section 18 of the MSMED Act, 2006 for delayed payment. "
        f"Supplier ({inp.supplier_udyam}) supplied under Invoice {inp.invoice_number} "
        f"dated {inv_dt_str} (PO: {po_num_str}). Delivery accepted on {deliv_dt_str}. "
        f"Statutory payment due date was {due_dt_str}. "
        f"Buyer has failed to clear payment as on {as_on_str}. "
        f"Principal outstanding: {principal_fmt}. "
        f"Compounded monthly interest at 3x Bank Rate under Section 16: {interest_fmt}. "
        f"Total amount claimed: {total_fmt}."
    )

    statement, _ = _safe_str(statement_raw, 1000)

    fields_list = [
        _make_field(
            "supplier_udyam", "Supplier Udyam Registration", inp.supplier_udyam, 25, "supplier"
        ),
        _make_field("supplier_name", "Supplier Name", inp.supplier_name, 100, "supplier"),
        _make_field("supplier_gstin", "Supplier GSTIN", inp.supplier_gstin, 15, "supplier"),
        _make_field("supplier_state", "Supplier State", inp.supplier_state, 50, "supplier"),
        _make_field("buyer_name", "Buyer Name", inp.buyer_name, 100, "buyer"),
        _make_field("buyer_gstin", "Buyer GSTIN", inp.buyer_gstin, 15, "buyer"),
        _make_field("buyer_type", "Buyer Category", inp.buyer_type, 50, "buyer"),
        _make_field("po_number", "Purchase Order Number", po_num_str, 50, "order"),
        _make_field("po_date", "Purchase Order Date", po_dt_str, 10, "order"),
        _make_field("invoice_number", "Invoice Number", inp.invoice_number, 50, "invoice"),
        _make_field("invoice_date", "Invoice Date", inv_dt_str, 10, "invoice"),
        _make_field("invoice_amount", "Invoice Amount (₹)", principal_fmt, 30, "invoice"),
        _make_field("delivery_date", "Delivery / Challan Date", deliv_dt_str, 10, "invoice"),
        _make_field("due_date", "Payment Due Date", due_dt_str, 10, "claim"),
        _make_field("principal_claimed", "Principal Claimed (₹)", principal_fmt, 30, "claim"),
        _make_field("interest_claimed", "Interest Claimed (₹)", interest_fmt, 30, "claim"),
        _make_field("total_claimed", "Total Claimed (₹)", total_fmt, 30, "claim"),
        _make_field("statement_of_claim", "Statement of Claim", statement, 1000, "claim"),
    ]

    # Generate CSV export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Portal Field", "Field Value", "Group"])
    for f in fields_list:
        writer.writerow([f.label_en, f.value, f.field_group])
    csv_str = output.getvalue()

    return SamadhaanPacket(
        supplier_udyam=inp.supplier_udyam,
        supplier_name=inp.supplier_name,
        supplier_gstin=inp.supplier_gstin,
        supplier_state=inp.supplier_state,
        buyer_name=inp.buyer_name,
        buyer_gstin=inp.buyer_gstin,
        buyer_type=inp.buyer_type,
        invoice_number=inp.invoice_number,
        invoice_date=inv_dt_str,
        invoice_amount_paise=inp.invoice_amount_paise,
        delivery_date=deliv_dt_str,
        due_date=due_dt_str,
        principal_claimed_paise=inp.principal_claimed_paise,
        interest_claimed_paise=inp.interest_claimed_paise,
        total_claimed_paise=total_claimed,
        statement_of_claim=statement,
        fields=tuple(fields_list),
        csv_export=csv_str,
    )
