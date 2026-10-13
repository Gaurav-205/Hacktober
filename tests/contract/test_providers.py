"""Provider contract (docs/AI_SPEC.md 5, docs/TESTING.md 4, PLAN_REVIEW D9).

The same contract runs against ReplayProvider and OllamaProvider over a fake Ollama served by
an httpx MockTransport. Gemini runs against a fake client. No network is used.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from munim_ai.prompts import extraction_prompt, strict_suffix
from munim_ai.providers import ProviderTimeout, ProviderUnavailable, ReadContext, make_provider
from munim_ai.providers.base import replay_filename, replay_key
from munim_ai.providers.gemini import GeminiProvider, QuotaExceeded
from munim_ai.providers.ollama import ModelMissing, OllamaProvider
from munim_ai.providers.replay import (
    RecordingProvider,
    ReplayMiss,
    ReplayProvider,
    write_recording,
)
from munim_ai.schemas import field_spec

pytestmark = pytest.mark.contract

IMAGE = b"\xff\xd8\xff synthetic jpeg bytes"
ANSWER = '{"invoice_total": {"value": "5,00,000.00", "box_2d": null}}'
CTX = ReadContext(original_sha256="ab" * 32, kind="invoice", prompt_version="1")
MODEL = "gemma4:e4b"


# ---------------------------------------------------------------- fake Ollama
class FakeOllama:
    """Serves /api/tags and /api/chat; records requests and the peak concurrency."""

    def __init__(self, answer: str = ANSWER, *, models: tuple[str, ...] = (MODEL,)) -> None:
        self.answer: str | Callable[[dict[str, Any]], str] = answer
        self.models = models
        self.requests: list[dict[str, Any]] = []
        self.status = 200
        self.error: Exception | None = None
        self.gate: asyncio.Event | None = None
        self.active = 0
        self.peak = 0

    async def handle(self, request: httpx.Request) -> httpx.Response:
        if self.error is not None:
            raise self.error
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"model": m, "name": m} for m in self.models]}
            )
        body = json.loads(request.content)
        self.requests.append(body)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if self.gate is not None:
                await self.gate.wait()
            if self.status != 200:
                return httpx.Response(self.status, json={"error": "model not found"})
            text = self.answer(body) if callable(self.answer) else self.answer
            return httpx.Response(
                200,
                json={
                    "model": body["model"],
                    "created_at": "2026-10-13T00:00:00Z",
                    "message": {"role": "assistant", "content": text},
                    "done": True,
                    "prompt_eval_count": 10,
                    "eval_count": 5,
                },
            )
        finally:
            self.active -= 1

    def provider(self, **kw: Any) -> OllamaProvider:
        return OllamaProvider(
            "http://127.0.0.1:11434", MODEL, transport=httpx.MockTransport(self.handle), **kw
        )


# ---------------------------------------------------------------- shared contract
@pytest.fixture(params=["replay", "ollama"])
def provider_under_test(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    if request.param == "replay":
        write_recording(
            tmp_path, CTX, ANSWER, provider="synthetic", model="none", recorded_from="synthetic"
        )
        reread_ctx = CTX.for_reread("buyer_gstin", (1, 2, 3, 4), "1")
        write_recording(
            tmp_path,
            reread_ctx,
            '{"value": "x"}',
            provider="synthetic",
            model="none",
            recorded_from="synthetic",
        )
        return ReplayProvider(tmp_path)
    return FakeOllama().provider()


async def test_contract_extract_returns_the_text_and_provenance(provider_under_test: Any) -> None:
    result = await provider_under_test.extract(IMAGE, "invoice", None, CTX)
    assert result.text == ANSWER
    assert result.provider == provider_under_test.name
    assert result.latency_ms >= 0
    if provider_under_test.name == "replay":
        assert (result.replayed, result.recorded_from) == (True, "synthetic")
    else:
        assert (result.replayed, result.model) == (False, MODEL)
        assert result.usage == {"prompt_eval_count": 10, "eval_count": 5}


async def test_contract_reread_returns_text(provider_under_test: Any) -> None:
    ctx = CTX.for_reread("buyer_gstin", (1, 2, 3, 4), "1")
    result = await provider_under_test.reread(IMAGE, field_spec("buyer_gstin"), ctx)
    assert isinstance(result.text, str) and result.text


# ---------------------------------------------------------------- replay
def test_replay_key_is_built_from_the_original_bytes_and_every_read_detail() -> None:
    assert replay_key(CTX) == f"{'ab' * 32}:invoice:1:r0:a1"
    reread = CTX.for_reread("buyer_gstin", (1, 2, 3, 4), "2")
    assert replay_key(reread) == f"{'ab' * 32}:invoice:2:r0:a1:buyer_gstin:1,2,3,4"
    variants = {
        replay_filename(CTX),
        replay_filename(ReadContext(CTX.original_sha256, "invoice", "1", attempt=2)),
        replay_filename(ReadContext(CTX.original_sha256, "invoice", "2")),
        replay_filename(ReadContext(CTX.original_sha256, "invoice", "1", rotation=90)),
        replay_filename(ReadContext(CTX.original_sha256, "challan", "1")),
        replay_filename(reread),
    }
    assert len(variants) == 6


async def test_replay_raises_on_a_missing_recording(tmp_path: Path) -> None:
    with pytest.raises(ReplayMiss) as info:
        await ReplayProvider(tmp_path).extract(IMAGE, "invoice", None, CTX)
    assert info.value.message_key == "error.replay_miss"


async def test_replay_refuses_a_recording_whose_key_does_not_match(tmp_path: Path) -> None:
    path = write_recording(tmp_path, CTX, ANSWER, provider="p", model="m", recorded_from="live")
    record = json.loads(path.read_text())
    record["key"] = "something else"
    path.write_text(json.dumps(record))
    with pytest.raises(ReplayMiss):
        await ReplayProvider(tmp_path).extract(IMAGE, "invoice", None, CTX)


async def test_recording_provider_writes_live_recordings_that_replay(tmp_path: Path) -> None:
    recorder = RecordingProvider(FakeOllama().provider(), tmp_path)
    live = await recorder.extract(IMAGE, "invoice", None, CTX)
    replayed = await ReplayProvider(tmp_path).extract(IMAGE, "invoice", None, CTX)
    assert replayed.text == live.text
    assert (replayed.provider, replayed.recorded_from, replayed.model) == ("replay", "live", MODEL)


async def test_replay_preflight_reports_an_empty_directory(tmp_path: Path) -> None:
    report = await ReplayProvider(tmp_path / "none").preflight()
    assert not report.ok
    assert report.problems == ("error.replay_empty",)


# ---------------------------------------------------------------- Ollama
async def test_ollama_sends_temperature_zero_and_the_image() -> None:
    fake = FakeOllama()
    await fake.provider().extract(IMAGE, "invoice", None, CTX)
    body = fake.requests[0]
    assert body["options"]["temperature"] == 0
    assert body["messages"][0]["content"] == extraction_prompt("invoice").text
    assert base64.b64decode(body["messages"][1]["images"][0]) == IMAGE
    assert body.get("format") in (None, "")


async def test_ollama_json_format_only_when_enabled_and_strict_suffix_on_retry() -> None:
    fake = FakeOllama()
    retry = ReadContext(CTX.original_sha256, "invoice", "1", attempt=2)
    await fake.provider(use_format=True).extract(IMAGE, "invoice", None, retry)
    body = fake.requests[0]
    assert body["format"] == "json"
    assert body["messages"][0]["content"].endswith(strict_suffix())


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ReadTimeout("slow"), ProviderTimeout),
        (httpx.ConnectError("refused"), ProviderUnavailable),
    ],
)
async def test_ollama_network_failures_become_provider_errors(
    error: Exception, expected: type
) -> None:
    fake = FakeOllama()
    fake.error = error
    with pytest.raises(expected):
        await fake.provider().extract(IMAGE, "invoice", None, CTX)


async def test_ollama_missing_model_and_server_error() -> None:
    fake = FakeOllama()
    fake.status = 404
    with pytest.raises(ModelMissing) as info:
        await fake.provider().extract(IMAGE, "invoice", None, CTX)
    assert info.value.message_key == "fix.ollama.model"
    fake.status = 500
    with pytest.raises(ProviderUnavailable):
        await fake.provider().extract(IMAGE, "invoice", None, CTX)


async def test_ollama_runs_one_request_at_a_time() -> None:
    fake = FakeOllama()
    fake.gate = asyncio.Event()
    provider = fake.provider()
    tasks = [asyncio.create_task(provider.extract(IMAGE, "invoice", None, CTX)) for _ in range(3)]
    while not fake.requests:
        await asyncio.sleep(0)
    for _ in range(20):
        await asyncio.sleep(0)
    assert fake.active == 1
    fake.gate.set()
    await asyncio.gather(*tasks)
    assert fake.peak == 1
    assert len(fake.requests) == 3


def probe_answers(vision: str, as_json: str) -> Callable[[dict[str, Any]], str]:
    def answer(body: dict[str, Any]) -> str:
        return as_json if body.get("format") == "json" else vision

    return answer


async def test_ollama_preflight_ok() -> None:
    fake = FakeOllama()
    fake.answer = probe_answers('{"text": "INV-0042"}', '{"ok": true}')
    report = await fake.provider().preflight()
    assert report.ok
    assert (report.vision_ok, report.json_format_ok) == (True, True)


async def test_ollama_preflight_reports_each_problem() -> None:
    blind = FakeOllama()
    blind.answer = probe_answers('{"text": "nothing"}', "not json")
    report = await blind.provider().preflight()
    assert report.problems == ("fix.ollama.vision",)
    assert report.json_format_ok is False

    missing = FakeOllama(models=("llama3:latest",))
    assert (await missing.provider().preflight()).problems == ("fix.ollama.model",)

    down = FakeOllama()
    down.error = httpx.ConnectError("refused")
    assert (await down.provider().preflight()).problems == ("fix.ollama.down",)


# ---------------------------------------------------------------- Gemini
class FakeFiles:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def upload(self, *, file: str) -> Any:
        self.calls.append("upload")
        assert Path(file).read_bytes() == IMAGE
        return type("Uploaded", (), {"name": "files/synthetic-1"})()

    def delete(self, *, name: str) -> None:
        self.calls.append(f"delete:{name}")


class FakeModels:
    def __init__(self, files: FakeFiles, error: Exception | None) -> None:
        self.files, self.error = files, error
        self.config: Any = None

    def generate_content(self, *, model: str, contents: list[Any], config: Any) -> Any:
        self.files.calls.append("generate")
        self.config = config
        if self.error:
            raise self.error
        return type("Response", (), {"text": ANSWER})()


class FakeClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.files = FakeFiles()
        self.models = FakeModels(self.files, error)


async def test_gemini_uploads_generates_then_deletes() -> None:
    client = FakeClient()
    result = await GeminiProvider("k", "gemma-4-31b-it", client=client).extract(
        IMAGE, "invoice", None, CTX
    )
    assert result.text == ANSWER
    assert (result.provider, result.model) == ("gemini", "gemma-4-31b-it")
    assert client.files.calls == ["upload", "generate", "delete:files/synthetic-1"]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (RuntimeError("429 RESOURCE_EXHAUSTED"), QuotaExceeded),
        (RuntimeError("500 internal"), ProviderUnavailable),
    ],
)
async def test_gemini_deletes_the_upload_even_when_the_call_fails(
    error: Exception, expected: type
) -> None:
    secret = "synthetic-key-value"  # pragma: allowlist secret
    client = FakeClient(error)
    with pytest.raises(expected) as info:
        await GeminiProvider(secret, "m", client=client).reread(
            IMAGE, field_spec("buyer_gstin"), CTX
        )
    assert client.files.calls[-1] == "delete:files/synthetic-1"
    assert secret not in str(info.value) and secret not in repr(info.value)


def test_gemini_needs_a_key() -> None:
    with pytest.raises(ProviderUnavailable):
        GeminiProvider("", "m", client=FakeClient())


# ---------------------------------------------------------------- factory
def test_make_provider_builds_each_reader(tmp_path: Path) -> None:
    common = {
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_model": MODEL,
        "gemini_model": "m",
        "gemini_key": None,
        "replay_dir": tmp_path,
    }
    assert make_provider("ollama", **common).name == "ollama"
    assert make_provider("replay", **common).name == "replay"
    with pytest.raises(ProviderUnavailable):
        make_provider("gemini", **common)
    with pytest.raises(ValueError):
        make_provider("other", **common)
