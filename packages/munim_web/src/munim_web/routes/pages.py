"""HTML routes (docs/API.md "Pages"). Thin: parse, call a service, render or redirect."""

from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from PIL import Image

from munim_ai import imageprep
from munim_ai.schemas import FIELD_SPECS
from munim_core.dates import DateParseError, parse_date_dayfirst
from munim_core.money import MoneyParseError, parse_inr
from munim_core.text import whole_number
from munim_core.verify.catalog import RULES
from munim_core.verify.models import FieldRef
from munim_web.db import Database
from munim_web.services import views
from munim_web.services.case_service import CaseSnapshot, load_case, ref_key, ref_of
from munim_web.services.notice import notice_text
from munim_web.services.papers import PROVIDERS, PaperService, UploadError
from munim_web.translate import LANGS, translator
from munim_web.web import LANG_COOKIE, language, render

router = APIRouter()
KINDS = ("invoice", "challan", "po")


def db_of(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def papers_of(request: Request) -> PaperService:
    service: PaperService = request.app.state.papers
    return service


def today(request: Request) -> date:
    fixed = getattr(request.app.state, "today", None)
    return fixed or date.today()


def snapshot_or_404(request: Request, case_id: str) -> CaseSnapshot:
    snap = load_case(db_of(request), case_id, today(request))
    if snap is None:
        raise HTTPException(status_code=404, detail="case.notfound")
    return snap


def back(url: str, *, status: int = 303) -> RedirectResponse:
    return RedirectResponse(url, status_code=status)


def parse_day(text: str | None) -> str | None:
    """A typed date as ISO, or None when empty. Raises ValueError when it is not a date."""
    if text is None or not text.strip():
        return None
    try:
        return parse_date_dayfirst(text).value.isoformat()
    except DateParseError as exc:
        raise ValueError(text) from exc


# ---------------------------------------------------------------- case list
@router.get("/", response_class=HTMLResponse)
async def cases(request: Request) -> Response:
    db = db_of(request)
    rows = []
    for case in db.cases():
        snap = load_case(db, case["id"], today(request))
        owed = None
        if snap and snap.clock.outcome and snap.clock.outcome.result:
            result = snap.clock.outcome.result
            if snap.clock.interest_off:
                owed = result.total_paise - result.interest_paise
            else:
                owed = result.total_paise
        rows.append(
            {"case": case, "kinds": [p["kind"] for p in db.papers(case["id"])], "owed": owed}
        )
    return render(request, "cases.html", rows=rows)


@router.post("/cases")
async def create_case(
    request: Request,
    title: Annotated[str, Form()] = "",
    supplier_name: Annotated[str, Form()] = "",
    buyer_name: Annotated[str, Form()] = "",
) -> Response:
    values = [v.strip()[:200] for v in (title, supplier_name, buyer_name)]
    if not all(values):
        return render(
            request,
            "cases.html",
            status_code=422,
            rows=[],
            form_error="case.err.required",
            form=dict(zip(("title", "supplier_name", "buyer_name"), values, strict=True)),
        )
    case_id = db_of(request).create_case(*values)
    return back(f"/cases/{case_id}")


# ---------------------------------------------------------------- workbench
def workbench_context(request: Request, snap: CaseSnapshot, paper_id: str | None) -> dict[str, Any]:
    t = translator(language(request), request.app.state.settings.dev)
    by_kind = {p["kind"]: p for p in snap.papers}
    selected = next((p for p in snap.papers if p["id"] == paper_id), None) or (
        snap.papers[0] if snap.papers else None
    )
    rows = views.rows_for(snap, selected["id"], t) if selected else []
    invoice = by_kind.get("invoice")
    has_invoice = (
        invoice is not None
        and invoice["status"] in ("read", "failed")
        and any(c["paper_id"] == invoice["id"] for c in snap.claims)
    )
    ctx: dict[str, Any] = {
        "snap": snap,
        "case": snap.case,
        "by_kind": by_kind,
        "kinds": KINDS,
        "selected": selected,
        "rows": rows,
        "counts": views.counts(rows),
        "unresolved": snap.unresolved,
        "can_confirm": has_invoice and not snap.unresolved,
        "has_invoice": has_invoice,
        "payments": snap.payments,
        "step_label": views.step_label,
    }
    ctx.update(views.clock_context(snap, t))
    return ctx


@router.get("/cases/{case_id}", response_class=HTMLResponse)
async def workbench(
    request: Request, case_id: str, paper: str | None = None, error: str | None = None
) -> Response:
    snap = snapshot_or_404(request, case_id)
    ctx = workbench_context(request, snap, paper)
    response = render(request, "workbench.html", error=error, **ctx)
    # The red-pen sequence plays once: clear the flag after it has been rendered.
    for row in ctx["rows"]:
        if row.animate:
            db_of(request).update_claim(row.id, animate=0)
    return response


@router.post("/cases/{case_id}/settings")
async def case_settings(request: Request, case_id: str) -> Response:
    snapshot_or_404(request, case_id)
    form = await request.form()

    def get(name: str) -> str:
        return str(form.get(name) or "").strip()

    values: dict[str, Any] = {}
    try:
        for name in ("acceptance_date", "objection_removed_on", "as_on_date", "udyam_date"):
            if name in form:
                values[name] = parse_day(get(name))
    except ValueError:
        return back(f"/cases/{case_id}?error=settings.case.err.date#terms")
    if "agreement" in form:
        values["agreement"] = get("agreement") if get("agreement") in ("written", "none") else None
    if "credit_days" in form:
        days = get("credit_days")
        credit_days = whole_number(days)
        if days and credit_days is None:
            return back(f"/cases/{case_id}?error=settings.case.err.days#terms")
        values["credit_days"] = credit_days
    if "enterprise_size" in form:
        size = get("enterprise_size")
        values["enterprise_size"] = size if size in ("micro", "small", "medium") else None
    if "interest_base" in form and get("interest_base") in ("invoice_total", "taxable_total"):
        values["interest_base"] = get("interest_base")
    notice_days = whole_number(get("notice_days")) if "notice_days" in form else None
    if notice_days is not None:
        values["notice_days"] = max(1, min(90, notice_days))
    for name in ("udyam_number", "supplier_address", "buyer_address"):
        if name in form:
            values[name] = get(name)[:300] or None
    db = db_of(request)
    db.update_case(case_id, values)
    db.event(case_id, "case.settings", fields=",".join(sorted(values)))
    return back(f"/cases/{case_id}#terms")


@router.post("/cases/{case_id}/payments")
async def add_payment(
    request: Request,
    case_id: str,
    paid_on: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "",
) -> Response:
    snapshot_or_404(request, case_id)
    try:
        day = parse_day(paid_on)
        paise = parse_inr(amount)
    except (ValueError, MoneyParseError):
        return back(f"/cases/{case_id}?error=payments.err#payments")
    if day is None or paise <= 0:
        return back(f"/cases/{case_id}?error=payments.err#payments")
    db = db_of(request)
    db.add_payment(case_id, day, paise)
    db.touch(case_id)
    db.event(case_id, "payment.added")
    return back(f"/cases/{case_id}#payments")


@router.post("/cases/{case_id}/payments/{payment_id}/delete")
async def delete_payment(request: Request, case_id: str, payment_id: str) -> Response:
    db = db_of(request)
    db.delete_payment(case_id, payment_id)
    db.touch(case_id)
    db.event(case_id, "payment.deleted")
    return back(f"/cases/{case_id}#payments")


# ---------------------------------------------------------------- papers
@router.post("/cases/{case_id}/papers")
async def upload(
    request: Request,
    case_id: str,
    file: UploadFile | None = None,
    kind: Annotated[str, Form()] = "",
) -> Response:
    snapshot_or_404(request, case_id)
    if file is None or not file.filename:
        return back(f"/cases/{case_id}?error=paper.err.nofile")
    limit = request.app.state.settings.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        return back(f"/cases/{case_id}?error=paper.err.size")
    try:
        paper_id = await papers_of(request).add(case_id, kind, data)
    except UploadError as exc:
        return back(f"/cases/{case_id}?error={exc.message_key}")
    return back(f"/cases/{case_id}?paper={paper_id}")


def paper_or_404(request: Request, paper_id: str) -> Any:
    paper = db_of(request).paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="error.notfound")
    return paper


