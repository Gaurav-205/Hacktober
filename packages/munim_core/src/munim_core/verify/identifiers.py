"""Identifier rules: GSTIN-*, PAN-FORMAT, UDYAM-FORMAT (docs/DOMAIN_RULES.md 3.1)."""

from __future__ import annotations

from munim_core.ids import check_gstin, check_pan, check_udyam
from munim_core.verify.common import field_text, finding, present_papers
from munim_core.verify.models import CaseState, FieldRef, Finding, Status

GSTIN_FIELDS = {
    "invoice": ("supplier_gstin", "buyer_gstin"),
    "challan": ("supplier_gstin", "buyer_gstin"),
    "po": ("buyer_gstin", "supplier_gstin"),
}
GSTIN_RULES = ("GSTIN-FORMAT", "GSTIN-STATE", "GSTIN-CHECKSUM")


def _gstin_findings(kind: str, name: str, text: str | None) -> list[Finding]:
    ref = (FieldRef(kind, name),)
    if text is None:
        return [finding(rule_id, Status.SKIPPED, ref) for rule_id in GSTIN_RULES]
    result = check_gstin(text)
    shape_ok = result.state_code is not None
    out: list[Finding] = []
    for rule_id in GSTIN_RULES:
        if rule_id != "GSTIN-FORMAT" and not shape_ok:
            out.append(finding(rule_id, Status.SKIPPED, ref))
        elif rule_id in result.errors:
            params = {"code": result.state_code or ""} if rule_id == "GSTIN-STATE" else {}
            out.append(finding(rule_id, Status.FAILED, ref, params=params))
        else:
            out.append(finding(rule_id, Status.PASSED, ref))
    return out


def check(state: CaseState) -> list[Finding]:
    out: list[Finding] = []
    for kind, paper in present_papers(state):
        for name in GSTIN_FIELDS[kind]:
            if name not in paper.fields:
                continue
            claim = paper.fields[name]
            out.extend(_gstin_findings(kind, name, field_text(paper, name)))
            if claim.flag == "lookalike":
                out.append(finding("GSTIN-LOOKALIKE", Status.NEEDS_REVIEW, (FieldRef(kind, name),)))
    invoice = state.papers.get("invoice")
    if invoice is not None:
        out.extend(
            _pan_findings(
                field_text(invoice, "supplier_gstin"), field_text(invoice, "supplier_pan")
            )
        )
    out.append(_udyam_finding(state.udyam_number))
    return out


def _pan_findings(gstin_text: str | None, pan_text: str | None) -> list[Finding]:
    pan_ref = FieldRef("invoice", "supplier_pan")
    refs = (FieldRef("invoice", "supplier_gstin"), pan_ref)
    if pan_text is None:
        return [
            finding("GSTIN-PAN", Status.SKIPPED, refs),
            finding("PAN-FORMAT", Status.SKIPPED, (pan_ref,)),
        ]
    pan = pan_text.replace(" ", "").upper()
    fmt = finding("PAN-FORMAT", Status.PASSED if check_pan(pan) else Status.FAILED, (pan_ref,))
    gstin_pan = check_gstin(gstin_text).pan if gstin_text else None
    if gstin_pan is None:
        return [finding("GSTIN-PAN", Status.SKIPPED, refs), fmt]
    if gstin_pan == pan:
        return [finding("GSTIN-PAN", Status.PASSED, refs), fmt]
    params = {"pan_gstin": gstin_pan, "pan_paper": pan_text}
    return [finding("GSTIN-PAN", Status.FAILED, refs, params=params), fmt]


def _udyam_finding(udyam: str | None) -> Finding:
    ref = (FieldRef("case", "udyam_number"),)
    if not udyam or not udyam.strip():
        return finding("UDYAM-FORMAT", Status.SKIPPED, ref)
    status = Status.PASSED if check_udyam(udyam) else Status.FAILED
    return finding("UDYAM-FORMAT", status, ref, params={"printed": udyam})
