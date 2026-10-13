"""The one interface every reader implements (docs/ARCHITECTURE.md 6, PLAN_REVIEW D9).

Live providers ignore the read context; the replay and record providers use it to key
recordings on the original uploaded bytes, never on re-encoded ones.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from munim_ai.schemas import FieldSpec, PaperKind

__all__ = [
    "PreflightReport",
    "Provider",
    "ProviderError",
    "ProviderResult",
    "ProviderTimeout",
    "ProviderUnavailable",
    "ReadContext",
    "replay_key",
]


class ProviderError(Exception):
    """The reader failed. `message_key` names the i18n message the UI shows."""

    message_key = "error.provider"


class ProviderUnavailable(ProviderError):
    """The reader cannot be reached or the model is missing."""

    message_key = "fix.ollama.down"


class ProviderTimeout(ProviderError):
    message_key = "error.provider_timeout"


@dataclass(frozen=True)
class ReadContext:
    """What a read is about, for replay keys and provenance. Never sent to a model."""

    original_sha256: str
    kind: PaperKind
    prompt_version: str
    rotation: int = 0
    attempt: int = 1  # 2 is the strict retry
    field: str | None = None  # set for a single-field re-read
    box: tuple[int, int, int, int] | None = None

    def for_reread(
        self, field_name: str, box: tuple[int, int, int, int] | None, prompt_version: str
    ) -> ReadContext:
        return ReadContext(
            original_sha256=self.original_sha256,
            kind=self.kind,
            prompt_version=prompt_version,
            rotation=self.rotation,
            attempt=1,
            field=field_name,
            box=box,
        )


def replay_key(ctx: ReadContext) -> str:
    """The recording key: sha256 of the original bytes, kind, prompt version, rotation, attempt,
    and for a re-read the field and box (AI_SPEC 5.3 with PLAN_REVIEW D9)."""
    parts = [
        ctx.original_sha256,
        ctx.kind,
        ctx.prompt_version,
        f"r{ctx.rotation}",
        f"a{ctx.attempt}",
    ]
    if ctx.field is not None:
        box = ",".join(str(v) for v in ctx.box) if ctx.box else "none"
        parts += [ctx.field, box]
    return ":".join(parts)


def replay_filename(ctx: ReadContext) -> str:
    """A file-system-safe name for a recording: the sha256 of its key."""
    return hashlib.sha256(replay_key(ctx).encode("utf-8")).hexdigest() + ".json"


@dataclass(frozen=True)
class ProviderResult:
    text: str
    latency_ms: int
    provider: str
    model: str
    usage: dict[str, int] | None = None
    replayed: bool = False
    recorded_from: Literal["synthetic", "live"] | None = None


@dataclass(frozen=True)
class PreflightReport:
    """Whether the reader is usable, with message keys for each problem (shown on Settings)."""

    provider: str
    model: str
    model_present: bool
    vision_ok: bool | None = None
    json_format_ok: bool | None = None
    latency_ms: int | None = None
    problems: tuple[str, ...] = ()
    params: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.model_present and not self.problems


@runtime_checkable
class Provider(Protocol):
    name: str
    model: str

    async def extract(
        self, image: bytes, kind: PaperKind, language_hint: str | None, ctx: ReadContext
    ) -> ProviderResult: ...

    async def reread(self, crop: bytes, field: FieldSpec, ctx: ReadContext) -> ProviderResult: ...

    async def preflight(self) -> PreflightReport: ...
