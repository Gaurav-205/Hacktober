"""Enforce Munim's coverage targets from a coverage.py JSON report.

Targets (docs/TESTING.md section 1, MASTER_PROMPT section 13):
- munim_core: at least 95% of lines and 90% of branches.
- everything measured: at least 85% of lines.

Exit 0 when the targets hold, 1 when one is missed, 2 when the report cannot be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Target:
    name: str
    path_part: str | None  # None means every measured file
    min_lines: float
    min_branches: float | None


TARGETS = (
    Target("munim_core", "/munim_core/", 95.0, 90.0),
    Target("overall", None, 85.0, None),
)


@dataclass
class Tally:
    statements: int = 0
    covered_lines: int = 0
    branches: int = 0
    covered_branches: int = 0

    def add(self, summary: dict[str, int]) -> None:
        self.statements += summary.get("num_statements", 0)
        self.covered_lines += summary.get("covered_lines", 0)
        self.branches += summary.get("num_branches", 0)
        self.covered_branches += summary.get("covered_branches", 0)

    @staticmethod
    def percent(part: int, whole: int) -> float:
        return 100.0 if whole == 0 else 100.0 * part / whole


def evaluate(report: dict[str, object]) -> list[str]:
    files = report.get("files")
    if not isinstance(files, dict):
        raise ValueError("report has no 'files' mapping")
    problems: list[str] = []
    for target in TARGETS:
        tally = Tally()
        for path, data in files.items():
            if target.path_part is None or target.path_part in path.replace("\\", "/"):
                tally.add(data["summary"])
        if tally.statements == 0:
            print(f"{target.name}: no measured code yet, skipped")
            continue
        lines = Tally.percent(tally.covered_lines, tally.statements)
        branches = Tally.percent(tally.covered_branches, tally.branches)
        line_ok = lines >= target.min_lines
        branch_ok = target.min_branches is None or branches >= target.min_branches
        status = "ok" if line_ok and branch_ok else "FAIL"
        wanted = f"lines >= {target.min_lines:.0f}%"
        if target.min_branches is not None:
            wanted += f", branches >= {target.min_branches:.0f}%"
        print(f"{target.name}: lines {lines:.2f}%, branches {branches:.2f}% ({wanted}) {status}")
        if status == "FAIL":
            problems.append(target.name)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path, help="coverage JSON report (coverage json)")
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        problems = evaluate(report)
    except (OSError, ValueError, KeyError) as exc:
        print(f"check_coverage: cannot read {args.report}: {exc}", file=sys.stderr)
        return 2
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
