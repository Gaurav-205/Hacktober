"""Tests for scripts/check_licences.py (licence allow-list and THIRD_PARTY coverage)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_licences.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_licences", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_licences"] = module
    spec.loader.exec_module(module)
    return module


lic = load()
Dist = lic.Distribution


@pytest.mark.parametrize(
    "dist",
    [
        Dist("fastapi", expression="MIT"),
        Dist("packaging", expression="Apache-2.0 OR BSD-2-Clause"),
        Dist("greenlet", expression="MIT AND PSF-2.0"),
        Dist("pillow", expression="MIT-CMU"),
        Dist("certifi", license_text="MPL-2.0"),
        Dist("jinja2", classifiers=("BSD License",)),
        Dist("detect-secrets", license_text="UNKNOWN", classifiers=("Apache Software License",)),
        Dist("python-dateutil", license_text="Dual License", classifiers=("BSD License",)),
        Dist("axe-playwright-python", license_file_head="MIT License\n\nCopyright (c) 2022"),
        Dist("python-stdnum", license_text="LGPL", classifiers=("GNU Lesser General Public",)),
        Dist("munim-core", expression="Apache-2.0"),
    ],
)
def test_allowed_licences_pass(dist: object) -> None:
    assert lic.check_distribution(dist) is None


@pytest.mark.parametrize(
    ("dist", "fragment"),
    [
        (Dist("somegpl", license_text="GPL-3.0"), "somegpl: licence ['GPL']"),
        (Dist("agpl-thing", expression="AGPL-3.0-only"), "agpl-thing: licence expression"),
        (Dist("lgpl-elsewhere", license_text="LGPL"), "lgpl-elsewhere: licence"),
        (Dist("both-needed", expression="MIT AND GPL-3.0-only"), "both-needed: licence expression"),
        (Dist("mystery"), "mystery: no licence found"),
    ],
)
def test_disallowed_or_unknown_licences_fail(dist: object, fragment: str) -> None:
    problem = lic.check_distribution(dist)
    assert problem is not None and problem.startswith("L1: ")
    assert fragment in problem


def test_documented_exception_passes() -> None:
    dist = Dist("text-unidecode", license_text="Artistic License", classifiers=("GPL",))
    assert lic.check_distribution(dist) is None
    assert "adr/0007" in lic.EXCEPTIONS["text-unidecode"]


def make_repo(tmp_path: Path, third_party: str, extra_deps: str = "") -> Path:
    (tmp_path / "packages" / "p").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "root"\ndependencies = ["munim-core"]\n'
        f'[dependency-groups]\ndev = ["pytest>=8", "pypdf>=5"{extra_deps}]\n'
    )
    (tmp_path / "packages" / "p" / "pyproject.toml").write_text(
        '[project]\nname = "p"\ndependencies = ["fastapi>=0.1", "python_multipart"]\n'
        '[project.optional-dependencies]\ngemini = ["google-genai>=1"]\n'
    )
    (tmp_path / "THIRD_PARTY.md").write_text(third_party)
    return tmp_path


def test_declared_dependencies_are_collected(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "")
    assert lic.declared_dependencies(root) == {
        "pytest",
        "pypdf",
        "fastapi",
        "python-multipart",
        "google-genai",
    }


def test_dependency_without_row_is_reported(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "| FastAPI | python-multipart | google-genai | pytest | pypdfium2 |")
    problems = lic.run(root, root / "THIRD_PARTY.md", [], verbose=False)
    assert problems == ["L2: pypdf: declared dependency has no row in THIRD_PARTY.md"]


def test_all_dependencies_listed_pass(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "fastapi, python_multipart, google-genai, pytest, pypdf")
    assert lic.run(root, root / "THIRD_PARTY.md", [], verbose=False) == []


def test_vendored_script_without_licence_is_reported(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "fastapi, python-multipart, google-genai, pytest, pypdf")
    vendor = root / lic.WEB_STATIC / "js" / "vendor"
    vendor.mkdir(parents=True)
    (vendor / "lib.min.js").write_text("x")
    problems = lic.run(root, root / "THIRD_PARTY.md", [], verbose=False)
    assert any(p.startswith("L3: ") and "lib.min.js" in p for p in problems)
    (vendor / "lib.LICENSE").write_text("0BSD")
    assert lic.run(root, root / "THIRD_PARTY.md", [], verbose=False) == []


def test_fonts_without_licence_files_are_reported(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "fastapi, python-multipart, google-genai, pytest, pypdf")
    fonts = root / lic.WEB_STATIC / "fonts"
    fonts.mkdir(parents=True)
    (fonts / "mukta-latin-400-normal.woff2").write_bytes(b"wOF2")
    problems = lic.run(root, root / "THIRD_PARTY.md", [], verbose=False)
    assert any("fonts without LICENSES" in p for p in problems)


def test_real_environment_is_clean() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout
    assert "0 problems" in result.stdout
