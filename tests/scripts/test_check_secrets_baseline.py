"""Tests for scripts/check_secrets_baseline.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_secrets_baseline.py"


def run(tmp_path: Path, results: object) -> subprocess.CompletedProcess[str]:
    path = tmp_path / ".secrets.baseline"
    path.write_text(json.dumps({"version": "1.5.0", "results": results}))
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True, check=False
    )


def test_only_audited_false_positives_pass(tmp_path: Path) -> None:
    results = {"docs/x.md": [{"type": "Secret Keyword", "line_number": 3, "is_secret": False}]}
    assert run(tmp_path, results).returncode == 0


def test_an_unaudited_finding_fails_with_its_location(tmp_path: Path) -> None:
    results = {"app/config.py": [{"type": "Secret Keyword", "line_number": 9}]}
    result = run(tmp_path, results)
    assert result.returncode == 1
    assert "app/config.py:9: Secret Keyword" in result.stdout


def test_a_finding_audited_as_a_real_secret_fails(tmp_path: Path) -> None:
    results = {
        "a.py": [{"type": "Base64 High Entropy String", "line_number": 1, "is_secret": True}]
    }
    assert run(tmp_path, results).returncode == 1


def test_empty_results_pass(tmp_path: Path) -> None:
    assert run(tmp_path, {}).returncode == 0


def test_unreadable_baseline_is_a_tool_error(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
