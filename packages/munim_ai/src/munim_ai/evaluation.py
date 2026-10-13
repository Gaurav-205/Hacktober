"""The evaluation harness (docs/AI_SPEC.md section 8, PLAN_REVIEW D10).

Reads every paper of a manifest with a provider, scores the FIRST-READ values against the truth
(before any repair), runs the core rules over each case built from those values, and measures
the headline: fields that were wrong and that no applicable rule failed or flagged. Repairs are
then tried on misread identifiers and amounts and on the injected GSTIN faults.

The numbers say nothing about a value being true in the world; they compare a read with the
synthetic truth the generator printed.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

from PIL import Image

from munim_ai import imageprep
from munim_ai.extract import ExtractOutcome, extract_paper
from munim_ai.normalize import ClaimDraft
from munim_ai.prompts import extraction_prompt, load
from munim_ai.providers.base import Provider, ProviderError, ReadContext
from munim_ai.providers.replay import ReplayMiss
from munim_ai.repair import RepairOutcome, repair_field
from munim_ai.schemas import PaperKind
from munim_core.dates import DateParseError, parse_date_dayfirst
from munim_core.ids import normalise_gstin
from munim_core.money import MoneyParseError, parse_signed_inr
from munim_core.verify.models import CaseState, ClaimValue, FieldRef, Finding, PaperState, Status
from munim_core.verify.registry import run_all

__all__ = [
    "AMOUNT_FIELDS",
    "IDENTIFIER_FIELDS",
    "REQUIRED_FIELDS",
    "case_state",
    "caught",
    "iou",
    "run_evaluation",
    "same_value",
]

SCHEMA_VERSION = 1
AMOUNT_FIELDS = frozenset(
    {"taxable_total", "cgst", "sgst", "igst", "round_off", "invoice_total", "rate", "amount"}
)
IDENTIFIER_FIELDS = frozenset(
    {
        "supplier_gstin",
        "buyer_gstin",
        "supplier_pan",
        "invoice_number",
        "challan_number",
        "po_number",
        "bank_ifsc",
    }
)
REQUIRED_FIELDS: Mapping[str, frozenset[str]] = {
    "invoice": frozenset(
        {
            "supplier_name",
            "supplier_gstin",
            "buyer_name",
            "buyer_gstin",
            "invoice_number",
            "invoice_date",
            "taxable_total",
            "invoice_total",
        }
    ),
    "challan": frozenset(
        {"supplier_name", "supplier_gstin", "buyer_name", "challan_number", "challan_date"}
    ),
    "po": frozenset({"buyer_name", "buyer_gstin", "po_number", "po_date"}),
}
REPAIRABLE = AMOUNT_FIELDS | {"supplier_gstin", "buyer_gstin"}


# ---------------------------------------------------------------- comparisons
def _norm(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if field_name in AMOUNT_FIELDS:
        try:
            return str(parse_signed_inr(value))
        except MoneyParseError:
            pass
    if field_name.endswith("_date"):
        try:
            return parse_date_dayfirst(value).value.isoformat()
        except DateParseError:
            pass
    if field_name.endswith("_gstin"):
        return normalise_gstin(value)
    return " ".join(value.split()).casefold()


def same_value(field_name: str, read: str | None, truth: str | None) -> bool:
    """Equal after the normalisation a person would accept (paise, ISO date, GSTIN, case)."""
    return _norm(field_name, read) == _norm(field_name, truth)


def iou(a: list[int] | tuple[int, ...] | None, b: list[int] | tuple[int, ...] | None) -> float:
    """Intersection over union of two [y1, x1, y2, x2] boxes; 0 when either is missing."""
    if not a or not b:
        return 0.0
    y1, x1 = max(a[0], b[0]), max(a[1], b[1])
    y2, x2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, y2 - y1) * max(0, x2 - x1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def case_state(
    papers: Mapping[str, tuple[ClaimDraft, ...]], as_on: date | None = None
) -> CaseState:
    """The rules' view of a case built from claim drafts (first-read values, source model)."""
    states: dict[str, PaperState] = {}
    for kind, drafts in papers.items():
        fields: dict[str, ClaimValue] = {}
        lines: dict[int, dict[str, ClaimValue]] = {}
        for d in drafts:
            value = ClaimValue(raw=d.value_read, text=d.value, source="model", flag=d.flag)
            if d.index is None:
                fields[d.field] = value
            else:
                lines.setdefault(d.index, {})[d.field] = value
        states[kind] = PaperState(
            kind=kind, fields=fields, lines=tuple(lines[i] for i in sorted(lines))
        )
    return CaseState(papers=states, as_on=as_on)


def caught(findings: list[Finding], ref: FieldRef) -> list[str]:
    """Rule ids that failed or flagged this field. Empty means the error was not caught."""
    return sorted(
        {
            f.rule_id
            for f in findings
            if f.status in (Status.FAILED, Status.NEEDS_REVIEW) and ref in f.fields
        }
    )


