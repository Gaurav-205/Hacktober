"""Draft notice text (docs/CONTENT.md section 2), filled only with values already formatted.

The templates are plain text (.md.j2). Every sentence comes from the template or from the
clock's basis string; no value from a model is inserted except the confirmed claim values,
which the person has seen and confirmed.
"""

from __future__ import annotations

from datetime import date
from importlib import resources

from jinja2 import Environment, StrictUndefined

from munim_core.dates import DateParseError, parse_date_dayfirst
from munim_core.money import MoneyParseError, parse_inr
from munim_web.services.case_service import CaseSnapshot
from munim_web.translate import translator

_ENV = Environment(autoescape=False, undefined=StrictUndefined, keep_trailing_newline=True)  # noqa: S701  # nosec B701 - plain text; the page escapes it


def _template(lang: str) -> str:
    return (
        resources.files("munim_web.notices")
        .joinpath(f"notice.{lang}.md.j2")
        .read_text(encoding="utf-8")
    )


def notice_text(snap: CaseSnapshot, lang: str, today: date | None = None) -> str | None:
    """The filled notice, or None when unconfirmed or the clock cannot be worked out yet."""
    if not snap.confirmed:
        return None
    outcome = snap.clock.outcome
    if outcome is None or outcome.result is None:
        return None
    t = translator(lang)
    result = outcome.result
    case = snap.case
    if result.basis_key == "clock.basis.capped":
        basis = t(result.basis_key, entered=case["credit_days"])
    else:
        basis = t(result.basis_key, days=result.credit_days_used)
    late_steps = [s for s in result.steps if s.bank_rate_percent is not None]
    unique_bank_rates: list[str] = []
    unique_rates: list[str] = []
    for s in late_steps:
        b_str = str(s.bank_rate_percent)
        r_str = str(s.rate_percent)
        if b_str not in unique_bank_rates:
            unique_bank_rates.append(b_str)
        if r_str not in unique_rates:
            unique_rates.append(r_str)
    conj = " and " if lang == "en" else " और "
    if len(unique_bank_rates) > 1:
        bank_rate = f"{', '.join(unique_bank_rates[:-1])}{conj}{unique_bank_rates[-1]}"
        rate = f"{', '.join(unique_rates[:-1])}{conj}{unique_rates[-1]}"
    elif unique_bank_rates:
        bank_rate = unique_bank_rates[0]
        rate = unique_rates[0]
    else:
        bank_rate = ""
        rate = ""

    def claim_date(kind: str, name: str) -> str:
        text = snap.value(kind, name)
        if not text:
            return ""
        try:
            return t.date(parse_date_dayfirst(text).value)
        except DateParseError:
            return text

    total_text = snap.value("invoice", "invoice_total") or ""
    invoice_total_paise: int | None = None
    if total_text:
        try:
            invoice_total_paise = parse_inr(total_text)
        except (MoneyParseError, ValueError):
            invoice_total_paise = None

    full_invoice_total = (
        invoice_total_paise if invoice_total_paise is not None else snap.clock.principal_paise
    )
    if snap.clock.interest_off:
        interest_paise = 0
        total_owed_paise = (
            full_invoice_total
            if full_invoice_total is not None
            else (snap.clock.principal_paise or 0)
        )
    else:
        interest_paise = result.interest_paise
        if full_invoice_total is not None:
            total_owed_paise = full_invoice_total + interest_paise
        else:
            total_owed_paise = result.total_paise

    context = {
        "today": t.date(today or date.today()),
        "buyer_name": snap.value("invoice", "buyer_name") or case["buyer_name"],
        "buyer_address": case["buyer_address"] or "",
        "supplier_name": snap.value("invoice", "supplier_name") or case["supplier_name"],
        "supplier_address": case["supplier_address"] or "",
        "invoice_number": snap.value("invoice", "invoice_number") or "",
        "invoice_date": claim_date("invoice", "invoice_date"),
        "po_number": snap.value("po", "po_number") or snap.value("invoice", "po_reference") or "",
        "delivery_date": t.date(snap.clock.delivered) if snap.clock.delivered else "",
        "challan_number": snap.value("challan", "challan_number") or "",
        "invoice_total": t.money(full_invoice_total) if full_invoice_total else total_text,
        "due_basis_sentence": basis,
        "due_date": t.date(result.due_date),
        "as_on": t.date(snap.clock.as_on),
        "days_late": result.days_late,
        "bank_rate": bank_rate,
        "rate": rate,
        "interest_off": snap.clock.interest_off,
        "interest": t.money(interest_paise),
        "total_owed": t.money(total_owed_paise),
        "notice_days": case["notice_days"],
        "udyam_number": case["udyam_number"] or "",
        "udyam_date": t.date(case["udyam_date"]) if case["udyam_date"] else "",
    }
    text = _ENV.from_string(_template(lang)).render(**context)
    # The template's rule comments leave trailing spaces; a notice has none.
    return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
