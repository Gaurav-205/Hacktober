"""Tests for scripts/check_coverage.py (coverage targets per package)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_coverage.py"


def summary(statements: int, covered: int, branches: int, covered_branches: int) -> dict[str, int]:
    return {
        "num_statements": statements,
        "covered_lines": covered,
        "num_branches": branches,
        "covered_branches": covered_branches,
    }


def run(tmp_path: Path, files: dict[str, dict[str, int]]) -> subprocess.CompletedProcess[str]:
    report = tmp_path / "cov.json"
    report.write_text(json.dumps({"files": {k: {"summary": v} for k, v in files.items()}}))
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(report)], capture_output=True, text=True, check=False
    )


def test_core_and_overall_meeting_targets_pass(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        {
            "packages/munim_core/src/munim_core/money.py": summary(100, 96, 20, 19),
            "packages/munim_web/src/munim_web/app.py": summary(100, 80, 10, 5),
        },
    )
    assert result.returncode == 0, result.stdout
    assert "munim_core: lines 96.00%, branches 95.00%" in result.stdout
    assert "overall: lines 88.00%" in result.stdout


def test_core_lines_below_95_fail(tmp_path: Path) -> None:
    result = run(tmp_path, {"x/munim_core/clock.py": summary(100, 94, 10, 10)})
    assert result.returncode == 1
    assert "munim_core: lines 94.00%" in result.stdout and "FAIL" in result.stdout


def test_core_branches_below_90_fail(tmp_path: Path) -> None:
    result = run(tmp_path, {"x/munim_core/clock.py": summary(100, 100, 10, 8)})
    assert result.returncode == 1
    assert "branches 80.00%" in result.stdout


def test_overall_below_85_fails_even_when_core_is_fine(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        {
            "x/munim_core/clock.py": summary(100, 100, 10, 10),
            "x/munim_web/app.py": summary(100, 60, 0, 0),
        },
    )
    assert result.returncode == 1
    assert "overall: lines 80.00%" in result.stdout


def test_no_core_code_yet_is_skipped_not_failed(tmp_path: Path) -> None:
    result = run(tmp_path, {})
    assert result.returncode == 0
    assert "munim_core: no measured code yet, skipped" in result.stdout


def test_unreadable_report_is_a_tool_error(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "missing.json")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
