"""The hosted demo entry point (api/index.py): own hosts only, reader pinned to replay."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.integration


def _load_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str) -> ModuleType:
    monkeypatch.setenv("MUNIM_DATA_DIR", str(tmp_path))
    for name in (
        "MUNIM_PUBLIC_HOST",
        "VERCEL_URL",
        "VERCEL_BRANCH_URL",
        "VERCEL_PROJECT_PRODUCTION_URL",
        "MUNIM_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("munim_vercel_entry", ROOT / "api" / "index.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_host_is_the_demo_domain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = _load_entry(monkeypatch, tmp_path)
    assert entry.deploy_hosts({}) == ("munim-demo.vercel.app",)


def test_vercel_and_override_hosts_are_added(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entry = _load_entry(monkeypatch, tmp_path)
    hosts = entry.deploy_hosts(
        {
            "MUNIM_PUBLIC_HOST": "Munim.example.in, www.munim.example.in",
            "VERCEL_URL": "munim-demo-abc123.vercel.app",
            "VERCEL_PROJECT_PRODUCTION_URL": "munim-demo.vercel.app",
            "VERCEL_BRANCH_URL": "",
        }
    )
    assert hosts == (
        "munim-demo-abc123.vercel.app",
        "munim-demo.vercel.app",
        "munim.example.in",
        "www.munim.example.in",
    )
    assert "*" not in hosts


def test_wildcard_is_never_accepted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = _load_entry(monkeypatch, tmp_path)
    assert entry.deploy_hosts({"MUNIM_PUBLIC_HOST": "*"}) == ("munim-demo.vercel.app",)


def test_foreign_host_is_refused_and_reader_is_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entry = _load_entry(monkeypatch, tmp_path, VERCEL_URL="munim-demo-abc123.vercel.app")
    assert entry.settings.provider == "replay"
    with TestClient(entry.app, base_url="https://munim-demo.vercel.app") as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["provider"] == "replay"
        own = client.get("/healthz", headers={"host": "munim-demo-abc123.vercel.app"})
        assert own.status_code == 200
        refused = client.get("/healthz", headers={"host": "evil.example"})
        assert refused.status_code == 400
        assert refused.content == b"Bad Host header"


def test_provider_env_cannot_unpin_replay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = _load_entry(monkeypatch, tmp_path, MUNIM_PROVIDER="gemini")
    assert entry.settings.provider == "replay"
