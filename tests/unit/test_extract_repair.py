"""Reading one paper and the red-pen repair loop (docs/AI_SPEC.md 6 and 7, PLAN_REVIEW D1, D9)."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field

import pytest
from PIL import Image

from munim_ai.extract import extract_paper, parse_json_object
from munim_ai.prompts import load
from munim_ai.providers.base import PreflightReport, ProviderResult, ReadContext
from munim_ai.repair import MAX_ATTEMPTS, RepairOutcome, repair_field
from munim_ai.schemas import FieldSpec, PaperKind
from munim_core.ids import check_gstin, lookalike_candidates
from tests.unit.verify_helpers import BUYER_GSTIN, SUPPLIER_GSTIN

pytestmark = pytest.mark.unit

CTX = ReadContext(original_sha256="cd" * 32, kind="invoice", prompt_version="1")


@dataclass
class ScriptedProvider:
    """Returns scripted texts in order and records what it was asked."""

    texts: list[str]
    name: str = "scripted"
    model: str = "fake"
    contexts: list[ReadContext] = field(default_factory=list)
    images: list[bytes] = field(default_factory=list)
    fields: list[FieldSpec] = field(default_factory=list)

    def _next(self) -> ProviderResult:
        return ProviderResult(self.texts.pop(0), 3, self.name, self.model)

    async def extract(
        self, image: bytes, kind: PaperKind, language_hint: str | None, ctx: ReadContext
    ) -> ProviderResult:
        self.contexts.append(ctx)
        self.images.append(image)
        return self._next()

    async def reread(self, crop: bytes, spec: FieldSpec, ctx: ReadContext) -> ProviderResult:
        self.contexts.append(ctx)
        self.images.append(crop)
        self.fields.append(spec)
        return self._next()

    async def preflight(self) -> PreflightReport:
        return PreflightReport(self.name, self.model, True)


def good_invoice(**extra: object) -> str:
    data: dict[str, object] = {
        "supplier_gstin": {"value": SUPPLIER_GSTIN, "box_2d": [10, 10, 20, 200]},
        "buyer_gstin": {"value": BUYER_GSTIN, "box_2d": [30, 10, 40, 200]},
        "invoice_total": {"value": "5,00,000.00", "box_2d": [900, 700, 920, 900]},
    }
    data.update(extra)
    return json.dumps(data)


def values(outcome: object) -> dict[str, str | None]:
    return {d.field: d.value for d in outcome.claims if d.index is None}  # type: ignore[attr-defined]


# ---------------------------------------------------------------- parse_json_object
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": {"b": 2}}\n```', {"a": {"b": 2}}),
        ('Here is the JSON:\n{"a": 1}\nThanks.', {"a": 1}),
        ('{"a": 1', None),
        ("[1, 2]", None),
        ("no json at all", None),
        ("", None),
    ],
)
def test_parse_json_object(text: str, expected: object) -> None:
    assert parse_json_object(text) == expected


# ---------------------------------------------------------------- extract_paper
async def test_valid_first_answer_is_used_without_retry() -> None:
    provider = ScriptedProvider([good_invoice()])
    outcome = await extract_paper(provider, b"img", "invoice", CTX)
    assert (outcome.ok, outcome.partial, outcome.attempts, outcome.invalid_attempts) == (
        True,
        False,
        1,
        0,
    )
    assert values(outcome)["invoice_total"] == "5,00,000.00"
    assert outcome.result is not None and outcome.result.provider == "scripted"
    assert [c.attempt for c in provider.contexts] == [1]


async def test_malformed_first_answer_gets_one_strict_retry() -> None:
    provider = ScriptedProvider(["sorry, I cannot", good_invoice()])
    outcome = await extract_paper(provider, b"img", "invoice", CTX)
    assert (outcome.ok, outcome.attempts, outcome.invalid_attempts) == (True, 2, 1)
    assert [c.attempt for c in provider.contexts] == [1, 2]
    assert all(c.original_sha256 == CTX.original_sha256 for c in provider.contexts)


async def test_two_malformed_answers_fail_soft() -> None:
    provider = ScriptedProvider(["nope", "{broken"])
    outcome = await extract_paper(provider, b"img", "invoice", CTX)
    assert (outcome.ok, outcome.claims, outcome.invalid_attempts) == (False, (), 2)


async def test_schema_invalid_answer_keeps_valid_fields_when_anchors_are_present() -> None:
    bad_lines = good_invoice(line_items=[{}] * 13)  # too many lines: the whole read is invalid
    provider = ScriptedProvider([bad_lines, bad_lines])
    outcome = await extract_paper(provider, b"img", "invoice", CTX)
    assert (outcome.ok, outcome.partial) == (True, True)
    assert values(outcome)["buyer_gstin"] == BUYER_GSTIN
    assert len([d for d in outcome.claims if d.index is not None]) == 12 * 6


async def test_schema_invalid_answer_without_anchors_fails_soft() -> None:
    answer = json.dumps({"invoice_number": "INV-1", "line_items": [{}] * 13})
    outcome = await extract_paper(ScriptedProvider([answer, answer]), b"img", "invoice", CTX)
    assert outcome.ok is False


async def test_runaway_value_is_dropped_and_flagged() -> None:
    answer = good_invoice(buyer_name={"value": "A" * 500})
    outcome = await extract_paper(ScriptedProvider([answer]), b"img", "invoice", CTX)
    runaway = next(d for d in outcome.claims if d.field == "buyer_name")
    assert (runaway.value, runaway.flag) == (None, "runaway")


# ---------------------------------------------------------------- repair_field
def prepared_image() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (1000, 800), "white").save(out, format="JPEG")
    return out.getvalue()


def gstin_fails(value: str) -> bool:
    return not check_gstin(value).ok


async def repair(provider: ScriptedProvider, field_name: str, current: str, **kw: object) -> object:
    args: dict[str, object] = {
        "field": field_name,
        "current": current,
        "box": (100, 100, 200, 400),
        "attempts_so_far": 0,
        "provider": provider,
        "prepared_image": prepared_image(),
        "ctx": CTX,
        "still_failing": gstin_fails,
    }
    args.update(kw)
    return await repair_field(**args)  # type: ignore[arg-type]


async def test_unique_lookalike_fix_is_used_without_calling_the_model() -> None:
    misread = "O" + SUPPLIER_GSTIN[1:]
    assert lookalike_candidates(misread) == [SUPPLIER_GSTIN]
    provider = ScriptedProvider([])
    result = await repair(provider, "supplier_gstin", misread)
    assert result.outcome == RepairOutcome.CORRECTED  # type: ignore[attr-defined]
    assert (result.value, result.via, result.flag, result.reason_key) == (  # type: ignore[attr-defined]
        SUPPLIER_GSTIN,
        "lookalike",
        "lookalike",
        "redpen.reason.lookalike",
    )
    assert provider.contexts == []


async def test_misread_outside_the_lookalike_map_is_re_read_from_the_crop() -> None:
    misread = SUPPLIER_GSTIN[:-1] + "M"
    assert lookalike_candidates(misread) == []
    provider = ScriptedProvider([json.dumps({"value": SUPPLIER_GSTIN, "box_2d": None})])
    result = await repair(provider, "supplier_gstin", misread)
    assert result.outcome == RepairOutcome.CORRECTED  # type: ignore[attr-defined]
    assert (result.value, result.via, result.reason_key, result.attempts) == (  # type: ignore[attr-defined]
        SUPPLIER_GSTIN,
        "model",
        "redpen.reason.gstin",
        1,
    )
    ctx = provider.contexts[0]
    assert (ctx.field, ctx.box, ctx.prompt_version) == (
        "supplier_gstin",
        (100, 100, 200, 400),
        load("reread.system.md").version,
    )
    crop = Image.open(io.BytesIO(provider.images[0]))
    assert crop.size == (300 + 2 * 24, 80 + 2 * 6)  # box on the prepared image, 8% a side
    assert provider.fields[0].name == "supplier_gstin"


async def test_non_gstin_field_uses_the_reread_reason() -> None:
    provider = ScriptedProvider([json.dumps({"value": "5,00,000.00"})])
    result = await repair(
        provider, "invoice_total", "5,O0,000.00", still_failing=lambda v: "O" in v
    )
    assert (result.outcome, result.reason_key) == (  # type: ignore[attr-defined]
        RepairOutcome.CORRECTED,
        "redpen.reason.reread",
    )


async def test_same_value_read_again_is_unchanged() -> None:
    misread = SUPPLIER_GSTIN[:-1] + "M"
    provider = ScriptedProvider([json.dumps({"value": misread.lower()})])
    result = await repair(provider, "supplier_gstin", misread)
    assert (result.outcome, result.reason_key, result.value) == (  # type: ignore[attr-defined]
        RepairOutcome.UNCHANGED,
        "redpen.unchanged",
        None,
    )


async def test_values_that_keep_failing_end_in_check_by_hand() -> None:
    misread = SUPPLIER_GSTIN[:-1] + "M"
    provider = ScriptedProvider(
        [
            json.dumps({"value": SUPPLIER_GSTIN[:-1] + "Q"}),
            json.dumps({"value": SUPPLIER_GSTIN[:-1] + "R"}),
        ]
    )
    result = await repair(provider, "supplier_gstin", misread)
    assert (result.outcome, result.reason_key, result.attempts) == (  # type: ignore[attr-defined]
        RepairOutcome.CHECK_BY_HAND,
        "redpen.still_failing",
        MAX_ATTEMPTS,
    )


async def test_no_attempts_left_and_no_box_need_no_model_call() -> None:
    provider = ScriptedProvider([])
    used = await repair(provider, "invoice_total", "x", attempts_so_far=MAX_ATTEMPTS)
    assert (used.outcome, used.reason_key) == (RepairOutcome.CHECK_BY_HAND, "redpen.no_attempts")  # type: ignore[attr-defined]
    boxless = await repair(provider, "invoice_total", "x", box=None)
    assert (boxless.outcome, boxless.reason_key) == (RepairOutcome.CHECK_BY_HAND, "redpen.no_box")  # type: ignore[attr-defined]
    assert provider.contexts == []


async def test_unreadable_reread_answer_counts_as_unchanged() -> None:
    provider = ScriptedProvider(["not json"])
    result = await repair(provider, "supplier_gstin", SUPPLIER_GSTIN[:-1] + "M")
    assert result.outcome == RepairOutcome.UNCHANGED  # type: ignore[attr-defined]
