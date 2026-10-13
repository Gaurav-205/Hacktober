"""Hosted Gemma 4 through the Gemini API (docs/AI_SPEC.md 5.2). Off unless the person consents.

The caller checks consent before building this provider. The image is uploaded, read and the
uploaded file is deleted after each call, even when the call fails. The key comes from the
environment and is never logged or stored. The google-genai package is an optional extra
(`munim-ai[gemini]`); tests pass a fake client.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from typing import Any

from munim_ai.prompts import USER_TURN, extraction_prompt, reread_prompt, strict_suffix
from munim_ai.providers.base import (
    PreflightReport,
    ProviderError,
    ProviderResult,
    ProviderUnavailable,
    ReadContext,
)
from munim_ai.schemas import FieldSpec, PaperKind

__all__ = ["GeminiProvider", "QuotaExceeded"]


class QuotaExceeded(ProviderError):
    message_key = "fix.gemini.quota"


class GeminiNotInstalled(ProviderUnavailable):
    message_key = "fix.gemini.install"


def _default_client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as exc:  # the optional extra is not installed
        raise GeminiNotInstalled("install munim-ai[gemini] to use the hosted reader") from exc
    return genai.Client(api_key=api_key)


def _config(system: str, thinking: str) -> Any:
    try:
        from google.genai import types
    except ImportError:
        return {
            "system_instruction": system,
            "temperature": 0,
            "thinking_config": {"thinking_level": thinking},
        }
    return types.GenerateContentConfig(
        system_instruction=system,
        temperature=0,
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
    )


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, *, client: Any = None) -> None:
        if not api_key:
            raise ProviderUnavailable("GEMINI_API_KEY is not set")
        self.model = model
        self._client = client if client is not None else _default_client(api_key)

    async def _generate(
        self, image: bytes, system: str, user: str, thinking: str
    ) -> ProviderResult:
        return await asyncio.to_thread(self._generate_sync, image, system, user, thinking)

    def _generate_sync(self, image: bytes, system: str, user: str, thinking: str) -> ProviderResult:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.jpg"
            path.write_bytes(image)
            uploaded = self._client.files.upload(file=str(path))
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=[uploaded, user], config=_config(system, thinking)
            )
        except Exception as exc:
            if "429" in str(exc) or "quota" in str(exc).lower() or "exhausted" in str(exc).lower():
                raise QuotaExceeded("the hosted reader's quota is used up") from exc
            raise ProviderUnavailable("the hosted reader failed") from exc
        finally:
            self._client.files.delete(name=uploaded.name)
        return ProviderResult(
            text=getattr(response, "text", "") or "",
            latency_ms=round((time.perf_counter() - started) * 1000),
            provider=self.name,
            model=self.model,
        )

    async def extract(
        self, image: bytes, kind: PaperKind, language_hint: str | None, ctx: ReadContext
    ) -> ProviderResult:
        prompt = extraction_prompt(kind).text
        if ctx.attempt > 1:
            prompt = f"{prompt}\n{strict_suffix()}"
        return await self._generate(image, prompt, USER_TURN[kind], "minimal")

    async def reread(self, crop: bytes, field: FieldSpec, ctx: ReadContext) -> ProviderResult:
        return await self._generate(crop, reread_prompt(field).text, "Read this field.", "high")

    async def preflight(self) -> PreflightReport:
        return PreflightReport(self.name, self.model, model_present=True)
