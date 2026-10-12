"""Fail when the detect-secrets baseline holds a finding nobody has audited.

Run `detect-secrets scan --baseline .secrets.baseline` first: it rescans, keeps the audit
marks of known findings and adds new ones without a mark. Line numbers may move when a
document changes; that is not a reason to fail. A finding counts as audited only when it is
marked `"is_secret": false` (a reviewed false positive). Anything else fails.

Exit 0 when every finding is an audited false positive, 1 otherwise, 2 if the file is unreadable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def unaudited(baseline: dict[str, object]) -> list[str]:
    results = baseline.get("results", {})
    if not isinstance(results, dict):
        raise ValueError("baseline has no results mapping")
    problems: list[str] = []
    for filename, items in sorted(results.items()):
        for item in items:
            if item.get("is_secret") is not False:
                problems.append(f"{filename}:{item.get('line_number', 0)}: {item.get('type')}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("baseline", type=Path, nargs="?", default=Path(".secrets.baseline"))
    args = parser.parse_args(argv)
    try:
        problems = unaudited(json.loads(args.baseline.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"check_secrets_baseline: {exc}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"{problem}: possible secret not audited; remove it, or audit it as a false positive")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
