"""Vercel ASGI serverless entry point for Munim's hosted demo.

The hosted copy is a demo: the reader is pinned to recorded responses (no Ollama on Vercel,
and no visitor photos sent on to Google), and only this deployment's own hostnames pass the
Host check (docs/SECURITY_PRIVACY.md, DNS rebinding).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

# Compute repository root
ROOT = Path(__file__).resolve().parent.parent

# Add workspace packages to Python path
for pkg in ("munim_core", "munim_ai", "munim_web", "munim_mcp"):
    src_dir = str(ROOT / "packages" / pkg / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

DEMO_HOST = "munim-demo.vercel.app"
# Hostnames Vercel sets for a deployment, then a comma-separated override for a custom domain.
HOST_VARS = (
    "VERCEL_URL",
    "VERCEL_BRANCH_URL",
    "VERCEL_PROJECT_PRODUCTION_URL",
    "MUNIM_PUBLIC_HOST",
)


def deploy_hosts(env: Mapping[str, str]) -> tuple[str, ...]:
    """Host header values the demo accepts: the demo domain plus the deployment's own names."""
    hosts = {DEMO_HOST}
    for var in HOST_VARS:
        for raw in env.get(var, "").split(","):
            name = raw.strip().lower()
            if name and name != "*":
                hosts.add(name)
    return tuple(sorted(hosts))


# Vercel serverless has a writable ephemeral directory at /tmp
data_dir_env = os.environ.get("MUNIM_DATA_DIR", "/tmp/munim_data")  # noqa: S108  # nosec B108
data_dir = Path(data_dir_env)
data_dir.mkdir(parents=True, exist_ok=True)

from munim_web.main import create_app  # noqa: E402
from munim_web.settings import Settings  # noqa: E402

settings = Settings(
    data_dir=data_dir,
    rules_dir=ROOT / "rules",
    replay_dir=ROOT / "eval" / "fixtures" / "replay",
    provider="replay",
    allowed_hosts=deploy_hosts(os.environ),
)

app = create_app(settings)
