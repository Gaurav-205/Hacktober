"""Tests for scripts/check_licences.py (licence allow-list and THIRD_PARTY coverage)."""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from types import ModuleType

import pytest
from packaging.requirements import Requirement  # installed with pytest, which requires it

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


# ---------------------------------------------------------------- main(): exit codes
ALL_LISTED = "fastapi, python-multipart, google-genai, pytest, pypdf"


def run_main(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run the script on a temporary workspace (the installed distributions are the real ones,
    which test_real_environment_is_clean shows are clean)."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def assert_tool_error(result: subprocess.CompletedProcess[str], *fragments: str) -> None:
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert len(lines) == 1, result.stderr
    assert lines[0].startswith("check_licences: ")
    for fragment in fragments:
        assert fragment in lines[0]


def test_main_passes_on_a_workspace_with_every_dependency_listed(tmp_path: Path) -> None:
    result = run_main(make_repo(tmp_path, ALL_LISTED))

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[-1].endswith(" distributions, 0 problems")


def test_main_exits_1_when_a_dependency_has_no_third_party_row(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "fastapi, python-multipart, google-genai, pytest")

    result = run_main(root)

    assert result.returncode == 1, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines[:-1] == ["L2: pypdf: declared dependency has no row in THIRD_PARTY.md"]
    assert lines[-1].endswith(" distributions, 1 problems")


def test_main_exits_2_on_a_broken_manifest(tmp_path: Path) -> None:
    root = make_repo(tmp_path, ALL_LISTED)
    (root / "packages" / "p" / "pyproject.toml").write_text('[project\nname = "p"\n')

    assert_tool_error(run_main(root), "pyproject.toml", "not valid TOML")


@pytest.mark.parametrize("rel", ["pyproject.toml", "packages/p/pyproject.toml", "THIRD_PARTY.md"])
def test_main_exits_2_on_a_file_that_is_not_utf8(tmp_path: Path, rel: str) -> None:
    root = make_repo(tmp_path, ALL_LISTED)
    (root / rel).write_bytes(b"\xff")

    assert_tool_error(run_main(root), Path(rel).name, "not valid UTF-8")


def test_main_exits_2_when_third_party_md_is_missing(tmp_path: Path) -> None:
    root = make_repo(tmp_path, ALL_LISTED)
    (root / "THIRD_PARTY.md").unlink()

    assert_tool_error(run_main(root), "THIRD_PARTY.md")


# ---------------------------------------------------------------- EXCEPTIONS stay dev-only
# docs/adr/0007 allows text-unidecode because it is only in the dev group and Munim never
# imports it. These tests keep both claims true for every name in EXCEPTIONS.
RUNTIME_ROOTS = ("munim-core", "munim-ai", "munim-web", "munim-mcp")
REPO_ROOT = Path(__file__).resolve().parents[2]


def runtime_closure(roots: tuple[str, ...]) -> set[str]:
    """Normalised names of the roots and everything they require at run time, transitively.

    Requirements behind an extra that was not asked for, or behind an environment marker that
    does not hold here, are left out; the extras a requirement asks for are followed.
    """
    seen: dict[str, frozenset[str]] = {}
    todo: list[tuple[str, frozenset[str]]] = [(root, frozenset()) for root in roots]
    while todo:
        name, extras = todo.pop()
        key = lic.normalise_name(name)
        if key in seen and extras <= seen[key]:
            continue
        seen[key] = seen.get(key, frozenset()) | extras
        try:
            requirements = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            pytest.fail(f"{name} is required at run time but not installed; run make install")
        for text in requirements:
            requirement = Requirement(text)
            marker = requirement.marker
            if marker is not None and not any(
                marker.evaluate({"extra": extra}) for extra in (seen[key] or {""})
            ):
                continue
            todo.append((requirement.name, frozenset(requirement.extras)))
    return set(seen)


def test_runtime_closure_follows_requirements_and_markers() -> None:
    closure = runtime_closure(RUNTIME_ROOTS)
    assert {"munim-core", "python-stdnum", "fastapi", "starlette", "pydantic-core"} <= closure
    assert "google-genai" not in closure  # only behind munim-ai's gemini extra
    assert "pytest" not in closure


def test_licence_exceptions_are_not_runtime_dependencies() -> None:
    closure = runtime_closure(RUNTIME_ROOTS)
    assert lic.EXCEPTIONS, "no exceptions left; this test can go"
    for name in lic.EXCEPTIONS:
        assert lic.normalise_name(name) not in closure, (
            f"{name} is a run-time dependency of a Munim package; docs/adr/0007 allows it only "
            "as a dev-only dependency"
        )


def exception_modules() -> set[str]:
    """Top-level import names of the EXCEPTIONS distributions (installed, or guessed)."""
    wanted = {lic.normalise_name(name) for name in lic.EXCEPTIONS}
    modules = {name.replace("-", "_") for name in wanted}
    for module, dists in metadata.packages_distributions().items():
        if wanted & {lic.normalise_name(dist) for dist in dists}:
            modules.add(module)
    return modules


def imported_modules(tree: ast.AST) -> set[str]:
    """Module names imported by a parsed file, including import_module("x") style strings."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)
    return found


def test_no_package_imports_a_licence_exception() -> None:
    modules = exception_modules()
    assert "text_unidecode" in modules
    offenders = []
    sources = sorted((REPO_ROOT / "packages").rglob("*.py"))
    assert sources, "no package sources found"
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in imported_modules(tree):
            if name.split(".")[0] in modules:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {name}")
    assert offenders == []


def test_import_scan_sees_plain_from_and_dynamic_imports() -> None:
    source = (
        "import text_unidecode\n"
        "from text_unidecode import unidecode\n"
        "importlib.import_module('text_unidecode.data')\n"
    )
    names = imported_modules(ast.parse(source))
    assert {"text_unidecode", "text_unidecode.data"} <= names
