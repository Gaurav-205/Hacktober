"""Cross-paper rules X-* (docs/DOMAIN_RULES.md 3.3). The model never compares papers; code does."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal

from rapidfuzz import fuzz

from munim_core.ids import normalise_gstin
from munim_core.verify.common import (
    PAPER_KEYS,
    day,
    field_text,
    finding,
    present_papers,
    quantity,
    text_of,
)
from munim_core.verify.models import (
    CaseState,
    ClaimValue,
    FieldRef,
    Finding,
    PaperState,
    Severity,
    Status,
)

NAME_THRESHOLD = 80
LINE_THRESHOLD = 70
CHALLAN_AFTER_INVOICE_DAYS = 30
_NAME_NOISE = re.compile(r"\b(?:pvt|ltd|limited|private|ms)\b")
_UNITS = {
    "kg": ("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"),
    "g": ("g", "gm", "gms", "gram", "grams", "grm"),
    "t": ("t", "mt", "ton", "tons", "tonne", "tonnes"),
    "l": ("l", "ltr", "ltrs", "litre", "litres", "liter", "liters"),
    "ml": ("ml",),
    "m": ("m", "mtr", "mtrs", "metre", "metres", "meter", "meters"),
    "nos": ("nos", "no", "pcs", "pc", "piece", "pieces", "unit", "units"),
}
_UNIT_OF = {alias: unit for unit, aliases in _UNITS.items() for alias in aliases}
# Factors into a base unit: mass in grams, volume in millilitres.
_BASE = {
    "g": ("mass", 1),
    "kg": ("mass", 1000),
    "t": ("mass", 1_000_000),
    "ml": ("vol", 1),
    "l": ("vol", 1000),
}


# ---------------------------------------------------------------- GSTINs across papers


def _same_gstin(state: CaseState, rule_id: str, name: str) -> Finding:
    values: list[tuple[str, str]] = []
    refs: list[FieldRef] = []
    for kind, paper in present_papers(state):
        if name in paper.fields:
            refs.append(FieldRef(kind, name))
        text = field_text(paper, name)
        if text is not None:
            values.append((kind, normalise_gstin(text)))
    if len(values) < 2:
        return finding(rule_id, Status.SKIPPED, refs)
    first_kind, first = values[0]
    for kind, value in values[1:]:
        if value != first:
            params = {
                "a": first,
                "a_paper_key": PAPER_KEYS[first_kind],
                "b": value,
                "b_paper_key": PAPER_KEYS[kind],
            }
            return finding(rule_id, Status.FAILED, refs, params=params)
    return finding(rule_id, Status.PASSED, refs)


# ---------------------------------------------------------------- names


def normalise_name(name: str) -> str:
    """Lowercase, drop punctuation, and drop pvt, ltd, limited, private and m/s."""
    text = name.lower().replace("m/s", " ms ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = _NAME_NOISE.sub(" ", text)
    return " ".join(text.split())


def _similar_names(state: CaseState, role: str) -> Finding:
    name = f"{role}_name"
    role_key = f"term.{role}"
    values = [(k, t) for k, p in present_papers(state) if (t := field_text(p, name))]
    refs = [FieldRef(k, name) for k, p in present_papers(state) if name in p.fields]
    if len(values) < 2:
        return finding("X-NAME-SIMILAR", Status.SKIPPED, refs, params={"role_key": role_key})
    # The lowest-scoring pair; min() keeps the first pair on a tie, in paper order.
    score, (a_kind, a_text), (b_kind, b_text) = min(
        (
            (fuzz.token_set_ratio(normalise_name(a[1]), normalise_name(b[1])), a, b)
            for i, a in enumerate(values)
            for b in values[i + 1 :]
        ),
        key=lambda pair: pair[0],
    )
    if score >= NAME_THRESHOLD:
        return finding("X-NAME-SIMILAR", Status.PASSED, refs, params={"role_key": role_key})
    params = {
        "role_key": role_key,
        "a": a_text,
        "a_paper_key": PAPER_KEYS[a_kind],
        "b": b_text,
        "b_paper_key": PAPER_KEYS[b_kind],
    }
    return finding("X-NAME-SIMILAR", Status.NEEDS_REVIEW, refs, params=params)


# ---------------------------------------------------------------- references


def normalise_reference(text: str) -> str:
    """Upper-case, split on / - space and dots, drop leading zeros of number groups.

    Groups are joined with "-", so "1/02" and "12" stay different references.
    """
    parts = [p for p in re.split(r"[\s/\-.]+", text.upper()) if p]
    return "-".join(p.lstrip("0") or "0" if p.isdigit() else p for p in parts)


def _invoice_ref(state: CaseState) -> Finding:
    refs = (FieldRef("challan", "invoice_reference"), FieldRef("invoice", "invoice_number"))
    quoted = field_text(state.papers.get("challan"), "invoice_reference")
    number = field_text(state.papers.get("invoice"), "invoice_number")
    if quoted is None or number is None:
        return finding("X-INVOICE-REF", Status.SKIPPED, refs)
    if normalise_reference(quoted) == normalise_reference(number):
        return finding("X-INVOICE-REF", Status.PASSED, refs)
    params = {"on_challan": quoted, "on_invoice": number}
    return finding("X-INVOICE-REF", Status.FAILED, refs, params=params)


def _po_refs(state: CaseState) -> list[Finding]:
    po_number = field_text(state.papers.get("po"), "po_number")
    out: list[Finding] = []
    for kind in ("invoice", "challan"):
        paper = state.papers.get(kind)
        if paper is None:
            continue
        refs = (FieldRef(kind, "po_reference"), FieldRef("po", "po_number"))
        quoted = field_text(paper, "po_reference")
        base = {"paper_key": PAPER_KEYS[kind]}
        if quoted is None or po_number is None:
            out.append(finding("X-PO-REF", Status.SKIPPED, refs, params=base))
        elif normalise_reference(quoted) == normalise_reference(po_number):
            out.append(finding("X-PO-REF", Status.PASSED, refs, params=base))
        else:
            params = {**base, "on_paper": quoted, "on_po": po_number}
            out.append(finding("X-PO-REF", Status.FAILED, refs, params=params))
    return out


# ---------------------------------------------------------------- quantities


def normalise_description(text: str) -> str:
    text = text.lower().replace(".", "")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", text)
    return " ".join(text.split())


def _unit(text: str | None) -> str | None:
    if text is None:
        return None
    word = re.sub(r"[^a-z]", "", text.lower())
    return _UNIT_OF.get(word, word or None)


def _comparable(qty: Decimal, unit: str | None, other_unit: str | None) -> tuple[Decimal, bool]:
    """Convert qty into the other line's unit. Returns (value, convertible)."""
    if unit is None or other_unit is None or unit == other_unit:
        return qty, True
    a, b = _BASE.get(unit), _BASE.get(other_unit)
    if a is None or b is None or a[0] != b[0]:
        return qty, False
    return qty * a[1] / b[1], True