# ---------------------------------------------------------------- the run
@dataclass
class PaperRun:
    id: str
    kind: PaperKind
    truth: dict[str, Any]
    original: bytes
    prepared: imageprep.Prepared
    ctx: ReadContext
    outcome: ExtractOutcome | None = None
    missing: bool = False
    error: str | None = None


@dataclass
class Tally:
    n: int = 0
    hit: int = 0

    def add(self, ok: bool) -> None:
        self.n += 1
        self.hit += int(ok)

    def rate(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "matched": self.hit,
            "rate": round(self.hit / self.n, 4) if self.n else None,
        }


@dataclass
class Scores:
    exact_required: Tally = field(default_factory=Tally)
    amounts: Tally = field(default_factory=Tally)
    identifiers: Tally = field(default_factory=Tally)
    boxes: Tally = field(default_factory=Tally)
    scored: int = 0
    wrong: int = 0
    wrong_and_passed: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)


def _crop_uri(run: PaperRun, box: list[int] | None) -> str | None:
    if not box:
        return None
    data = imageprep.crop(run.prepared.jpeg, (box[0], box[1], box[2], box[3]))
    image = Image.open(io.BytesIO(data))
    image.thumbnail((320, 320))
    out = io.BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def _truth_cells(truth: dict[str, Any]) -> list[tuple[str, int | None, dict[str, Any]]]:
    cells: list[tuple[str, int | None, dict[str, Any]]] = [
        (name, None, cell) for name, cell in truth["fields"].items()
    ]
    for index, row in enumerate(truth["line_items"]):
        cells += [(name, index, cell) for name, cell in row.items()]
    return [c for c in cells if c[2].get("value")]


def _score_paper(run: PaperRun, findings: list[Finding], scores: Scores) -> None:
    claims = run.outcome.claims if run.outcome else ()
    read = {(d.field, d.index): d for d in claims}
    for name, index, cell in _truth_cells(run.truth):
        draft = read.get((name, index))
        value = draft.value if draft else None
        ok = same_value(name, value, cell["value"])
        scores.scored += 1
        if index is None and name in REQUIRED_FIELDS[run.kind]:
            scores.exact_required.add(ok)
        if name in AMOUNT_FIELDS:
            scores.amounts.add(ok)
        if name in IDENTIFIER_FIELDS:
            scores.identifiers.add(ok)
        if draft and draft.box and cell.get("box"):
            scores.boxes.add(iou(draft.box, cell["box"]) >= 0.5)
        if ok:
            continue
        scores.wrong += 1
        rules = caught(findings, FieldRef(run.kind, name, index))
        if not rules:
            scores.wrong_and_passed += 1
        scores.failures.append(
            {
                "paper": run.id,
                "field": name if index is None else f"{name}[{index}]",
                "truth": cell["value"],
                "read": value,
                "rules": rules,
                "caught": bool(rules),
                "crop": _crop_uri(run, cell.get("box")),
            }
        )


async def _repair_one(
    provider: Provider,
    run: PaperRun,
    name: str,
    papers: dict[str, tuple[ClaimDraft, ...]],
    as_on: date,
) -> RepairOutcome:
    claims = run.outcome.claims if run.outcome else ()
    draft = next(d for d in claims if d.field == name and d.index is None)
    ref = FieldRef(run.kind, name)

    def still_failing(value: str) -> bool:
        changed = tuple(
            ClaimDraft(d.field, d.index, d.value_read, value, d.box, d.flag)
            if (d.field, d.index) == (name, None)
            else d
            for d in papers[run.kind]
        )
        state = case_state({**papers, run.kind: changed}, as_on)
        return any(f.blocks and ref in f.fields for f in run_all(state, as_on))

    result = await repair_field(
        field=name,
        current=draft.value,
        box=draft.box,
        attempts_so_far=0,
        provider=provider,
        prepared_image=run.prepared.jpeg,
        ctx=run.ctx,
        still_failing=still_failing,
    )
    return result.outcome


