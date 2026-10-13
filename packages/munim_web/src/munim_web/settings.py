"""The one place that reads the environment (docs/ARCHITECTURE.md, .claude/rules/web-server.md)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Munim's settings. Environment variables use the MUNIM_ prefix (GEMINI_API_KEY excepted)."""

    model_config = SettingsConfigDict(env_prefix="MUNIM_", extra="ignore")

    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8765
    # An explicitly set provider pins the reader; Settings then shows it locked (PLAN_REVIEW D12).
    provider: str | None = None
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4:12b"
    ollama_json_format: bool = False
    gemini_model: str = "gemma-4-31b-it"
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    replay_dir: Path = REPO_ROOT / "eval" / "fixtures" / "replay"
    rules_dir: Path = REPO_ROOT / "rules"
    eval_reports: Path = REPO_ROOT / "eval" / "reports"
    lang: str = "en"
    dev: bool = False
    max_upload_bytes: int = 15 * 1024 * 1024
    allowed_hosts: tuple[str, ...] = ()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "munim.db"

    @property
    def uploads(self) -> Path:
        return self.data_dir / "uploads"

    def hosts(self) -> set[str]:
        """Host header values accepted: loopback names with this port, plus any configured."""
        names = {"127.0.0.1", "localhost", "[::1]", self.host}
        return {f"{n}:{self.port}" for n in names} | set(self.allowed_hosts)


@cache
def get_settings() -> Settings:
    return Settings()
