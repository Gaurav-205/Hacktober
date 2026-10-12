"""Tests for scripts/check_repo_files.py (repository hygiene guard)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_repo_files.py"


def run(root: Path, *files: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *files],
        capture_output=True,
        text=True,
        check=False,
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


@pytest.mark.parametrize("folder", ["tests", "docs", "eval/fixtures"])
def test_gstin_shaped_string_in_allowed_folders_passes(tmp_path: Path, folder: str) -> None:
    rel = write(tmp_path, f"{folder}/x.md", b"Published vector 27AAPFU0939F1ZV\n")
    assert run(tmp_path, rel).returncode == 0


def test_missing_file_is_ignored(tmp_path: Path) -> None:
    assert run(tmp_path, "deleted/in/this/commit.py").returncode == 0
