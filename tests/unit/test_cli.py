"""The core CLI (T1.8): the clock and GSTIN rules from a terminal."""

from __future__ import annotations

import subprocess
import sys

import pytest

from munim_core.cli import main

pytestmark = pytest.mark.unit


def test_interest_reproduces_the_three_month_golden(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "interest",
            "--principal",
            "500000",
            "--due",
            "2025-12-31",
            "--as-on",
            "2026-04-01",
            "--rate",
            "18",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "interest        ₹22,839.19" in out
    assert "total           ₹5,22,839.19" in out
    assert out.count("  month ") == 3


def test_bank_rate_option_is_multiplied_by_three(capsys: pytest.CaptureFixture[str]) -> None:
    main(
        [
            "interest",
            "--principal",
            "5,00,000",
            "--due",
            "2026-04-19",
            "--as-on",
            "2026-10-13",
            "--bank-rate",
            "5.75",
        ]
    )
    out = capsys.readouterr().out
    assert "days late       177" in out
    assert "interest        ₹42,903.70" in out
    assert "partial" in out and "(23/30 days)" in out


def test_gstin_command_reports_each_rule_and_a_lookalike(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["gstin", "27AAPFU0939F1ZV"]) == 0
    assert main(["gstin", "27AAPFUO939F1ZV"]) == 1
    out = capsys.readouterr().out
    assert "GSTIN-FORMAT    failed" in out
    assert "look-alike      27AAPFU0939F1ZV" in out


@pytest.mark.parametrize(
    "args",
    [
        [
            "interest",
            "--principal",
            "-5",
            "--due",
            "2026-01-01",
            "--as-on",
            "2026-02-01",
            "--rate",
            "18",
        ],
        [
            "interest",
            "--principal",
            "5",
            "--due",
            "01/01/2026",
            "--as-on",
            "2026-02-01",
            "--rate",
            "18",
        ],
        [
            "interest",
            "--principal",
            "5",
            "--due",
            "2026-01-01",
            "--as-on",
            "2026-02-01",
            "--rate",
            "x",
        ],
        ["interest", "--principal", "5", "--due", "2026-01-01", "--as-on", "2026-02-01"],
    ],
)
def test_bad_arguments_exit_with_a_usage_error(args: list[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        main(args)
    assert exited.value.code == 2


def test_module_runs_as_a_script() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "munim_core.cli", "gstin", "09AAACT2727Q1ZU"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "GSTIN-CHECKSUM  passed" in result.stdout
