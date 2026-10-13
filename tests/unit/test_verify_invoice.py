"""Invoice rules (docs/DOMAIN_RULES.md 3.2): pass, fail, boundary and skipped for each."""

from __future__ import annotations

from datetime import date

import pytest

from munim_core.verify import run_all
from munim_core.verify.models import FieldRef, Severity, Status
from tests.ref_gstin import check_character
from tests.unit.verify_helpers import TODAY, case, clean_invoice_lines, invoice, only

pytestmark = pytest.mark.unit

# A synthetic Maharashtra supplier, so supplier and buyer are in the same state.
INTRA_SUPPLIER = "27AAAPZ1234Z1Z" + check_character("27AAAPZ1234Z1Z")


def run_invoice(lines: list[dict[str, str | None]] | None = None, **fields: str | None):
    return run_all(case(inv=invoice(**fields), inv_lines=lines), TODAY)


def test_the_demo_invoice_passes_every_invoice_rule() -> None:
    findings = run_invoice()
    for rule_id in (
        "INV-LINE-AMOUNT",
        "INV-TAXABLE-SUM",
        "INV-TAX-SPLIT",
        "INV-TAX-RATE",
        "INV-TOTAL",
        "INV-NUMBER-FORMAT",
        "INV-DATE-SANE",
    ):
        results = only(findings, rule_id)
        assert results, rule_id
        assert {f.status for f in results} == {Status.PASSED}, rule_id


# ---------------------------------------------------------------- VALUE-FORMAT


def test_unreadable_amount_fails_value_format_and_skips_the_arithmetic() -> None:
    findings = run_invoice(invoice_total="5,0O,000.00")
    value = only(findings, "VALUE-FORMAT", "invoice_total")[0]
    assert value.status is Status.FAILED
    assert value.severity is Severity.BLOCKING
    assert value.message_key == "rule.VALUE-FORMAT.amount"
    assert value.params == {"printed": "5,0O,000.00"}
    assert only(findings, "INV-TOTAL")[0].status is Status.SKIPPED


def test_unreadable_date_fails_value_format() -> None:
    findings = run_invoice(invoice_date="31/02/2026")
    value = only(findings, "VALUE-FORMAT", "invoice_date")[0]
    assert (value.status, value.message_key) == (Status.FAILED, "rule.VALUE-FORMAT.date")


def test_readable_values_pass_value_format() -> None:
    findings = run_invoice()
    assert only(findings, "VALUE-FORMAT", "invoice_total")[0].status is Status.PASSED


# ---------------------------------------------------------------- INV-LINE-AMOUNT


def lines_with(**changes: str | None) -> list[dict[str, str | None]]:
    lines = clean_invoice_lines()
    lines[0] = {**lines[0], **changes}
    return lines


def test_line_amount_off_by_one_paisa_passes() -> None:
    findings = run_invoice(lines_with(amount="3,00,000.01"))
    assert only(findings, "INV-LINE-AMOUNT")[0].status is Status.PASSED


def test_line_amount_off_by_two_paise_fails_with_the_line_number() -> None:
    findings = run_invoice(lines_with(amount="3,00,000.02"))
    line = only(findings, "INV-LINE-AMOUNT")[0]
    assert line.status is Status.FAILED
    assert line.params == {"n": "1", "computed_paise": "30000000", "printed_paise": "30000002"}
    assert FieldRef("invoice", "amount", 0) in line.fields


def test_fractional_quantity_times_rate_is_rounded_half_up() -> None:
    findings = run_invoice(lines_with(quantity="2.5", rate="0.03", amount="0.08"))
    assert only(findings, "INV-LINE-AMOUNT")[0].status is Status.PASSED


def test_line_with_a_missing_rate_is_skipped() -> None:
    findings = run_invoice(lines_with(rate=None))
    assert only(findings, "INV-LINE-AMOUNT")[0].status is Status.SKIPPED


# ---------------------------------------------------------------- INV-TAXABLE-SUM


def test_lines_not_adding_up_to_the_taxable_total_fail() -> None:
    findings = run_invoice(taxable_total="4,23,730.00")
    taxable = only(findings, "INV-TAXABLE-SUM")[0]
    assert taxable.status is Status.FAILED
    assert taxable.params == {"computed_paise": "42372900", "printed_paise": "42373000"}


def test_taxable_sum_is_skipped_without_lines() -> None:
    assert only(run_invoice([]), "INV-TAXABLE-SUM")[0].status is Status.SKIPPED