@router.post("/papers/{paper_id}/read")
async def read(request: Request, paper_id: str) -> Response:
    paper = paper_or_404(request, paper_id)
    papers_of(request).start_read(paper_id)
    if request.headers.get("hx-request"):
        return await status(request, paper_id)
    return back(f"/cases/{paper['case_id']}?paper={paper_id}")


@router.get("/papers/{paper_id}/status", response_class=HTMLResponse)
async def status(request: Request, paper_id: str) -> Response:
    paper = paper_or_404(request, paper_id)
    if paper["status"] in ("reading", "repairing"):
        return render(request, "_status.html", paper=paper)
    response = render(request, "_status.html", paper=paper)
    response.headers["HX-Redirect"] = f"/cases/{paper['case_id']}?paper={paper_id}"
    return response


@router.post("/papers/{paper_id}/rotate")
async def rotate(request: Request, paper_id: str, deg: int = 90) -> Response:
    paper = paper_or_404(request, paper_id)
    await papers_of(request).rotate(paper_id, 90 if deg not in (90, 180, 270) else deg)
    return back(f"/cases/{paper['case_id']}?paper={paper_id}")


@router.post("/papers/{paper_id}/kind")
async def change_kind(
    request: Request, paper_id: str, kind: Annotated[str, Form()] = ""
) -> Response:
    paper = paper_or_404(request, paper_id)
    papers_of(request).set_kind(paper_id, kind)
    return back(f"/cases/{paper['case_id']}?paper={paper_id}")