def _printed_qty(line: dict[str, str | None]) -> str:
    return " ".join(p for p in (line.get("quantity"), line.get("unit")) if p)


def _quantities(state: CaseState) -> list[Finding]:
    inv, ch = state.papers.get("invoice"), state.papers.get("challan")
    if inv is None or ch is None or not inv.lines or not ch.lines:
        refs = [FieldRef(k, "quantity") for k in ("invoice", "challan") if k in state.papers]
        return [finding("X-QTY", Status.SKIPPED, refs)]
    challan_lines = [_texts(line) for line in ch.lines]
    out: list[Finding] = []
    for i, raw in enumerate(inv.lines):
        line = _texts(raw)
        description = line.get("description")
        inv_qty = quantity(line.get("quantity"))
        if description is None or inv_qty is None:
            out.append(finding("X-QTY", Status.SKIPPED, (FieldRef("invoice", "quantity", i),)))
            continue
        match = _best_line(description, challan_lines)
        if match is None:
            out.append(
                finding(
                    "X-QTY",
                    Status.NEEDS_REVIEW,
                    (FieldRef("invoice", "description", i), FieldRef("invoice", "quantity", i)),
                    params={"item": description},
                    message_key="rule.X-QTY.unmatched",
                )
            )
            continue
        j, other = match
        pair = (FieldRef("invoice", "quantity", i), FieldRef("challan", "quantity", j))
        ch_qty = quantity(other.get("quantity"))
        if ch_qty is None:
            out.append(finding("X-QTY", Status.SKIPPED, pair))
            continue
        converted, convertible = _comparable(
            ch_qty, _unit(other.get("unit")), _unit(line.get("unit"))
        )
        params = {
            "item": description,
            "challan_qty": _printed_qty(other),
            "invoice_qty": _printed_qty(line),
        }
        if not convertible:
            out.append(
                finding(
                    "X-QTY", Status.NEEDS_REVIEW, pair, params=params, message_key="rule.X-QTY.unit"
                )
            )
        elif converted == inv_qty:
            out.append(finding("X-QTY", Status.PASSED, pair))
        else:
            out.append(finding("X-QTY", Status.FAILED, pair, params=params))
    return out


def _texts(line: Mapping[str, ClaimValue]) -> dict[str, str | None]:
    return {name: text_of(claim) for name, claim in line.items()}


