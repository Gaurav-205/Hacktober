"""Data shapes for the verification rules (docs/DOMAIN_RULES.md section 3).

Rules read claims as they stand now (`ClaimValue.text`) and return findings. A finding never
says a value is true: `passed` only means the rule's computation succeeded on the value as read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

__all__ = [
    "CaseState",
    "ClaimValue",
    "FieldRef",
    "Finding",
    "PaperState",
    "Severity",
    "Status",
]


class Status(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    SKIPPED = "skipped"


class Severity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"


@dataclass(frozen=True)
class FieldRef:
    """A field on one paper of the case; `index` is the line number (0-based) for line items.

    `paper_kind` is "invoice", "challan", "po", or "case" for inputs the person types.
    """

    paper_kind: str
    field: str
    index: int | None = None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    status: Status
    severity: Severity
    message_key: str
    params: Mapping[str, str]
    fields: tuple[FieldRef, ...]
    rule_version: str

    @property
    def blocks(self) -> bool:
        """True when this finding stops "Confirm these values" until it is resolved or accepted."""
        return self.severity is Severity.BLOCKING and self.status in (
            Status.FAILED,
            Status.NEEDS_REVIEW,
        )

    @property
    def subject(self) -> tuple[str, tuple[FieldRef, ...]]:
        """What an acceptance is tied to: the rule and the fields it names."""
        return self.rule_id, self.fields


@dataclass(frozen=True)
class ClaimValue:
    """A value as it stands, with where it came from.

    `raw` is the first read (never changed), `text` the current value, `source` one of model,
    repair or user. `flag` carries a review reason stored with the claim: "lookalike" after a
    look-alike repair, "runaway" when the model returned an over-long value.
    """

    raw: str | None
    text: str | None
    source: str
    flag: str | None = None


@dataclass(frozen=True)
class PaperState:
    kind: str
    fields: Mapping[str, ClaimValue]
    lines: tuple[Mapping[str, ClaimValue], ...] = ()


@dataclass(frozen=True)
class CaseState:
    """Everything the rules look at. Papers are keyed by "invoice", "challan" or "po"."""

    papers: Mapping[str, PaperState]
    as_on: date | None = None
    udyam_number: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)