@router.post("/papers/{paper_id}/delete")
async def delete_paper(request: Request, paper_id: str) -> Response:
    paper = paper_or_404(request, paper_id)
    papers_of(request).delete(paper_id)
    return back(f"/cases/{paper['case_id']}")


def _image_response(data: bytes) -> Response:
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/papers/{paper_id}/image")
async def image(request: Request, paper_id: str) -> Response:
    paper = paper_or_404(request, paper_id)
    return _image_response(papers_of(request).path(paper["derived_path"]).read_bytes())


@router.get("/papers/{paper_id}/crop")
async def crop(request: Request, paper_id: str, box: str) -> Response:
    paper = paper_or_404(request, paper_id)
    try:
        y1, x1, y2, x2 = (max(0, min(1000, int(v))) for v in box.split(","))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="error.generic") from exc
    if y2 <= y1 or x2 <= x1:
        raise HTTPException(status_code=400, detail="error.generic")
    data = imageprep.crop(
        papers_of(request).path(paper["derived_path"]).read_bytes(), (y1, x1, y2, x2)
    )
    picture = Image.open(io.BytesIO(data))
    picture.thumbnail((480, 240))
    out = io.BytesIO()
    picture.save(out, format="JPEG", quality=85)
    return _image_response(out.getvalue())


# ---------------------------------------------------------------- claims
def claim_or_404(request: Request, claim_id: str) -> Any:
    claim = db_of(request).claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="error.notfound")
    return claim


@router.post("/claims/{claim_id}")
async def edit_claim(
    request: Request,
    claim_id: str,
    value: Annotated[str, Form()] = "",
    version: Annotated[str, Form()] = "",
) -> Response:
    claim = claim_or_404(request, claim_id)
    url = f"/cases/{claim['case_id']}?paper={claim['paper_id']}"
    if version and version != str(claim["version"]):
        return back(f"{url}&error=claims.stale#row-{claim_id}")
    text = " ".join(value.split())[:200] or None
    if text == claim["value_current"]:
        return back(f"{url}#row-{claim_id}")
    db = db_of(request)
    db.set_claim_value(claim_id, text, "user", review_flag=None, animate=0)
    db.touch(claim["case_id"])
    db.event(claim["case_id"], "claim.edited", claim=claim_id)
    return back(f"{url}#row-{claim_id}")


