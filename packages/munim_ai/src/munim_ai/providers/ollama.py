"""Local Gemma 4 through Ollama (docs/AI_SPEC.md 5.1), the default reader.

One request at a time (a semaphore: a laptop has memory for one), temperature 0, 90 s for a
read and 45 s for a re-read. Ollama's JSON `format` is used only after the preflight probe shows
it works with this model; otherwise the prompt alone asks for JSON and Pydantic checks it.
"""

from __future__ import annotations

import asyncio
import io
import time
from typing import Any

import httpx
import ollama
from PIL import Image, ImageDraw

from munim_ai.extract import parse_json_object
from munim_ai.prompts import USER_TURN, extraction_prompt, reread_prompt, strict_suffix
from munim_ai.providers.base import (
    PreflightReport,
    ProviderResult,
    ProviderTimeout,
    ProviderUnavailable,
    ReadContext,
)
from munim_ai.schemas import FieldSpec, PaperKind

__all__ = ["OllamaProvider"]

READ_TIMEOUT_S = 240.0
REREAD_TIMEOUT_S = 90.0
PROBE_TEXT = "INV-0042"


class ModelMissing(ProviderUnavailable):
    message_key = "fix.ollama.model"


def probe_image() -> bytes:
    """A 200 x 60 image with INV-0042 printed on it, for the vision probe."""
    image = Image.new("RGB", (200, 60), "white")
    ImageDraw.Draw(image).text((20, 20), PROBE_TEXT, fill="black", font_size=24)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        host: str,
        model: str,
        *,
        use_format: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.host = host
        self.model = model
        self.use_format = use_format
        self._transport = transport
        self._lock: asyncio.Semaphore | None = None

    def _client(self, timeout: float) -> ollama.AsyncClient:
        kwargs: dict[str, Any] = {"timeout": timeout}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return ollama.AsyncClient(host=self.host, **kwargs)

    def _semaphore(self) -> asyncio.Semaphore:
        if self._lock is None:
            self._lock = asyncio.Semaphore(1)
        return self._lock

    async def _chat(
        self, system: str, user: str, image: bytes, timeout: float, use_format: bool
    ) -> ProviderResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user, "images": [image]},
        ]
        started = time.perf_counter()
        async with self._semaphore():
            try:
                response = await self._client(timeout).chat(
                    model=self.model,
                    messages=messages,
                    options={"temperature": 0},
                    format="json" if use_format else None,
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeout(f"no answer within {timeout:g} s") from exc
            except (httpx.ConnectError, httpx.NetworkError, ConnectionError) as exc:
                raise ProviderUnavailable(f"cannot reach Ollama at {self.host}") from exc
            except ollama.ResponseError as exc:
                if exc.status_code == 404:
                    raise ModelMissing(f"model {self.model} is not pulled") from exc
                raise ProviderUnavailable(f"Ollama answered {exc.status_code}") from exc
        elapsed = round((time.perf_counter() - started) * 1000)
        usage = {
            k: int(v)
            for k in ("prompt_eval_count", "eval_count")
            if isinstance(v := getattr(response, k, None), int)
        }
        return ProviderResult(
            text=response.message.content or "",
            latency_ms=elapsed,
            provider=self.name,
            model=self.model,
            usage=usage or None,
        )

    async def extract(
        self, image: bytes, kind: PaperKind, language_hint: str | None, ctx: ReadContext
    ) -> ProviderResult:
        prompt = extraction_prompt(kind).text
        if ctx.attempt > 1:
            prompt = f"{prompt}\n{strict_suffix()}"
        return await self._chat(prompt, USER_TURN[kind], image, READ_TIMEOUT_S, self.use_format)

    async def reread(self, crop: bytes, field: FieldSpec, ctx: ReadContext) -> ProviderResult:
        prompt = reread_prompt(field).text
        return await self._chat(prompt, "Read this field.", crop, REREAD_TIMEOUT_S, self.use_format)

    async def preflight(self) -> PreflightReport:
        """Is Ollama up, is the model pulled, can it see, does JSON `format` work?"""
        params = {"url": self.host, "model": self.model}
        try:
            listing = await self._client(10.0).list()
        except (httpx.HTTPError, ollama.ResponseError, ConnectionError):
            return PreflightReport(
                self.name, self.model, False, problems=("fix.ollama.down",), params=params
            )
        names = {m.model for m in listing.models if m.model}
        present = self.model in names or f"{self.model}:latest" in names
        if not present:
            return PreflightReport(
                self.name, self.model, False, problems=("fix.ollama.model",), params=params
            )
        started = time.perf_counter()
        problems: list[str] = []
        try:
            seen = await self._chat(
                'Read the text in this image. Return JSON {"text": "<the text>"}.',
                "What does it say?",
                probe_image(),
                READ_TIMEOUT_S,
                False,
            )
            vision_ok = "0042" in seen.text
            as_json = await self._chat(
                'Return JSON {"ok": true} and nothing else.',
                "Answer.",
                probe_image(),
                READ_TIMEOUT_S,
                True,
            )
            parsed = parse_json_object(as_json.text)
            json_ok = bool(parsed and parsed.get("ok") is True)
        except (ProviderTimeout, ProviderUnavailable):
            return PreflightReport(
                self.name, self.model, True, problems=("fix.ollama.slow",), params=params
            )
        if not vision_ok:
            problems.append("fix.ollama.vision")
        return PreflightReport(
            provider=self.name,
            model=self.model,
            model_present=True,
            vision_ok=vision_ok,
            json_format_ok=json_ok,
            latency_ms=round((time.perf_counter() - started) * 1000),
            problems=tuple(problems),
            params=params,
        )