def _best_line(
    description: str, lines: list[dict[str, str | None]]
) -> tuple[int, dict[str, str | None]] | None:
    target = normalise_description(description)
    best: tuple[float, int] | None = None
    for j, line in enumerate(lines):
        other = line.get("description")
        if other is None:
            continue
        score = fuzz.token_set_ratio(target, normalise_description(other))
        if best is None or score > best[0]:
            best = (score, j)
    if best is None or best[0] < LINE_THRESHOLD:
        return None
    return best[1], lines[best[1]]


# ---------------------------------------------------------------- dates and acknowledgement


def _acceptance(ch: PaperState | None) -> tuple[date | None, FieldRef]:
    received = day(field_text(ch, "received_date"))
    if received is not None:
        return received, FieldRef("challan", "received_date")
    return day(field_text(ch, "challan_date")), FieldRef("challan", "challan_date")


def _date_order(state: CaseState) -> list[Finding]:
    inv, ch, order = (state.papers.get(k) for k in ("invoice", "challan", "po"))
    po_date = day(field_text(order, "po_date"))
    challan_date = day(field_text(ch, "challan_date"))
    invoice_date = day(field_text(inv, "invoice_date"))
    out: list[Finding] = []

    refs = (FieldRef("po", "po_date"), FieldRef("challan", "challan_date"))
    if po_date is None or challan_date is None:
        out.append(finding("X-DATE-ORDER", Status.SKIPPED, refs))
    elif po_date <= challan_date:
        out.append(finding("X-DATE-ORDER", Status.PASSED, refs))
    else:
        params = {"po_date": po_date.isoformat(), "challan_date": challan_date.isoformat()}
        out.append(
            finding(
                "X-DATE-ORDER",
                Status.FAILED,
                refs,
                params=params,
                message_key="rule.X-DATE-ORDER.po_challan",
            )
        )

    refs = (FieldRef("challan", "challan_date"), FieldRef("invoice", "invoice_date"))
    if challan_date is None or invoice_date is None:
        out.append(finding("X-DATE-ORDER", Status.SKIPPED, refs))
    elif challan_date <= invoice_date + timedelta(days=CHALLAN_AFTER_INVOICE_DAYS):
        out.append(finding("X-DATE-ORDER", Status.PASSED, refs))
    else:
        params = {
            "challan_date": challan_date.isoformat(),
            "invoice_date": invoice_date.isoformat(),
        }
        out.append(
            finding(
                "X-DATE-ORDER",
                Status.FAILED,
                refs,
                params=params,
                message_key="rule.X-DATE-ORDER.invoice_challan",
            )
        )

    acceptance, acceptance_ref = _acceptance(ch)
    if "acceptance_date" in state.extra and state.extra["acceptance_date"]:
        try:
            acceptance = date.fromisoformat(state.extra["acceptance_date"])
            acceptance_ref = FieldRef("case", "acceptance_date")
        except ValueError:
            pass
    refs = (acceptance_ref, FieldRef("case", "as_on_date"))
    if acceptance is None or state.as_on is None:
        out.append(finding("X-DATE-ORDER", Status.SKIPPED, refs))
    elif acceptance <= state.as_on:
        out.append(finding("X-DATE-ORDER", Status.PASSED, refs))
    else:
        params = {"acceptance_date": acceptance.isoformat(), "as_on_date": state.as_on.isoformat()}
        out.append(
            finding(
                "X-DATE-ORDER",
                Status.FAILED,
                refs,
                params=params,
                message_key="rule.X-DATE-ORDER.after_as_on",
                severity=Severity.BLOCKING,
            )
        )
    return out


def _receiver_ack(state: CaseState) -> Finding:
    ch = state.papers.get("challan")
    refs = (
        FieldRef("challan", "receiver_stamp_present"),
        FieldRef("challan", "receiver_signature_present"),
    )
    if ch is None:
        return finding("X-RECEIVER-ACK", Status.SKIPPED, refs)
    marks = {
        (field_text(ch, n) or "").lower()
        for n in ("receiver_stamp_present", "receiver_signature_present")
    }
    status = Status.PASSED if "yes" in marks else Status.NEEDS_REVIEW
    return finding("X-RECEIVER-ACK", status, refs)


def check(state: CaseState) -> list[Finding]:
    return [
        _same_gstin(state, "X-SUPPLIER-GSTIN", "supplier_gstin"),
        _same_gstin(state, "X-BUYER-GSTIN", "buyer_gstin"),
        _similar_names(state, "supplier"),
        _similar_names(state, "buyer"),
        _invoice_ref(state),
        *_po_refs(state),
        *_quantities(state),
        *_date_order(state),
        _receiver_ack(state),
    ]
