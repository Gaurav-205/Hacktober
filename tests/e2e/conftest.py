"""A live Munim server on a free loopback port, with a temporary data folder and replay."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn

from munim_web.main import create_app
from munim_web.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "eval" / "fixtures" / "demo"
SCREENS = ROOT / "docs" / "screens"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def serve(settings: Settings) -> Iterator[str]:
    port = settings.port
    config = uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/healthz").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)  # waiting for the socket to open, not for app state
    yield url
    srv.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def server(tmp_path: Path) -> Iterator[str]:
    yield from serve(
        Settings(
            data_dir=tmp_path,
            port=free_port(),
            provider="replay",
            replay_dir=ROOT / "eval/fixtures/replay",
        )
    )


@pytest.fixture
def server_without_ollama(tmp_path: Path) -> Iterator[str]:
    """The local reader pointed at a loopback port where nothing listens."""
    yield from serve(
        Settings(
            data_dir=tmp_path,
            port=free_port(),
            provider="ollama",
            ollama_url=f"http://127.0.0.1:{free_port()}",
        )
    )
