"""Recorded responses (docs/AI_SPEC.md 5.3): the CI provider and the labelled demo fallback.

A recording is `<dir>/<sha256 of the key>.json` holding {key, text, provider, model,
recorded_at, recorded_from, latency_ms}. The key comes from the read context (original bytes,
kind, prompt version, rotation, attempt, and for re-reads the field and box). A missing
recording raises ReplayMiss; replay never falls back to anything else. Results always say
provider "replay", so a replay is never shown as a live read.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from munim_ai.providers.base import (
    PreflightReport,
    Provider,
    ProviderError,
    ProviderResult,
    ReadContext,
    replay_filename,
    replay_key,
)
from munim_ai.schemas import FieldSpec, PaperKind

__all__ = ["RecordingProvider", "ReplayMiss", "ReplayProvider", "write_recording"]


class ReplayMiss(ProviderError):
    """No recording exists for this read."""

    message_key = "error.replay_miss"


def write_recording(
    directory: Path,
    ctx: ReadContext,
    text: str,
    *,
    provider: str,
    model: str,
    recorded_from: Literal["synthetic", "live"],
    latency_ms: int | None = None,
    recorded_at: str | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / replay_filename(ctx)
    record = {
        "key": replay_key(ctx),
        "text": text,
        "provider": provider,
        "model": model,
        "recorded_at": recorded_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "recorded_from": recorded_from,
        "latency_ms": latency_ms,
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


class ReplayProvider:
    name = "replay"

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.model = "recorded"

    def _load(self, ctx: ReadContext) -> ProviderResult:
        path = self.directory / replay_filename(ctx)
        if not path.is_file():
            raise ReplayMiss(f"no recording for {ctx.kind} read (attempt {ctx.attempt})")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("key") != replay_key(ctx):
            raise ReplayMiss("recording key does not match")
        recorded_from = record.get("recorded_from")
        return ProviderResult(
            text=str(record["text"]),
            latency_ms=0,
            provider=self.name,
            model=str(record.get("model", "recorded")),
            replayed=True,
            recorded_from=recorded_from if recorded_from in ("synthetic", "live") else None,
        )

    async def extract(
        self, image: bytes, kind: PaperKind, language_hint: str | None, ctx: ReadContext
    ) -> ProviderResult:
        return self._load(ctx)

    async def reread(self, crop: bytes, field: FieldSpec, ctx: ReadContext) -> ProviderResult:
        return self._load(ctx)

    async def preflight(self) -> PreflightReport:
        present = self.directory.is_dir() and any(self.directory.glob("*.json"))
        problems = () if present else ("error.replay_empty",)
        return PreflightReport(
            provider=self.name,
            model=self.model,
            model_present=present,
            vision_ok=None,
            json_format_ok=None,
            problems=problems,
        )


class RecordingProvider:
    """Wraps a live provider and writes every response as a "live" recording."""

    def __init__(self, inner: Provider, directory: Path) -> None:
        self.inner = inner
        self.directory = directory
        self.name = inner.name
        self.model = inner.model

    async def extract(
        self, image: bytes, kind: PaperKind, language_hint: str | None, ctx: ReadContext
    ) -> ProviderResult:
        result = await self.inner.extract(image, kind, language_hint, ctx)
        self._save(ctx, result)
        return result

    async def reread(self, crop: bytes, field: FieldSpec, ctx: ReadContext) -> ProviderResult:
        result = await self.inner.reread(crop, field, ctx)
        self._save(ctx, result)
        return result

    async def preflight(self) -> PreflightReport:
        return await self.inner.preflight()

    def _save(self, ctx: ReadContext, result: ProviderResult) -> None:
        write_recording(
            self.directory,
            ctx,
            result.text,
            provider=result.provider,
            model=result.model,
            recorded_from="live",
            latency_ms=result.latency_ms,
        )