@router.post("/claims/{claim_id}/accept")
async def accept(
    request: Request,
    claim_id: str,
    rule_id: Annotated[str, Form()] = "",
    reason: Annotated[str, Form()] = "",
) -> Response:
    claim = claim_or_404(request, claim_id)
    url = f"/cases/{claim['case_id']}?paper={claim['paper_id']}"
    reason = " ".join(reason.split())[:300]
    if len(reason) < 5:
        return back(f"{url}&error=claims.accept.err#row-{claim_id}")
    snap = snapshot_or_404(request, claim["case_id"])
    ref = ref_of(claim)
    finding = next(
        (
            f
            for f in snap.findings_for(ref)
            if f.rule_id == rule_id
            and not snap.accepted(f)
            and f.status.value in ("failed", "needs_review")
        ),
        None,
    )
    if finding is None:
        return back(f"{url}#row-{claim_id}")
    fields = [[r.paper_kind, r.field, r.index] for r in finding.fields]
    db = db_of(request)
    db.add_acceptance(
        claim["case_id"], finding.rule_id, fields, snap.versions(list(finding.fields)), reason
    )
    db.touch(claim["case_id"])
    db.event(claim["case_id"], "finding.accepted", rule=finding.rule_id)
    return back(f"{url}#row-{claim_id}")


@router.post("/claims/{claim_id}/reread")
async def reread(request: Request, claim_id: str) -> Response:
    claim = claim_or_404(request, claim_id)
    await papers_of(request).repair(claim_id)
    return back(f"/cases/{claim['case_id']}?paper={claim['paper_id']}#row-{claim_id}")


# ---------------------------------------------------------------- confirm, working, evidence
@router.post("/cases/{case_id}/confirm")
async def confirm(request: Request, case_id: str) -> Response:
    snap = snapshot_or_404(request, case_id)
    ctx = workbench_context(request, snap, None)
    if not ctx["can_confirm"]:
        return render(request, "workbench.html", status_code=409, error="confirm.blocked", **ctx)
    db = db_of(request)
    db.confirm(case_id)
    db.event(case_id, "case.confirmed")
    return back(f"/cases/{case_id}?stamped=1")


@router.get("/cases/{case_id}/working", response_class=HTMLResponse)
async def working(request: Request, case_id: str) -> Response:
    snap = snapshot_or_404(request, case_id)
    t = translator(language(request), request.app.state.settings.dev)
    return render(
        request,
        "working.html",
        case=snap.case,
        snap=snap,
        step_label=views.step_label,
        **views.clock_context(snap, t),
    )


@router.get("/cases/{case_id}/dossier", response_class=HTMLResponse)
async def dossier(request: Request, case_id: str) -> Response:
    snap = snapshot_or_404(request, case_id)
    lang = language(request)
    t = translator(lang, request.app.state.settings.dev)
    model = snap.dossier()
    papers = []
    for paper in snap.papers:
        rows = views.rows_for(snap, paper["id"], t)
        papers.append({"paper": paper, "rows": rows})
    notices = {code: notice_text(snap, code, today(request)) for code in LANGS}
    db_of(request).event(case_id, "evidence.viewed")
    return render(
        request,
        "dossier.html",
        case=snap.case,
        snap=snap,
        model=model,
        papers=papers,
        notices=notices,
        step_label=views.step_label,
        **views.clock_context(snap, t),
    )


@router.get("/cases/{case_id}/notice")
async def notice(request: Request, case_id: str, lang: str = "en") -> Response:
    snap = snapshot_or_404(request, case_id)
    text = notice_text(snap, lang if lang in LANGS else "en", today(request))
    if text is None:
        raise HTTPException(status_code=409, detail="notice.unavailable")
    return PlainTextResponse(text)


