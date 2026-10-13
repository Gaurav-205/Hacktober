"""Run Munim's evaluation (docs/AI_SPEC.md section 8) and write the report.

MUNIM_PROVIDER picks the reader (default replay over eval/fixtures/replay). A replay run writes
eval/reports/replay.json; any other reader writes eval/reports/latest.json (PLAN_REVIEW D10).
Exit 0 when the report was written and no recording was missing, 1 otherwise, 2 on bad input.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "eval" / "fixtures"
REPORTS = ROOT / "eval" / "reports"


def main(argv: list[str] | None = None) -> int:
    from munim_ai.evaluation import run_evaluation
    from munim_ai.providers import make_provider

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--case", action="append", default=None, help="only these case ids")
    parser.add_argument("--repair-only", action="store_true", help="only the injected GSTIN cases")
    parser.add_argument("--no-repair", action="store_true")
    args = parser.parse_args(argv)
    name = os.environ.get("MUNIM_PROVIDER", "replay")
    if not (args.fixtures / "manifest.json").is_file():
        print(f"run_eval: no manifest in {args.fixtures}; run make fixtures", file=sys.stderr)
        return 2
    provider = make_provider(
        name,
        ollama_url=os.environ.get("MUNIM_OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=os.environ.get("MUNIM_OLLAMA_MODEL", "gemma4:e4b"),
        gemini_model=os.environ.get("MUNIM_GEMINI_MODEL", "gemma-4-31b-it"),
        gemini_key=os.environ.get("GEMINI_API_KEY"),
        replay_dir=args.fixtures / "replay",
    )
    cases = set(args.case) if args.case else None
    if args.repair_only:
        manifest = json.loads((args.fixtures / "manifest.json").read_text(encoding="utf-8"))
        cases = {c["id"] for c in manifest["cases"] if c["injected"]}
    report = asyncio.run(
        run_evaluation(
            provider,
            args.fixtures,
            as_on=args.date,
            limit=args.limit,
            case_ids=cases,
            repair=not args.no_repair,
        )
    )
    out = args.out or REPORTS / ("replay.json" if name == "replay" else "latest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    wp = report["metrics"]["wrong_and_passed"]
    print(
        f"run_eval: {report['provider']} ({report['recorded_from']}), {report['n_papers']} papers, "
        f"{report['n_fields']} fields -> {out}"
    )
    print(
        f"run_eval: {report['summary']} "
        f"Wrong and passed: {wp['count']} of {wp['over_scored_fields']['n']}."
    )
    if report["missing_recordings"]:
        print(
            f"run_eval: missing recordings: {', '.join(report['missing_recordings'])}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
