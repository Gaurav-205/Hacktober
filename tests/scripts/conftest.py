"""Shared helpers for the tests of the scripts in ``scripts/``.

Scripts are run the way ``make`` runs them (a subprocess with the current
interpreter) or imported as modules from their file path, since ``scripts/`` is
not a package.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def run_script(name: str, *args: str | Path) -> subprocess.CompletedProcess[str]:
    """Run ``scripts/<name>.py`` with ``args`` and capture its text output."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / f"{name}.py"), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )


def load_script(name: str) -> ModuleType:
    """Import ``scripts/<name>.py`` as a module (loaded once per test session)."""
    module_name = f"munim_script_{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # dataclasses look the module up while it loads
    spec.loader.exec_module(module)
    return module