@router.post("/cases/{case_id}/delete")
async def delete_case(
    request: Request, case_id: str, sure: Annotated[str, Form()] = ""
) -> Response:
    snapshot_or_404(request, case_id)
    if sure != "yes":
        return back(f"/cases/{case_id}#delete")
    papers_of(request).delete_case_files(case_id)
    db_of(request).delete_case(case_id)
    return back("/?deleted=1")


# ---------------------------------------------------------------- rules, evaluation, settings
@router.get("/rules", response_class=HTMLResponse)
async def rules(request: Request, error: str | None = None) -> Response:
    import yaml

    settings = request.app.state.settings
    meta = yaml.safe_load((settings.rules_dir / "rules.yaml").read_text(encoding="utf-8"))
    rows = meta.get("rules", meta) if isinstance(meta, dict) else meta
    return render(
        request,
        "rules.html",
        rules=rows,
        specs=RULES,
        rates=db_of(request).bank_rates(),
        error=error,
    )


@router.post("/rules/bank-rate")
async def bank_rate(
    request: Request,
    effective_from: Annotated[str, Form()] = "",
    percent: Annotated[str, Form()] = "",
    source: Annotated[str, Form()] = "",
    confirmed: Annotated[str, Form()] = "",
) -> Response:
    try:
        day = parse_day(effective_from)
        rate = Decimal(percent.strip())
    except (ValueError, InvalidOperation):
        return back("/rules?error=rules.bank.err#bank")
    if day is None or not (Decimal(0) < rate < Decimal(50)) or not source.strip():
        return back("/rules?error=rules.bank.err#bank")
    db = db_of(request)
    db.upsert_bank_rate(day, str(rate), source.strip()[:300], confirmed == "on")
    for case in db.cases():
        db.touch(case["id"], unconfirm=False)
    db.event(None, "bank_rate.saved", effective_from=day)
    return back("/rules#bank")


@router.get("/evaluation", response_class=HTMLResponse)
async def evaluation(request: Request) -> Response:
    reports = request.app.state.settings.eval_reports
    report = None
    for name in ("latest.json", "replay.json"):
        path = reports / name
        if path.is_file():
            report = json.loads(path.read_text(encoding="utf-8"))
            break
    return render(request, "evaluation.html", report=report)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request, error: str | None = None, check: str | None = None
) -> Response:
    service = papers_of(request)
    preflight: object = None
    if check:
        try:
            preflight = await service.provider().preflight()
        except Exception as exc:  # noqa: BLE001 - shown as a fix message, never raised
            preflight = {"error": getattr(exc, "message_key", "error.provider")}
    return render(
        request,
        "settings.html",
        choice=service.choice(),
        providers=PROVIDERS,
        preflight=preflight,
        error=error,
        settings=request.app.state.settings,
        stored_lang=db_of(request).setting("language") or language(request),
    )


@router.post("/settings")
async def save_settings(
    request: Request,
    provider: Annotated[str, Form()] = "",
    cloud_consent: Annotated[str, Form()] = "",
    language_choice: Annotated[str, Form(alias="language")] = "",
) -> Response:
    db = db_of(request)
    if provider in PROVIDERS and not request.app.state.settings.provider:
        if provider == "gemini" and cloud_consent != "on":
            return back("/settings?error=settings.consent.needed")
        db.set_setting("provider", provider)
    db.set_setting("cloud_consent", "on" if cloud_consent == "on" else "off")
    response = back("/settings")
    if language_choice in LANGS:
        db.set_setting("language", language_choice)
        response.set_cookie(LANG_COOKIE, language_choice, samesite="lax", path="/")
    db.event(None, "settings.saved")
    return response


@router.get("/lang/{code}")
async def switch_language(request: Request, code: str, back_to: str = "/") -> Response:
    target = back_to if back_to.startswith("/") and not back_to.startswith("//") else "/"
    response = back(target, status=303)
    if code in LANGS:
        response.set_cookie(LANG_COOKIE, code, samesite="lax", path="/")
    return response


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request) -> Response:
    return render(request, "about.html")


__all__ = ["FIELD_SPECS", "FieldRef", "ref_key", "router"]