async def run_evaluation(
    provider: Provider,
    fixtures: Path,
    *,
    as_on: date,
    limit: int | None = None,
    case_ids: set[str] | None = None,
    repair: bool = True,
) -> dict[str, Any]:
    """Read, score and repair; return the report as a JSON-ready dict."""
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    cases = [c for c in manifest["cases"] if case_ids is None or c["id"] in case_ids]
    wanted = {pid for c in cases for pid in c["papers"].values()}
    papers = [p for p in manifest["papers"] if p["id"] in wanted][:limit]
    runs: dict[str, PaperRun] = {}
    latencies: list[int] = []
    for p in papers:
        original = (fixtures / p["image"]).read_bytes()
        truth = json.loads((fixtures / "truth" / f"{p['id']}.json").read_text(encoding="utf-8"))
        kind = cast(PaperKind, p["kind"])
        ctx = ReadContext(
            original_sha256=hashlib.sha256(original).hexdigest(),
            kind=kind,
            prompt_version=extraction_prompt(kind).version,
        )
        run = PaperRun(p["id"], kind, truth, original, imageprep.prepare(original), ctx)
        try:
            run.outcome = await extract_paper(provider, run.prepared.jpeg, kind, ctx)
            if run.outcome.result and not run.outcome.result.replayed:
                latencies.append(run.outcome.result.latency_ms)
        except ReplayMiss:
            run.missing = True
        except ProviderError as exc:
            run.error = exc.message_key
        runs[p["id"]] = run

    scores = Scores()
    retry = failed_after_retry = read_papers = 0
    repairs: dict[str, dict[str, int]] = {"model_misreads": {}, "injected_gstin": {}}
    for case in cases:
        members = {k: runs[pid] for k, pid in case["papers"].items() if pid in runs}
        read = {k: r for k, r in members.items() if r.outcome is not None}
        drafts = {k: r.outcome.claims for k, r in read.items() if r.outcome}
        findings = run_all(case_state(drafts, as_on), as_on)
        for kind, run in read.items():
            injected_paper = bool(run.truth["injected"])
            if case["injected"] != injected_paper:
                continue  # each paper is scored once, in its own case
            outcome = run.outcome
            if outcome is None:
                continue
            if not injected_paper:
                read_papers += 1
                retry += int(outcome.attempts > 1)
                failed_after_retry += int(not outcome.ok)
                if outcome.ok:  # a failed read goes to hand entry; it is counted above
                    _score_paper(run, findings, scores)
            if not repair or not outcome.ok:
                continue
            if injected_paper:
                targets = [
                    f["field"] for f in run.truth["injected"] if f["field"].endswith("_gstin")
                ]
                bucket = repairs["injected_gstin"]
            else:
                targets = [
                    m["field"]
                    for m in run.truth["simulated_misreads"]
                    if m["index"] is None and m["field"] in REPAIRABLE
                ]
                bucket = repairs["model_misreads"]
            for name in targets:
                if not any(f.blocks and FieldRef(kind, name) in f.fields for f in findings):
                    bucket["not_flagged"] = bucket.get("not_flagged", 0) + 1
                    continue
                result = await _repair_one(provider, run, name, drafts, as_on)
                bucket[str(result)] = bucket.get(str(result), 0) + 1

    missing = sorted(r.id for r in runs.values() if r.missing)
    errors = sorted(f"{r.id}: {r.error}" for r in runs.values() if r.error)
    recorded = {
        r.outcome.result.recorded_from
        for r in runs.values()
        if r.outcome and r.outcome.result and r.outcome.result.replayed
    }
    recorded_from = (
        "live"
        if not recorded and getattr(provider, "name", "") != "replay"
        else next(iter(recorded))
        if len(recorded) == 1
        else "mixed"
    )
    caught_n = scores.wrong - scores.wrong_and_passed
    failures = sorted(scores.failures, key=lambda f: (f["caught"], f["paper"], f["field"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider.name,
        "model": provider.model,
        "recorded_from": recorded_from,
        "prompt_versions": _prompt_versions(),
        "date": as_on.isoformat(),
        "n_papers": read_papers,
        "n_fields": scores.scored,
        "metrics": {
            "field_exact_match_required": scores.exact_required.rate(),
            "amount_exact_match": scores.amounts.rate(),
            "identifier_exact_match": scores.identifiers.rate(),
            "box_iou_at_least_0_5": scores.boxes.rate(),
            "invalid_json": {
                "papers": read_papers,
                "needed_retry": retry,
                "failed_after_retry": failed_after_retry,
            },
            "wrong_and_passed": {
                "count": scores.wrong_and_passed,
                "over_scored_fields": _ratio(scores.wrong_and_passed, scores.scored),
                "over_wrong_fields": _ratio(scores.wrong_and_passed, scores.wrong),
            },
            "detected_and_flagged": {
                "count": caught_n,
                "over_wrong_fields": _ratio(caught_n, scores.wrong),
            },
            "wrong_fields": scores.wrong,
            "repair": repairs,
            "latency_ms": _latency(latencies),
        },
        "missing_recordings": missing,
        "provider_errors": errors,
        "summary": (
            f"In {scores.wrong} of {scores.scored} fields the value was wrong; "
            f"the checks caught {caught_n} of those {scores.wrong}."
        ),
        "caveat": (
            "Synthetic papers. These numbers do not predict accuracy on real papers."
            + (
                " Recorded responses were replayed, so they test the checks and the harness, "
                "not the model."
                if recorded
                else ""
            )
        ),
        "failure_examples": failures[:8],
    }


def _ratio(part: int, whole: int) -> dict[str, Any]:
    return {"n": whole, "count": part, "rate": round(part / whole, 4) if whole else None}


def _latency(values: list[int]) -> dict[str, Any] | None:
    if not values:
        return None
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    return {"median": statistics.median(ordered), "p95": p95, "n": len(ordered)}


def _prompt_versions() -> dict[str, str]:
    names = ("invoice.system.md", "challan.system.md", "po.system.md", "reread.system.md")
    return {name.split(".")[0]: load(name).version for name in names}


current_prompt_versions: Callable[[], dict[str, str]] = _prompt_versions
