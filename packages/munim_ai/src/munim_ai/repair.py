"""The repair loop: the red pen (docs/AI_SPEC.md section 7, PLAN_REVIEW D1 and D8).

For one field whose check failed: try a unique look-alike fix first (GSTIN only), otherwise
re-read the marked box with the model. A repair proposes a value for that one field only; it
never edits other fields or makes totals balance. Outcomes:

- corrected: the field's failing checks now pass with the proposed value;
- unchanged: the model read the same value again;
- check_by_hand: no box to re-read, attempts used up, or the new value still fails.

A look-alike correction is flagged so the GSTIN-LOOKALIKE rule keeps it in review.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from munim_ai import imageprep
from munim_ai.extract import parse_json_object
from munim_ai.normalize import clean_value
from munim_ai.prompts import load as load_prompt
from munim_ai.providers.base import Provider, ReadContext
from munim_ai.schemas import field_spec
from munim_core.ids import lookalike_candidates, normalise_gstin

__all__ = ["MAX_ATTEMPTS", "RepairOutcome", "RepairResult", "repair_field"]

MAX_ATTEMPTS = 2


class RepairOutcome(StrEnum):
    CORRECTED = "corrected"
    UNCHANGED = "unchanged"
    CHECK_BY_HAND = "check_by_hand"


@dataclass(frozen=True)
class RepairResult:
    outcome: RepairOutcome
    value: str | None  # the proposed value when corrected
    via: Literal["lookalike", "model"] | None
    attempts: int  # total attempts on this field after this call
    reason_key: str
    flag: str | None = None  # "lookalike" when the value came from the look-alike map


def _same(a: str | None, b: str | None, is_gstin: bool) -> bool:
    if a is None or b is None:
        return a == b
    if is_gstin:
        return normalise_gstin(a) == normalise_gstin(b)
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


async def repair_field(
    *,
    field: str,
    current: str | None,
    box: tuple[int, int, int, int] | None,
    attempts_so_far: int,
    provider: Provider,
    prepared_image: bytes,
    ctx: ReadContext,
    still_failing: Callable[[str], bool],
) -> RepairResult:
    """Try to repair one field. `still_failing(value)` re-runs that field's checks in core."""
    is_gstin = field.endswith("_gstin")
    attempts = attempts_so_far
    if attempts >= MAX_ATTEMPTS:
        return RepairResult(RepairOutcome.CHECK_BY_HAND, None, None, attempts, "redpen.no_attempts")
    if is_gstin and current:
        candidates = lookalike_candidates(current)
        if len(candidates) == 1 and not still_failing(candidates[0]):
            return RepairResult(
                RepairOutcome.CORRECTED,
                candidates[0],
                "lookalike",
                attempts + 1,
                "redpen.reason.lookalike",
                flag="lookalike",
            )
    if box is None:
        return RepairResult(RepairOutcome.CHECK_BY_HAND, None, None, attempts, "redpen.no_box")
    spec = field_spec(field)
    reread_version = load_prompt("reread.system.md").version
    piece = imageprep.crop(prepared_image, box)
    value = current
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        result = await provider.reread(piece, spec, ctx.for_reread(field, box, reread_version))
        data = parse_json_object(result.text)
        raw = data.get("value") if data else None
        new = clean_value(raw) if isinstance(raw, str) else None
        if new is None or _same(new, value, is_gstin):
            return RepairResult(
                RepairOutcome.UNCHANGED, None, "model", attempts, "redpen.unchanged"
            )
        if not still_failing(new):
            reason = "redpen.reason.gstin" if is_gstin else "redpen.reason.reread"
            return RepairResult(RepairOutcome.CORRECTED, new, "model", attempts, reason)
        value = new
    return RepairResult(
        RepairOutcome.CHECK_BY_HAND, None, "model", attempts, "redpen.still_failing"
    )
