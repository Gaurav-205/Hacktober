"""Validate an evaluation report against eval/reports/schema.json and the current prompts.

Exit 0 valid, 1 invalid (schema errors, or prompt versions that differ from the prompt files,
so the report no longer describes this code), 2 when the report cannot be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

SCHEMA = Path(__file__).resolve().parent / "reports" / "schema.json"


def problems(report: object) -> list[str]:
    from munim_ai.evaluation import current_prompt_versions

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    found = [
        f"{'/'.join(str(p) for p in error.absolute_path) or '(root)'}: {error.message}"
        for error in sorted(validator.iter_errors(report), key=lambda e: list(e.absolute_path))
    ]
    if isinstance(report, dict) and report.get("prompt_versions") != current_prompt_versions():
        found.append("prompt_versions: differ from the prompt files; re-run the evaluation")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"validate_report: cannot read {args.report}: {exc}", file=sys.stderr)
        return 2
    found = problems(report)
    for problem in found:
        print(f"{args.report}: {problem}")
    print(f"validate_report: {len(found)} problems")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
