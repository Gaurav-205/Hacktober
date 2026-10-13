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

__all__ = ["GeminiKeyMissing", "GeminiProvider", "GeminiUnavailable", "QuotaExceeded"]


class QuotaExceeded(ProviderError):
    message_key = "fix.gemini.quota"


class GeminiNotInstalled(ProviderUnavailable):
    message_key = "fix.gemini.install"


class GeminiUnavailable(ProviderUnavailable):
    message_key = "fix.gemini.down"


class GeminiKeyMissing(ProviderUnavailable):
    message_key = "fix.gemini.key"


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
            "response_mime_type": "application/json",
        }
    return types.GenerateContentConfig(
        system_instruction=system,
        temperature=0,
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
        response_mime_type="application/json",
    )


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, *, client: Any = None) -> None:
        if not api_key:
            raise GeminiKeyMissing("GEMINI_API_KEY is not set")
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
            last_exc: Exception | None = None
            response = None
            for attempt in range(3):
                try:
                    response = self._client.models.generate_content(
                        model=self.model,
                        contents=[uploaded, user],
                        config=_config(system, thinking),
                    )
                    break
                except Exception as exc:
                    last_exc = exc
                    msg = str(exc).lower()
                    if "429" in msg or "quota" in msg or "exhausted" in msg:
                        raise QuotaExceeded("the hosted reader's quota is used up") from exc
                    is_transient = any(
                        t in msg
                        for t in (
                            "500",
                            "503",
                            "high demand",
                            "overloaded",
                            "server error",
                            "unavailable",
                            "internal",
                        )
                    )
                    if is_transient and attempt < 2:
                        time.sleep(0.5 * (2**attempt))
                        continue
                    raise GeminiUnavailable("the hosted reader failed") from exc
            if response is None and last_exc is not None:
                raise GeminiUnavailable("the hosted reader failed") from last_exc
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
