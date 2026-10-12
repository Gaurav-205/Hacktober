"""Shared fixtures for the Claude Code hook script tests (scripts/hooks/).

The hooks are run the way Claude Code runs them: as a separate process with the hook JSON on
stdin. CLAUDE_PROJECT_DIR and MUNIM_HOOK_UV are removed from the inherited environment and
set explicitly per test, so the caller's session cannot change what a test sees.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "scripts" / "hooks"
HOOK_ENV_VARS = ("CLAUDE_PROJECT_DIR", "MUNIM_HOOK_UV")

RunHook = Callable[..., subprocess.CompletedProcess[str]]
LoadHook = Callable[[str], ModuleType]


def _run_hook(
    name: str,
    payload: object,
    *,
    project: Path | None,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run scripts/hooks/<name>.py with the payload on stdin (a str is sent as is)."""
    environment = {key: value for key, value in os.environ.items() if key not in HOOK_ENV_VARS}
    if project is not None:
        environment["CLAUDE_PROJECT_DIR"] = str(project)
    if env is not None:
        environment.update(env)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / f"{name}.py")],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=environment,
        check=False,
        timeout=120,
    )


def _load_hook(name: str) -> ModuleType:
    """Import scripts/hooks/<name>.py as a module."""
    module_name = f"munim_hook_{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, HOOKS_DIR / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # dataclasses look the module up while it loads
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run_hook() -> RunHook:
    """Return a function that runs a hook script as a subprocess."""
    return _run_hook


@pytest.fixture
def load_hook() -> LoadHook:
    """Return a function that imports a hook script as a module."""
    return _load_hook
