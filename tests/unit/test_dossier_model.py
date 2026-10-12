"""The evidence-file model: field status, confirmation, stamp and assumptions (pure)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from munim_core.clock import BankRate, ClockInput, Payment
from munim_core.dossier_model import (
    Acceptance,
    ClaimInput,
    RateRow,
    build_dossier,
    can_confirm,
    field_statuses,
    is_accepted,
    run_clock,
    stamp_visible,
    unresolved_blocking,
)
from munim_core.verify.models import FieldRef, Finding, Severity, Status

pytestmark = pytest.mark.unit

REF = FieldRef("invoice", "buyer_gstin")


def f(
    rule: str,
    status: Status,
    severity: Severity = Severity.BLOCKING,
    refs: tuple[FieldRef, ...] = (REF,),
) -> Finding:
    return Finding(rule, status, severity, f"rule.{rule}", {}, refs, "1.0")


def test_field_status_is_the_worst_finding_about_the_field() -> None:
    findings = [
        f("GSTIN-FORMAT", Status.PASSED),
        f("GSTIN-CHECKSUM", Status.FAILED),
        f(
            "X-NAME-SIMILAR",
            Status.NEEDS_REVIEW,
            Severity.WARNING,
            (FieldRef("invoice", "buyer_name"),),
        ),
        f("X-QTY", Status.SKIPPED, refs=(FieldRef("invoice", "quantity", 0),)),
    ]
    statuses = field_statuses(findings)
    assert statuses[REF] is Status.FAILED
    assert statuses[FieldRef("invoice", "buyer_name")] is Status.NEEDS_REVIEW
    assert statuses[FieldRef("invoice", "quantity", 0)] is Status.SKIPPED


def test_needs_review_outranks_passed_and_failed_outranks_needs_review() -> None:
    assert (
        field_statuses([f("A", Status.PASSED), f("B", Status.NEEDS_REVIEW)])[REF]
        is Status.NEEDS_REVIEW
    )
    assert (
        field_statuses([f("B", Status.NEEDS_REVIEW), f("C", Status.FAILED)])[REF] is Status.FAILED
    )


def test_blocking_failures_stop_confirmation_until_accepted() -> None:
    failing = f("GSTIN-CHECKSUM", Status.FAILED)
    assert unresolved_blocking([failing], []) == [failing]
    assert can_confirm([failing], []) is False
    accepted = [Acceptance("GSTIN-CHECKSUM", (REF,), "I checked the paper by hand")]
    assert is_accepted(failing, accepted)
    assert can_confirm([failing], accepted) is True


def test_an_acceptance_covers_only_the_same_rule_and_fields() -> None:
    failing = f("GSTIN-CHECKSUM", Status.FAILED)
    other_field = [Acceptance("GSTIN-CHECKSUM", (FieldRef("challan", "buyer_gstin"),), "checked")]
    other_rule = [Acceptance("GSTIN-FORMAT", (REF,), "checked")]
    assert can_confirm([failing], other_field) is False
    assert can_confirm([failing], other_rule) is False


def test_warnings_and_passes_never_stop_confirmation() -> None:
    findings = [f("A", Status.PASSED), f("X-NAME-SIMILAR", Status.NEEDS_REVIEW, Severity.WARNING)]
    assert can_confirm(findings, []) is True


def test_blocking_needs_review_stops_confirmation() -> None:
    assert can_confirm([f("GSTIN-LOOKALIKE", Status.NEEDS_REVIEW)], []) is False


def test_stamp_shows_only_when_confirmed_and_nothing_blocks() -> None:
    clean = [f("A", Status.PASSED)]
    blocked = [f("B", Status.FAILED)]
    assert stamp_visible(True, clean, []) is True
    assert stamp_visible(False, clean, []) is False
    assert stamp_visible(True, blocked, []) is False
    assert stamp_visible(True, blocked, [Acceptance("B", (REF,), "checked")]) is True


SEEDED = (
    RateRow(BankRate(date(2025, 6, 6), Decimal("5.75")), confirmed=False),
    RateRow(BankRate(date(2025, 12, 5), Decimal("5.50")), confirmed=False),
    RateRow(BankRate(date(2026, 10, 7), Decimal("5.75")), confirmed=False),
)


def demo_input(**over: object) -> ClockInput:
    base: dict[str, object] = {
        "acceptance_date": date(2026, 3, 20),
        "agreement": "written",
        "credit_days": 30,
        "principal_paise": 50_000_000,
        "as_on": date(2026, 10, 13),
        "rates": tuple(r.rate for r in SEEDED),
    }
    base.update(over)
    return ClockInput(**base)  # type: ignore[arg-type]


def test_run_clock_returns_the_result_and_the_rows_it_used() -> None:
    outcome = run_clock(demo_input(), SEEDED)
    assert outcome.error_key is None
    assert outcome.result is not None and outcome.result.interest_paise == 4_097_671
    assert outcome.rates_used == (SEEDED[1],)
    assert outcome.rates_unconfirmed is True


def test_run_clock_turns_a_missing_rate_into_a_message_key_with_the_date() -> None:
    late_only = (SEEDED[2],)
    outcome = run_clock(demo_input(rates=(late_only[0].rate,)), late_only)
    assert outcome.result is None
    assert outcome.error_key == "clock.error.no_rate"
    assert outcome.error_params == {"needed_date": "2026-04-20"}


def test_run_clock_asks_for_credit_days_with_a_written_agreement() -> None:
    outcome = run_clock(demo_input(credit_days=None), SEEDED)
    assert (outcome.result, outcome.error_key) == (None, "clock.error.credit_days")


def test_run_clock_reports_an_overpayment() -> None:
    outcome = run_clock(demo_input(payments=(Payment(date(2026, 5, 1), 60_000_000),)), SEEDED)
    assert outcome.error_key == "clock.error.payment_too_large"
    assert outcome.error_params == {
        "paid_on_date": "2026-05-01",
        "amount_paise": "60000000",
        "balance_paise": "50252083",
    }


def test_confirmed_rates_clear_the_unconfirmed_flag() -> None:
    confirmed = tuple(RateRow(r.rate, confirmed=True) for r in SEEDED)
    assert run_clock(demo_input(), confirmed).rates_unconfirmed is False


def claims() -> list[ClaimInput]:
    return [
        ClaimInput(
            REF,
            value="27AAAPZ5678Z1Z1",
            value_read="27AAAPZ5678Z1ZK",
            source="repair",
            box=(100, 200, 140, 600),
        ),
        ClaimInput(
            FieldRef("invoice", "buyer_name"),
            value="Demo Textiles Ltd",
            value_read="Demo Textiles Ltd",
            source="model",
            box=None,
        ),
    ]


def test_build_dossier_rows_carry_status_rules_and_acceptance_reasons() -> None:
    findings = [f("GSTIN-CHECKSUM", Status.FAILED), f("GSTIN-FORMAT", Status.PASSED)]
    acceptances = [Acceptance("GSTIN-CHECKSUM", (REF,), "I checked the paper by hand")]
    model = build_dossier(
        claims=claims(),
        findings=findings,
        acceptances=acceptances,
        confirmed=True,
        clock=run_clock(demo_input(), SEEDED),
        interest_base="invoice_total",
        has_payments=False,
    )
    row = model.rows[0]
    assert (row.status, row.rule_ids, row.accepted_reasons) == (
        Status.FAILED,
        ("GSTIN-CHECKSUM", "GSTIN-FORMAT"),
        ("I checked the paper by hand",),
    )
    assert model.rows[1].status is None and model.rows[1].rule_ids == ()
    assert model.stamp_visible is True
    assert model.unresolved == ()


def test_build_dossier_lists_the_assumptions_that_apply() -> None:
    model = build_dossier(
        claims=claims(),
        findings=[],
        acceptances=[],
        confirmed=False,
        clock=run_clock(demo_input(payments=(Payment(date(2026, 5, 1), 1_000),)), SEEDED),
        interest_base="taxable_total",
        has_payments=True,
    )
    assert model.assumptions == (
        "assumption.registration",
        "assumption.acceptance",
        "assumption.rate_month_start",
        "assumption.partial_month",
        "assumption.interest_base.taxable_total",
        "assumption.part_payments",
        "assumption.bank_rate_unconfirmed",
    )
    assert model.stamp_visible is False


def test_build_dossier_without_a_clock_has_no_clock_assumptions() -> None:
    model = build_dossier(
        claims=claims(),
        findings=[],
        acceptances=[],
        confirmed=False,
        clock=None,
        interest_base="invoice_total",
        has_payments=False,
    )
    assert model.assumptions == ("assumption.registration", "assumption.acceptance")
