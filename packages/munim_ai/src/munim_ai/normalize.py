"""From a validated read to claim drafts (docs/AI_SPEC.md section 3, post-processing).

Every value is cleaned the same way: Unicode NFC, surrounding and repeated whitespace removed,
other scripts' digits made ASCII, and Aadhaar-like numbers masked. Masking happens here, before
anything is stored or logged. `value_read` keeps what the model wrote (masked); `value` is the
cleaned text the rules check. A runaway value (over 200 characters) is dropped and flagged.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from munim_ai.schemas import LINE_FIELDS, PAPER_FIELDS, Field_, LineItem
from munim_core.ids import mask_aadhaar
from munim_core.text import to_ascii_digits

__all__ = ["ClaimDraft", "clean_value", "drafts_from_read"]


@dataclass(frozen=True)
class ClaimDraft:
    field: str
    index: int | None
    value_read: str | None
    value: str | None
    box: tuple[int, int, int, int] | None
    flag: str | None = None  # "runaway" when an over-long value was dropped


def clean_value(text: str | None) -> str | None:
    """The text the rules check. Idempotent: cleaning twice gives the same result."""
    if text is None:
        return None
    cleaned = " ".join(to_ascii_digits(unicodedata.normalize("NFC", text)).split())
    cleaned = mask_aadhaar(cleaned)
    return cleaned or None


def _masked(text: str | None) -> str | None:
    return mask_aadhaar(to_ascii_digits(text)) if text is not None else None


def _draft(name: str, index: int | None, value: Field_ | None) -> ClaimDraft:
    if value is None:
        return ClaimDraft(name, index, None, None, None)
    return ClaimDraft(
        field=name,
        index=index,
        value_read=_masked(value.value),
        value=clean_value(value.value),
        box=value.box_2d.as_tuple() if value.box_2d else None,
        flag="runaway" if value.runaway else None,
    )


def drafts_from_read(kind: str, data: object) -> list[ClaimDraft]:
    """One draft per schema field (absent ones with value None) and per line-item field."""
    drafts = [_draft(name, None, getattr(data, name, None)) for name in PAPER_FIELDS[kind]]
    lines: list[LineItem] = list(getattr(data, "line_items", []) or [])
    for index, line in enumerate(lines):
        drafts.extend(_draft(name, index, getattr(line, name, None)) for name in LINE_FIELDS[kind])
    return drafts
