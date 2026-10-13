"""Readers: local Ollama (default), hosted Gemini (with consent) and recorded replay."""

from __future__ import annotations

from pathlib import Path

from munim_ai.providers.base import (
    PreflightReport,
    Provider,
    ProviderError,
    ProviderResult,
    ProviderTimeout,
    ProviderUnavailable,
    ReadContext,
    replay_key,
)

__all__ = [
    "PreflightReport",
    "Provider",
    "ProviderError",
    "ProviderResult",
    "ProviderTimeout",
    "ProviderUnavailable",
    "ReadContext",
    "make_provider",
    "replay_key",
]


def make_provider(
    name: str,
    *,
    ollama_url: str,
    ollama_model: str,
    gemini_model: str,
    gemini_key: str | None,
    replay_dir: Path,
    use_json_format: bool = False,
) -> Provider:
    """Build the reader by name. Consent for the hosted reader is checked by the caller."""
    if name == "ollama":
        from munim_ai.providers.ollama import OllamaProvider

        return OllamaProvider(ollama_url, ollama_model, use_format=use_json_format)
    if name == "gemini":
        from munim_ai.providers.gemini import GeminiProvider

        return GeminiProvider(gemini_key or "", gemini_model)
    if name == "replay":
        from munim_ai.providers.replay import ReplayProvider

        return ReplayProvider(replay_dir)
    raise ValueError(f"unknown reader {name!r}")
