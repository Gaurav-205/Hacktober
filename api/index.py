"""Vercel ASGI serverless entry point for Munim."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Compute repository root
ROOT = Path(__file__).resolve().parent.parent

# Add workspace packages to Python path
for pkg in ("munim_core", "munim_ai", "munim_web", "munim_mcp"):
    src_dir = str(ROOT / "packages" / pkg / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

# Vercel serverless has a writable ephemeral directory at /tmp
data_dir_env = os.environ.get("MUNIM_DATA_DIR", "/tmp/munim_data")  # noqa: S108
data_dir = Path(data_dir_env)
data_dir.mkdir(parents=True, exist_ok=True)

from munim_web.main import create_app  # noqa: E402
from munim_web.settings import Settings  # noqa: E402

settings = Settings(
    data_dir=data_dir,
    rules_dir=ROOT / "rules",
    replay_dir=ROOT / "eval" / "fixtures" / "replay",
    allowed_hosts=("*",),
)

app = create_app(settings)
