"""Invoice rules (docs/DOMAIN_RULES.md 3.2): arithmetic, tax split, slabs, number and date."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from munim_core.ids import check_gstin
from munim_core.money import round_half_up
from munim_core.states import state_code_from_text
from munim_core.verify.common import (
    amount,
    day,
    field_text,
    finding,
    quantity,
    rate_paise,
    signed_amount,
    text_of,
)
from munim_core.verify.models import CaseState, FieldRef, Finding, PaperState, Status

GST_START = date(2017, 7, 1)
GST2_START = date(2025, 9, 22)
SLABS_BEFORE = tuple(Decimal(s) for s in ("0", "0.25", "3", "5", "12", "18", "28"))
SLABS_FROM_GST2 = tuple(Decimal(s) for s in ("0", "0.25", "3", "5", "18", "40"))
LINE_TOLERANCE_PAISE = 1
NO_ROUND_OFF_TOLERANCE_PAISE = 100
INVOICE_NUMBER = re.compile(r"^[A-Za-z0-9/-]{1,16}$")
TAX_FIELDS = ("cgst", "sgst", "igst")


def ref(name: str, index: int | None = None) -> FieldRef:
    return FieldRef("invoice", name, index)


def _line_amounts(inv: PaperState) -> list[int | None]:
    return [amount(text_of(line.get("amount"))) for line in inv.lines]


def line_amount(inv: PaperState) -> list[Finding]:
    out: list[Finding] = []
    for index, line in enumerate(inv.lines):
        refs = (ref("quantity", index), ref("rate", index), ref("amount", index))
        qty = quantity(text_of(line.get("quantity")))
        rate = rate_paise(text_of(line.get("rate")))
        printed = amount(text_of(line.get("amount")))
        if qty is None or rate is None or printed is None:
            out.append(finding("INV-LINE-AMOUNT", Status.SKIPPED, refs))
            continue
        computed = round_half_up(qty * rate)
        if abs(computed - printed) <= LINE_TOLERANCE_PAISE:
            out.append(finding("INV-LINE-AMOUNT", Status.PASSED, refs))
        else:
            params = {
                "n": str(index + 1),
                "computed_paise": str(computed),
                "printed_paise": str(printed),
            }
            out.append(finding("INV-LINE-AMOUNT", Status.FAILED, refs, params=params))
    return out


def taxable_sum(inv: PaperState) -> Finding:
    refs = (ref("taxable_total"), *(ref("amount", i) for i in range(len(inv.lines))))
    amounts = _line_amounts(inv)
    printed = amount(field_text(inv, "taxable_total"))
    if not amounts or any(a is None for a in amounts) or printed is None:
        return finding("INV-TAXABLE-SUM", Status.SKIPPED, refs)
    computed = sum(a for a in amounts if a is not None)
    if computed == printed:
        return finding("INV-TAXABLE-SUM", Status.PASSED, refs)
    params = {"computed_paise": str(computed), "printed_paise": str(printed)}
    return finding("INV-TAXABLE-SUM", Status.FAILED, refs, params=params)


def _taxes(inv: PaperState) -> tuple[tuple[int, int, int] | None, bool]:
    """((cgst, sgst, igst) in paise, whether any tax line is printed).

    An absent tax line counts as 0. If a printed tax line cannot be read the values are None,
    so no rule computes with a guess.
    """
    values: list[int] = []
    present = False
    for name in TAX_FIELDS:
        text = field_text(inv, name)
        if text is None:
            values.append(0)
            continue
        parsed = amount(text)
        if parsed is None:
            return None, True
        present = True
        values.append(parsed)
    return (values[0], values[1], values[2]), present


def tax_split(inv: PaperState) -> Finding:
    refs = (
        ref("supplier_gstin"),
        ref("buyer_gstin"),
        ref("place_of_supply"),
        *(ref(n) for n in TAX_FIELDS),
    )
    supplier = check_gstin(field_text(inv, "supplier_gstin") or "").state_code
    buyer = check_gstin(field_text(inv, "buyer_gstin") or "").state_code
    taxes, printed = _taxes(inv)
    if supplier is None or buyer is None or taxes is None or not printed:
        return finding("INV-TAX-SPLIT", Status.SKIPPED, refs)
    pos_text = field_text(inv, "place_of_supply")
    pos = state_code_from_text(pos_text) if pos_text else None
    destination = pos or buyer
    same = supplier == destination
    params = {
        "same_or_different_key": "term.same_state" if same else "term.different_states",
        "expected_key": "term.cgst_sgst" if same else "term.igst",
    }
    if pos is not None and pos != buyer:
        return finding(
            "INV-TAX-SPLIT",
            Status.NEEDS_REVIEW,
            refs,
            params={**params, "printed": pos_text or ""},
            message_key="rule.INV-TAX-SPLIT.place_of_supply",
        )
    cgst, sgst, igst = taxes
    ok = (igst == 0 and cgst == sgst) if same else (cgst == 0 and sgst == 0)
    return finding("INV-TAX-SPLIT", Status.PASSED if ok else Status.FAILED, refs, params=params)


def tax_rate(inv: PaperState) -> Finding:
    refs = (ref("taxable_total"), *(ref(n) for n in TAX_FIELDS), ref("invoice_date"))
    taxable = amount(field_text(inv, "taxable_total"))
    taxes, printed = _taxes(inv)
    invoice_date = day(field_text(inv, "invoice_date"))
    if not taxable or taxes is None or not printed or invoice_date is None:
        return finding("INV-TAX-RATE", Status.SKIPPED, refs)
    tax = sum(taxes)
    slabs = SLABS_FROM_GST2 if invoice_date >= GST2_START else SLABS_BEFORE
    tolerance = max(1, len(inv.lines)) * LINE_TOLERANCE_PAISE
    for slab in slabs:
        if abs(tax - round_half_up(Decimal(taxable) * slab / 100)) <= tolerance:
            return finding("INV-TAX-RATE", Status.PASSED, refs)
    effective = (Decimal(tax) * 100 / Decimal(taxable)).quantize(Decimal("0.01"))
    params = {"rate_percent": str(effective), "read_date": invoice_date.isoformat()}
    return finding("INV-TAX-RATE", Status.NEEDS_REVIEW, refs, params=params)


def total(inv: PaperState) -> Finding:
    refs = (
        ref("taxable_total"),
        *(ref(n) for n in TAX_FIELDS),
        ref("round_off"),
        ref("invoice_total"),
    )
    printed = amount(field_text(inv, "invoice_total"))
    taxable = amount(field_text(inv, "taxable_total"))
    taxes, _ = _taxes(inv)
    round_off_text = field_text(inv, "round_off")
    round_off = signed_amount(round_off_text) if round_off_text is not None else 0
    if printed is None or taxable is None or taxes is None or round_off is None:
        return finding("INV-TOTAL", Status.SKIPPED, refs)
    computed = taxable + sum(taxes) + round_off
    if round_off_text is not None:
        ok = abs(computed - printed) <= LINE_TOLERANCE_PAISE and abs(round_off) < 100
    else:
        ok = abs(computed - printed) <= NO_ROUND_OFF_TOLERANCE_PAISE
    if ok:
        return finding("INV-TOTAL", Status.PASSED, refs)
    params = {"computed_paise": str(computed), "printed_paise": str(printed)}
    return finding("INV-TOTAL", Status.FAILED, refs, params=params)


def number_format(inv: PaperState) -> Finding:
    text = field_text(inv, "invoice_number")
    refs = (ref("invoice_number"),)
    if text is None:
        return finding("INV-NUMBER-FORMAT", Status.SKIPPED, refs)
    ok = bool(INVOICE_NUMBER.match(text))
    params = {} if ok else {"printed": text}
    return finding("INV-NUMBER-FORMAT", Status.PASSED if ok else Status.FAILED, refs, params=params)


def date_sane(inv: PaperState, today: date) -> Finding:
    text = field_text(inv, "invoice_date")
    refs = (ref("invoice_date"),)
    value = day(text)
    if text is None or value is None:
        return finding("INV-DATE-SANE", Status.SKIPPED, refs)
    if GST_START <= value <= today:
        return finding("INV-DATE-SANE", Status.PASSED, refs)
    params = {"printed": text, "read_date": value.isoformat()}
    return finding("INV-DATE-SANE", Status.FAILED, refs, params=params)


def check(state: CaseState, today: date) -> list[Finding]:
    inv = state.papers.get("invoice")
    if inv is None:
        return []
    return [
        *line_amount(inv),
        taxable_sum(inv),
        tax_split(inv),
        tax_rate(inv),
        total(inv),
        number_format(inv),
        date_sane(inv, today),
    ]
