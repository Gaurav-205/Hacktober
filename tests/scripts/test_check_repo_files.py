"""Tests for scripts/check_repo_files.py (repository hygiene guard)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_repo_files.py"
GSTIN_SHAPED = "27AAPFU0939F1ZV"  # the published python-stdnum test vector, not a real business


def clean_env(ceiling: Path) -> dict[str, str]:
    """The environment without GIT_* variables (a pre-commit run sets some), and git kept
    from finding a repository above ``ceiling``."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["GIT_CEILING_DIRECTORIES"] = str(ceiling)
    return env


def run(root: Path, *files: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *files],
        capture_output=True,
        text=True,
        check=False,
        env=clean_env(root.parent),
    )


def write(root: Path, rel: str, data: bytes) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def test_clean_text_file_passes(tmp_path: Path) -> None:
    rel = write(tmp_path, "packages/x.py", b"print('hello')\n")
    result = run(tmp_path, rel)
    assert result.returncode == 0, result.stdout
    assert result.stdout == ""


def test_file_over_two_megabytes_is_blocked(tmp_path: Path) -> None:
    rel = write(tmp_path, "big.bin", b"\0" * (2 * 1024 * 1024 + 1))
    result = run(tmp_path, rel)
    assert result.returncode == 1
    assert "big.bin:0: R1:" in result.stdout


def test_file_of_exactly_two_megabytes_passes(tmp_path: Path) -> None:
    rel = write(tmp_path, "edge.bin", b"\0" * (2 * 1024 * 1024))
    assert run(tmp_path, rel).returncode == 0


@pytest.mark.parametrize("rel", ["photo.jpg", "packages/a/scan.PNG", "docs/invoice.pdf"])
def test_image_outside_allowed_folders_is_blocked(tmp_path: Path, rel: str) -> None:
    write(tmp_path, rel, b"not really an image")
    result = run(tmp_path, rel)
    assert result.returncode == 1
    assert f"{rel}:0: R2:" in result.stdout


@pytest.mark.parametrize("rel", ["eval/fixtures/demo/invoice.jpg", "docs/screens/cases-en-360.png"])
def test_image_inside_allowed_folders_passes(tmp_path: Path, rel: str) -> None:
    write(tmp_path, rel, b"synthetic image bytes")
    assert run(tmp_path, rel).returncode == 0


def test_gstin_shaped_string_in_package_code_is_blocked(tmp_path: Path) -> None:
    rel = write(tmp_path, "packages/m/x.py", b"a = 1\nEXAMPLE = '27AAPFU0939F1ZV'\n")
    result = run(tmp_path, rel)
    assert result.returncode == 1
    assert "packages/m/x.py:2: R3:" in result.stdout


@pytest.mark.parametrize(
    ("rel", "line"),
    [
        ("data_export/claims.csv", f"id,gstin\n1,{GSTIN_SHAPED}\n"),
        ("eval/reports/run.jsonl", f'{{"id": 1}}\n{{"gstin": "{GSTIN_SHAPED}"}}\n'),
        ("exports/claims.tsv", f"id\tgstin\n1\t{GSTIN_SHAPED}\n"),
        ("packages/w/static/seal.svg", f"<svg>\n<text>{GSTIN_SHAPED}</text></svg>\n"),
        ("packages/w/feed.xml", f"<feed>\n<gstin>{GSTIN_SHAPED}</gstin></feed>\n"),
        ("rules/sample.yaml", f"id: x\nexample: {GSTIN_SHAPED}\n"),
        ("packages/m/lower.py", f"a = 1\nEXAMPLE = '{GSTIN_SHAPED.lower()}'\n"),
        ("packages/m/Makefile.local", f"all:\n\techo {GSTIN_SHAPED}\n"),
    ],
    ids=["csv", "jsonl", "tsv", "svg", "xml", "yaml", "lowercase-py", "no-known-suffix"],
)
def test_gstin_shaped_string_in_any_text_file_is_blocked(
    tmp_path: Path, rel: str, line: str
) -> None:
    write(tmp_path, rel, line.encode("utf-8"))
    result = run(tmp_path, rel)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        f"{rel}:2: R3: GSTIN-shaped string outside eval/fixtures/, tests/ and docs/; "
        "use synthetic values in those folders only"
    ]


def test_binary_file_is_not_scanned_for_gstins(tmp_path: Path) -> None:
    # A NUL byte in the first 8 KB marks the file as binary (git uses the same test).
    data = b"\x89PNG\0\0" + b"x" * 100 + GSTIN_SHAPED.encode("ascii") + b"\n"
    rel = write(tmp_path, "packages/w/static/blob.dat", data)
    assert run(tmp_path, rel).returncode == 0


def test_nul_byte_after_the_first_8_kb_still_counts_as_text(tmp_path: Path) -> None:
    data = GSTIN_SHAPED.encode("ascii") + b"\n" + b"x" * 9000 + b"\0"
    rel = write(tmp_path, "packages/w/static/late.dat", data)
    result = run(tmp_path, rel)
    assert result.returncode == 1
    assert f"{rel}:1: R3:" in result.stdout


@pytest.mark.parametrize("folder", ["tests", "docs", "eval/fixtures", ".claude"])
@pytest.mark.parametrize("name", ["x.md", "x.csv", "x.jsonl"])
def test_gstin_shaped_string_in_allowed_folders_passes(
    tmp_path: Path, folder: str, name: str
) -> None:
    rel = write(tmp_path, f"{folder}/{name}", b"Published vector 27AAPFU0939F1ZV\n")
    assert run(tmp_path, rel).returncode == 0
    lower = write(tmp_path, f"{folder}/lower-{name}", b"Published vector 27aapfu0939f1zv\n")
    assert run(tmp_path, lower).returncode == 0


def test_missing_file_is_ignored(tmp_path: Path) -> None:
    assert run(tmp_path, "deleted/in/this/commit.py").returncode == 0


# ---------------------------------------------------------------- no file arguments: git ls-files
def git(root: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Munim Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        env=clean_env(root.parent),
    )


def test_without_arguments_every_tracked_file_is_checked(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "packages/m/x.py", f"EXAMPLE = '{GSTIN_SHAPED}'\n".encode())
    write(root, "tests/ok.py", f"EXAMPLE = '{GSTIN_SHAPED}'\n".encode())
    write(root, "untracked.py", f"EXAMPLE = '{GSTIN_SHAPED}'\n".encode())
    git(root, "add", "packages/m/x.py", "tests/ok.py")
    git(root, "commit", "-q", "-m", "synthetic test commit")

    result = run(root)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        "packages/m/x.py:1: R3: GSTIN-shaped string outside eval/fixtures/, tests/ and docs/; "
        "use synthetic values in those folders only"
    ]


def test_without_arguments_a_clean_repository_passes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "packages/m/x.py", b"print('hello')\n")
    git(root, "add", "packages/m/x.py")
    git(root, "commit", "-q", "-m", "synthetic test commit")

    result = run(root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_without_arguments_outside_a_git_repository_is_an_error(tmp_path: Path) -> None:
    root = tmp_path / "not-a-repo"
    root.mkdir()
    write(root, "packages/m/x.py", f"EXAMPLE = '{GSTIN_SHAPED}'\n".encode())

    result = run(root)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("check_repo_files: ")