# ---------------------------------------------------------------- INV-TAX-SPLIT


def test_inter_state_with_cgst_fails() -> None:
    findings = run_invoice(cgst="38,135.61", sgst="38,135.61", igst=None)
    split = only(findings, "INV-TAX-SPLIT")[0]
    assert split.status is Status.FAILED
    assert split.params == {
        "same_or_different_key": "term.different_states",
        "expected_key": "term.igst",
    }


def test_intra_state_with_igst_fails() -> None:
    findings = run_invoice(supplier_gstin=INTRA_SUPPLIER, place_of_supply="27-Maharashtra")
    split = only(findings, "INV-TAX-SPLIT")[0]
    assert split.status is Status.FAILED
    assert split.params["expected_key"] == "term.cgst_sgst"


def test_intra_state_with_equal_cgst_and_sgst_passes() -> None:
    findings = run_invoice(
        supplier_gstin=INTRA_SUPPLIER,
        cgst="38,135.61",
        sgst="38,135.61",
        igst=None,
        round_off="0.00",
    )
    assert only(findings, "INV-TAX-SPLIT")[0].status is Status.PASSED


def test_intra_state_with_unequal_cgst_and_sgst_fails() -> None:
    findings = run_invoice(
        supplier_gstin=INTRA_SUPPLIER, cgst="38,135.61", sgst="38,135.60", igst=None
    )
    assert only(findings, "INV-TAX-SPLIT")[0].status is Status.FAILED


def test_place_of_supply_naming_another_state_needs_review() -> None:
    findings = run_invoice(place_of_supply="Karnataka")
    split = only(findings, "INV-TAX-SPLIT")[0]
    assert split.status is Status.NEEDS_REVIEW
    assert split.message_key == "rule.INV-TAX-SPLIT.place_of_supply"
    assert split.blocks is True


def test_place_of_supply_by_code_or_name_matching_the_buyer_passes() -> None:
    for pos in ("27", "Maharashtra", "MAHARASHTRA (27)", "27 - Maharashtra"):
        assert only(run_invoice(place_of_supply=pos), "INV-TAX-SPLIT")[0].status is Status.PASSED, (
            pos
        )


def test_tax_split_is_skipped_without_both_gstins() -> None:
    assert only(run_invoice(buyer_gstin=None), "INV-TAX-SPLIT")[0].status is Status.SKIPPED


# ---------------------------------------------------------------- INV-TAX-RATE


def test_eighteen_percent_is_an_allowed_slab_in_2026() -> None:
    assert only(run_invoice(), "INV-TAX-RATE")[0].status is Status.PASSED


@pytest.mark.parametrize(
    ("invoice_date", "status"),
    [
        ("21/09/2025", Status.PASSED),
        ("22/09/2025", Status.NEEDS_REVIEW),
        ("01/01/2026", Status.NEEDS_REVIEW),
    ],
)
def test_twelve_percent_is_allowed_only_before_22_september_2025(
    invoice_date: str, status: Status
) -> None:
    # 12% of 4,23,729.00 = 50,847.48; total 4,74,576.48.
    findings = run_invoice(
        igst="50,847.48", round_off=None, invoice_total="4,74,576.48", invoice_date=invoice_date
    )
    rate = only(findings, "INV-TAX-RATE")[0]
    assert rate.status is status
    assert rate.severity is Severity.WARNING


def test_twenty_eight_percent_needs_review_after_the_reform() -> None:
    findings = run_invoice(
        igst="1,18,644.12", round_off=None, invoice_total="5,42,373.12", invoice_date="01/01/2026"
    )
    assert only(findings, "INV-TAX-RATE")[0].status is Status.NEEDS_REVIEW


def test_tax_rate_tolerance_is_one_paisa_per_line() -> None:
    # Two lines allow 2 paise: 76,271.24 is 2 paise above 18%.
    findings = run_invoice(igst="76,271.24", round_off="-0.24")
    assert only(findings, "INV-TAX-RATE")[0].status is Status.PASSED
    findings = run_invoice(igst="76,271.25", round_off="-0.25")
    assert only(findings, "INV-TAX-RATE")[0].status is Status.NEEDS_REVIEW


def test_tax_rate_is_skipped_without_a_taxable_total() -> None:
    assert only(run_invoice(taxable_total=None), "INV-TAX-RATE")[0].status is Status.SKIPPED


