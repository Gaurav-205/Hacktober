"""Command line for the pure core: the payment clock and the GSTIN rules, for debugging and demos.

    python -m munim_core.cli interest --principal 500000 --due 2025-12-31 \
        --as-on 2026-04-01 --rate 18
    python -m munim_core.cli gstin 27AAPFU0939F1ZV

`--rate` is the annual interest rate (three times the Bank Rate); `--bank-rate` gives the Bank
Rate itself. Output is plain text for a developer, not the product's interface.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation

from munim_core.clock import BankRate, ClockError, ClockInput, compute
from munim_core.ids import check_gstin, lookalike_candidates
from munim_core.money import MoneyParseError, format_inr, parse_inr

__all__ = ["main"]


def _date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{text!r} is not a date in YYYY-MM-DD form") from exc


def _decimal(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("a rate cannot be negative")
    return value


def _paise(text: str) -> int:
    try:
        return parse_inr(text)
    except MoneyParseError as exc:
        raise argparse.ArgumentTypeError(f"{text!r} is not an amount in rupees: {exc}") from exc


def _interest(args: argparse.Namespace) -> int:
    bank_rate = args.bank_rate if args.bank_rate is not None else args.rate / 3
    result = compute(
        ClockInput(
            acceptance_date=args.due,
            agreement="written",
            credit_days=0,
            principal_paise=args.principal,
            as_on=args.as_on,
            rates=(BankRate(date(1900, 1, 1), bank_rate),),
        )
    )
    print(f"due date        {result.due_date.isoformat()}")
    print(f"days late       {result.days_late}")
    for step in result.steps[1:]:
        span = f"{step.start.isoformat()} to {step.end.isoformat()}"
        if step.kind == "partial":
            span += f" ({step.days}/{step.period_days} days)"
        print(f"  {step.kind:8} {span:40} {format_inr(step.interest_paise):>16}")
    print(f"interest        {format_inr(result.interest_paise)}")
    print(f"total           {format_inr(result.total_paise)}")
    return 0


def _gstin(args: argparse.Namespace) -> int:
    result = check_gstin(args.value)
    print(f"normalised      {result.normalised}")
    for rule_id in ("GSTIN-FORMAT", "GSTIN-STATE", "GSTIN-CHECKSUM"):
        print(f"{rule_id:15} {'failed' if rule_id in result.errors else 'passed'}")
    if not result.ok:
        for candidate in lookalike_candidates(result.normalised):
            print(f"look-alike      {candidate}")
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="munim-core", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    interest = sub.add_parser("interest", help="MSMED compound interest from the day after --due")
    interest.add_argument("--principal", type=_paise, required=True, help="amount in rupees")
    interest.add_argument(
        "--due", type=_date, required=True, help="due date; interest runs from the next day"
    )
    interest.add_argument(
        "--as-on", type=_date, required=True, help="interest up to (not including) this date"
    )
    rate = interest.add_mutually_exclusive_group(required=True)
    rate.add_argument(
        "--rate", type=_decimal, help="annual interest rate in percent (3 x Bank Rate)"
    )
    rate.add_argument("--bank-rate", type=_decimal, help="the RBI Bank Rate in percent")
    interest.set_defaults(run=_interest)
    gstin = sub.add_parser("gstin", help="run the GSTIN rules on a value")
    gstin.add_argument("value")
    gstin.set_defaults(run=_gstin)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        code: int = args.run(args)
    except ClockError as exc:
        print(f"munim-core: {exc}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
