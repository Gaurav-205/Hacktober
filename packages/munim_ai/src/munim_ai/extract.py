"""Reading one paper (docs/AI_SPEC.md sections 4 and 6).

parse -> validate -> one strict retry -> keep valid fields when the anchor fields are present
-> otherwise fail soft so the person enters values by hand. Provider errors (unreachable,
timeout, replay miss) are not caught here: the caller records them on the paper.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from munim_ai.normalize import ClaimDraft, drafts_from_read
from munim_ai.providers.base import Provider, ProviderResult, ReadContext
from munim_ai.schemas import ANCHORS, Field_, LineItem, PaperKind, read_model_for

__all__ = ["ExtractOutcome", "extract_paper", "parse_json_object"]

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractOutcome:
    """What a read produced.

    ok is False when nothing usable came back: the paper shows "Enter the values by hand".
    partial is True when some fields failed validation and were dropped. invalid_attempts
    counts attempts whose text was not valid JSON for the schema (for the evaluation).
    """

    claims: tuple[ClaimDraft, ...]
    ok: bool
    partial: bool
    attempts: int
    invalid_attempts: int
    result: ProviderResult | None


def parse_json_object(text: str) -> dict[str, Any] | None:
    """The JSON object in a model answer, tolerating code fences and stray prose around it."""
    stripped = _FENCE.sub("", text.strip())
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    body = stripped[start : end + 1]
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        value = _without_trailing_array(body)
        if value is None:
            return None
    return value if isinstance(value, dict) else None


# A trailing list-valued field, comma and all, up to the object's closing brace.
_TRAILING_ARRAY = re.compile(r',\s*"[a-z_]+"\s*:\s*\[.*\]\s*(?=\}$)', re.DOTALL)


def _without_trailing_array(body: str) -> dict[str, Any] | None:
    """Drop a trailing list-valued field and parse again, or None.

    Gemma 4 misspells the `line_items` array often enough to matter: it writes the first item's
    `amount` as a sibling of the item object, so the document has no valid JSON reading at all.
    Every other field on the paper is scalar, and no verify rule reads a line item, so dropping
    that one array is better than dropping the whole paper. The dropped field is absent from the
    result, and the schema treats it as optional.
    """
    try:
        value = json.loads(_TRAILING_ARRAY.sub("", body))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _validate(kind: str, data: dict[str, Any]) -> Any | None:
    model = read_model_for(kind)
    try:
        return model.model_validate({**data, "kind": kind})
    except ValidationError:
        return None


def _salvage(kind: str, data: dict[str, Any]) -> Any | None:
    """Keep each top-level field that validates on its own; None if the anchors are missing."""
    model = read_model_for(kind)
    kept: dict[str, Any] = {"kind": kind}
    for name in model.model_fields:
        if name in ("kind", "line_items") or name not in data:
            continue
        try:
            kept[name] = Field_.model_validate(data[name])
        except ValidationError:
            continue
    lines = data.get("line_items")
    if isinstance(lines, list):
        good = []
        for line in lines[:12]:
            try:
                good.append(LineItem.model_validate(line))
            except ValidationError:
                continue
        kept["line_items"] = good
    anchors = ANCHORS[kind]
    present = {n for n in anchors if (f := kept.get(n)) is not None and f.value}
    needs_all = anchors[0]
    if needs_all not in present or len(present) < min(2, len(anchors)):
        return None
    return model.model_validate(kept)


async def extract_paper(
    provider: Provider,
    image: bytes,
    kind: PaperKind,
    ctx: ReadContext,
    language_hint: str | None = None,
) -> ExtractOutcome:
    """Read a prepared image with one strict retry. Never raises for bad model output."""
    last: ProviderResult | None = None
    invalid = 0
    best_data: dict[str, Any] | None = None
    for attempt in (1, 2):
        attempt_ctx = ReadContext(
            original_sha256=ctx.original_sha256,
            kind=kind,
            prompt_version=ctx.prompt_version,
            rotation=ctx.rotation,
            attempt=attempt,
        )
        last = await provider.extract(image, kind, language_hint, attempt_ctx)
        data = parse_json_object(last.text)
        if data is not None:
            best_data = data
            read = _validate(kind, data)
            if read is not None:
                drafts = tuple(drafts_from_read(kind, read))
                return ExtractOutcome(drafts, True, False, attempt, invalid, last)
        invalid += 1
    if best_data is not None:
        salvaged = _salvage(kind, best_data)
        if salvaged is not None:
            return ExtractOutcome(
                tuple(drafts_from_read(kind, salvaged)), True, True, 2, invalid, last
            )
    return ExtractOutcome((), False, False, 2, invalid, last)