# ---------------------------------------------------------------- INV-TOTAL


def test_printed_round_off_must_give_an_exact_sum() -> None:
    assert only(run_invoice(invoice_total="5,00,000.01"), "INV-TOTAL")[0].status is Status.PASSED
    failed = only(run_invoice(invoice_total="5,00,000.02"), "INV-TOTAL")[0]
    assert failed.status is Status.FAILED
    assert failed.params == {"computed_paise": "50000000", "printed_paise": "50000002"}


def test_sign_flipped_round_off_fails() -> None:
    assert only(run_invoice(round_off="0.22"), "INV-TOTAL")[0].status is Status.FAILED


def test_round_off_of_a_whole_rupee_fails() -> None:
    findings = run_invoice(round_off="-1.00", igst="76,272.00")
    assert only(findings, "INV-TOTAL")[0].status is Status.FAILED


@pytest.mark.parametrize(
    ("total", "status"),
    [
        ("5,00,000.21", Status.PASSED),
        ("5,00,000.22", Status.PASSED),
        ("4,99,999.22", Status.PASSED),
        ("4,99,999.21", Status.FAILED),
        ("5,00,001.23", Status.FAILED),
    ],
)
def test_without_a_round_off_line_up_to_one_rupee_difference_passes(
    total: str, status: Status
) -> None:
    # Taxable + IGST = 5,00,000.22; 99 paise either side passes, 100 passes, 101 fails.
    findings = run_invoice(round_off=None, invoice_total=total)
    assert only(findings, "INV-TOTAL")[0].status is status


def test_total_is_skipped_without_the_invoice_total() -> None:
    assert only(run_invoice(invoice_total=None), "INV-TOTAL")[0].status is Status.SKIPPED


# ---------------------------------------------------------------- INV-NUMBER-FORMAT


@pytest.mark.parametrize(
    ("number", "status"),
    [
        ("SF/2025-26/0412", Status.PASSED),
        ("A" * 16, Status.PASSED),
        ("A" * 17, Status.FAILED),
        ("SF 2025 0412", Status.FAILED),
        ("INV#12", Status.FAILED),
    ],
)
def test_invoice_number_format(number: str, status: Status) -> None:
    result = only(run_invoice(invoice_number=number), "INV-NUMBER-FORMAT")[0]
    assert result.status is status
    assert result.severity is Severity.WARNING


def test_invoice_number_format_is_skipped_without_a_number() -> None:
    assert only(run_invoice(invoice_number=None), "INV-NUMBER-FORMAT")[0].status is Status.SKIPPED


# ---------------------------------------------------------------- INV-DATE-SANE


@pytest.mark.parametrize(
    ("printed", "status"),
    [
        ("13/10/2026", Status.PASSED),
        ("14/10/2026", Status.FAILED),
        ("01 Jul 2017", Status.PASSED),
        ("30 Jun 2017", Status.FAILED),
    ],
)
def test_invoice_date_between_gst_start_and_today(printed: str, status: Status) -> None:
    result = only(run_invoice(invoice_date=printed), "INV-DATE-SANE")[0]
    assert result.status is status
    assert result.severity is Severity.BLOCKING


def test_invoice_date_sane_reports_the_date_it_read() -> None:
    result = only(run_invoice(invoice_date="14/10/2026"), "INV-DATE-SANE")[0]
    assert result.params == {"printed": "14/10/2026", "read_date": date(2026, 10, 14).isoformat()}


def test_runaway_value_on_any_field_needs_review() -> None:
    from munim_core.verify.models import CaseState, ClaimValue, PaperState
    from tests.unit.verify_helpers import paper

    base = paper("challan", {"challan_number": "DC-1", "challan_date": "20/03/2026"})
    fields = {
        **base.fields,
        "buyer_name": ClaimValue(raw=None, text=None, source="model", flag="runaway"),
    }
    state = CaseState(papers={"challan": PaperState("challan", fields, base.lines)})
    flagged = only(run_all(state, TODAY), "VALUE-FORMAT", "buyer_name")
    assert len(flagged) == 1
    assert (flagged[0].status, flagged[0].severity, flagged[0].message_key) == (
        Status.NEEDS_REVIEW,
        Severity.WARNING,
        "rule.VALUE-FORMAT.runaway",
    )
    assert flagged[0].fields == (FieldRef("challan", "buyer_name"),)
