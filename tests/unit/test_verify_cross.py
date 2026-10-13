"""Date and cross-paper rules (docs/DOMAIN_RULES.md 3.2 DATE-AMBIGUOUS and 3.3)."""

from __future__ import annotations

from datetime import date

import pytest

from munim_core.verify import run_all
from munim_core.verify.models import FieldRef, Severity, Status
from tests.ref_gstin import check_character
from tests.unit.verify_helpers import (
    BUYER_GSTIN,
    SUPPLIER_GSTIN,
    TODAY,
    case,
    challan,
    challan_lines,
    clean_invoice_lines,
    invoice,
    only,
    po,
)

pytestmark = pytest.mark.unit


def full_case(**kw):  # type: ignore[no-untyped-def]
    return case(
        inv=kw.pop("inv", invoice()),
        ch=kw.pop("ch", challan()),
        order=kw.pop("order", po()),
        **kw,
    )


def test_the_demo_case_passes_every_blocking_rule() -> None:
    findings = run_all(full_case(), TODAY)
    blocking = [f for f in findings if f.blocks]
    assert blocking == []
    for rule_id in (
        "X-SUPPLIER-GSTIN",
        "X-BUYER-GSTIN",
        "X-INVOICE-REF",
        "X-PO-REF",
        "X-QTY",
        "X-DATE-ORDER",
        "X-RECEIVER-ACK",
        "X-NAME-SIMILAR",
    ):
        assert {f.status for f in only(findings, rule_id)} == {Status.PASSED}, rule_id


# ---------------------------------------------------------------- DATE-AMBIGUOUS


def test_ambiguous_challan_date_is_blocking_and_offers_both_readings() -> None:
    findings = run_all(full_case(ch=challan(challan_date="04/03/2026")), TODAY)
    amb = only(findings, "DATE-AMBIGUOUS", "challan_date")[0]
    assert amb.status is Status.NEEDS_REVIEW
    assert amb.severity is Severity.BLOCKING
    assert amb.params == {"printed": "04/03/2026", "a_date": "2026-03-04", "b_date": "2026-04-03"}
    assert amb.fields == (FieldRef("challan", "challan_date"),)


def test_ambiguous_po_date_is_only_a_warning() -> None:
    findings = run_all(full_case(order=po(po_date="02/03/2026")), TODAY)
    amb = only(findings, "DATE-AMBIGUOUS", "po_date")[0]
    assert (amb.status, amb.severity, amb.blocks) == (Status.NEEDS_REVIEW, Severity.WARNING, False)


@pytest.mark.parametrize("printed", ["20/03/2026", "07/07/2026", "02 Mar 2026", "2026-03-02"])
def test_unambiguous_dates_pass(printed: str) -> None:
    findings = run_all(full_case(ch=challan(challan_date=printed)), TODAY)
    assert only(findings, "DATE-AMBIGUOUS", "challan_date")[0].status is Status.PASSED


def test_absent_or_unreadable_dates_are_skipped() -> None:
    findings = run_all(full_case(ch=challan(received_date=None, challan_date="soon")), TODAY)
    assert only(findings, "DATE-AMBIGUOUS", "received_date")[0].status is Status.SKIPPED
    assert only(findings, "DATE-AMBIGUOUS", "challan_date")[0].status is Status.SKIPPED


# ---------------------------------------------------------------- X-SUPPLIER-GSTIN, X-BUYER-GSTIN


def other_gstin() -> str:
    body = "27AAAPZ9999Z1Z"
    return body + check_character(body)


def test_buyer_gstin_differing_between_papers_fails_with_both_values() -> None:
    findings = run_all(full_case(ch=challan(buyer_gstin=other_gstin())), TODAY)
    cross = only(findings, "X-BUYER-GSTIN")[0]
    assert cross.status is Status.FAILED
    assert cross.blocks is True
    assert cross.params == {
        "a": BUYER_GSTIN,
        "a_paper_key": "paper.kind.invoice",
        "b": other_gstin(),
        "b_paper_key": "paper.kind.challan",
    }
    assert set(cross.fields) == {
        FieldRef("invoice", "buyer_gstin"),
        FieldRef("challan", "buyer_gstin"),
        FieldRef("po", "buyer_gstin"),
    }


def test_gstin_comparison_ignores_case_and_spaces() -> None:
    spaced = SUPPLIER_GSTIN[:2] + " " + SUPPLIER_GSTIN[2:].lower()
    findings = run_all(full_case(ch=challan(supplier_gstin=spaced)), TODAY)
    assert only(findings, "X-SUPPLIER-GSTIN")[0].status is Status.PASSED


def test_cross_gstin_is_skipped_with_fewer_than_two_values() -> None:
    findings = run_all(case(inv=invoice(), ch=challan(buyer_gstin=None)), TODAY)
    assert only(findings, "X-BUYER-GSTIN")[0].status is Status.SKIPPED
    assert only(run_all(case(inv=invoice()), TODAY), "X-SUPPLIER-GSTIN")[0].status is Status.SKIPPED


# ---------------------------------------------------------------- X-NAME-SIMILAR


def test_trade_name_variants_are_similar() -> None:
    findings = run_all(
        full_case(
            inv=invoice(supplier_name="M/s Shree Ram Fabricators Pvt. Ltd."),
            ch=challan(supplier_name="Shree Ram Fabricators Private Limited"),
            order=po(supplier_name=None),
        ),
        TODAY,
    )
    supplier = [
        f for f in only(findings, "X-NAME-SIMILAR") if f.params.get("role_key") == "term.supplier"
    ]
    assert [f.status for f in supplier] == [Status.PASSED]


def test_names_below_the_threshold_need_review_not_failure() -> None:
    findings = run_all(
        full_case(
            inv=invoice(buyer_name="Delta Textiles"),
            ch=challan(buyer_name="Delta Textile Mills"),
            order=po(buyer_name=None),
        ),
        TODAY,
    )
    buyer = [
        f for f in only(findings, "X-NAME-SIMILAR") if f.params.get("role_key") == "term.buyer"
    ][0]
    assert buyer.status is Status.NEEDS_REVIEW
    assert buyer.severity is Severity.WARNING
    assert buyer.params["a"] == "Delta Textiles" and buyer.params["b"] == "Delta Textile Mills"


def test_name_similarity_is_skipped_for_a_single_paper() -> None:
    findings = run_all(case(inv=invoice()), TODAY)
    assert {f.status for f in only(findings, "X-NAME-SIMILAR")} == {Status.SKIPPED}


# ---------------------------------------------------------------- X-INVOICE-REF, X-PO-REF


@pytest.mark.parametrize(
    "quoted", ["SF/2025-26/0412", "sf/2025-26/412", "SF 2025 26 0412", "SF-2025-26-0412"]
)
def test_invoice_reference_ignores_case_separators_and_leading_zeros(quoted: str) -> None:
    findings = run_all(full_case(ch=challan(invoice_reference=quoted)), TODAY)
    assert only(findings, "X-INVOICE-REF")[0].status is Status.PASSED


def test_invoice_reference_naming_another_invoice_fails() -> None:
    findings = run_all(full_case(ch=challan(invoice_reference="SF/2025-26/0413")), TODAY)
    ref = only(findings, "X-INVOICE-REF")[0]
    assert ref.status is Status.FAILED
    assert ref.blocks is True
    assert ref.params == {"on_challan": "SF/2025-26/0413", "on_invoice": "SF/2025-26/0412"}


def test_invoice_reference_is_skipped_when_the_challan_quotes_none() -> None:
    findings = run_all(full_case(ch=challan(invoice_reference=None)), TODAY)
    assert only(findings, "X-INVOICE-REF")[0].status is Status.SKIPPED


def test_po_reference_mismatch_is_a_warning_per_quoting_paper() -> None:
    findings = run_all(full_case(inv=invoice(po_reference="PO-2026-0118")), TODAY)
    refs = only(findings, "X-PO-REF")
    by_paper = {f.params.get("paper_key"): f for f in refs}
    assert by_paper["paper.kind.invoice"].status is Status.FAILED
    assert by_paper["paper.kind.invoice"].severity is Severity.WARNING
    assert by_paper["paper.kind.challan"].status is Status.PASSED


def test_po_reference_is_skipped_without_a_po() -> None:
    findings = run_all(case(inv=invoice(), ch=challan()), TODAY)
    assert {f.status for f in only(findings, "X-PO-REF")} == {Status.SKIPPED}


# ---------------------------------------------------------------- X-QTY


def test_quantities_match_after_unit_names_are_normalised() -> None:
    findings = run_all(full_case(), TODAY)
    qty = only(findings, "X-QTY")
    assert len(qty) == 2
    assert {f.status for f in qty} == {Status.PASSED}


def test_quantity_difference_fails_with_both_numbers() -> None:
    lines = challan_lines()
    lines[0] = {**lines[0], "quantity": "1150"}
    findings = run_all(full_case(ch_lines=lines), TODAY)
    failed = [f for f in only(findings, "X-QTY") if f.status is Status.FAILED]
    assert len(failed) == 1
    assert failed[0].params == {
        "item": "MS angle 40x40x5",
        "challan_qty": "1150 kgs",
        "invoice_qty": "1,200 kg",
    }
    assert failed[0].blocks is True


def test_kilograms_and_grams_are_converted() -> None:
    lines = challan_lines()
    lines[0] = {**lines[0], "quantity": "12,00,000", "unit": "g"}
    findings = run_all(full_case(ch_lines=lines), TODAY)
    assert {f.status for f in only(findings, "X-QTY")} == {Status.PASSED}


def test_units_that_cannot_be_converted_need_review() -> None:
    lines = challan_lines()
    lines[0] = {**lines[0], "unit": "nos"}
    findings = run_all(full_case(ch_lines=lines), TODAY)
    review = [f for f in only(findings, "X-QTY") if f.status is Status.NEEDS_REVIEW]
    assert len(review) == 1
    assert review[0].message_key == "rule.X-QTY.unit"


def test_an_invoice_line_with_no_matching_challan_line_needs_review() -> None:
    lines = clean_invoice_lines()
    lines.append(
        {
            "description": "Galvanised bolts M12",
            "quantity": "100",
            "unit": "nos",
            "rate": "0",
            "amount": "0",
        }
    )
    findings = run_all(full_case(inv_lines=lines), TODAY)
    unmatched = [f for f in only(findings, "X-QTY") if f.message_key == "rule.X-QTY.unmatched"]
    assert len(unmatched) == 1
    assert unmatched[0].status is Status.NEEDS_REVIEW
    assert unmatched[0].params == {"item": "Galvanised bolts M12"}


def test_quantities_are_skipped_without_a_challan() -> None:
    findings = run_all(case(inv=invoice()), TODAY)
    assert {f.status for f in only(findings, "X-QTY")} == {Status.SKIPPED}


# ---------------------------------------------------------------- X-DATE-ORDER


def test_challan_before_the_po_is_a_warning() -> None:
    findings = run_all(full_case(ch=challan(challan_date="01/03/2026")), TODAY)
    order = [
        f for f in only(findings, "X-DATE-ORDER") if f.message_key == "rule.X-DATE-ORDER.po_challan"
    ][0]
    assert (order.status, order.severity) == (Status.FAILED, Severity.WARNING)
    assert order.params == {"po_date": "2026-03-02", "challan_date": "2026-03-01"}


@pytest.mark.parametrize(
    ("challan_date", "status"), [("20/04/2026", Status.PASSED), ("21/04/2026", Status.FAILED)]
)
def test_challan_more_than_30_days_after_the_invoice_is_a_warning(
    challan_date: str, status: Status
) -> None:
    findings = run_all(full_case(ch=challan(challan_date=challan_date)), TODAY)
    order = [
        f
        for f in only(findings, "X-DATE-ORDER")
        if f.message_key in ("rule.X-DATE-ORDER.invoice_challan", "check.passed")
        and FieldRef("invoice", "invoice_date") in f.fields
    ][0]
    assert order.status is status


def test_challan_after_the_as_on_date_is_blocking() -> None:
    findings = run_all(full_case(as_on=date(2026, 3, 19)), date(2026, 10, 13))
    late = [
        f
        for f in only(findings, "X-DATE-ORDER")
        if f.message_key == "rule.X-DATE-ORDER.after_as_on"
    ][0]
    assert late.status is Status.FAILED
    assert late.blocks is True
    assert late.params == {"acceptance_date": "2026-03-20", "as_on_date": "2026-03-19"}


def test_received_date_is_used_for_acceptance_when_printed() -> None:
    findings = run_all(
        full_case(ch=challan(received_date="25/03/2026"), as_on=date(2026, 3, 24)), TODAY
    )
    late = [
        f
        for f in only(findings, "X-DATE-ORDER")
        if f.message_key == "rule.X-DATE-ORDER.after_as_on"
    ][0]
    assert late.params["acceptance_date"] == "2026-03-25"


def test_typed_acceptance_date_is_used_when_provided() -> None:
    findings = run_all(
        full_case(extra={"acceptance_date": "2026-03-25"}, as_on=date(2026, 3, 24)), TODAY
    )
    late = [
        f
        for f in only(findings, "X-DATE-ORDER")
        if f.message_key == "rule.X-DATE-ORDER.after_as_on"
    ][0]
    assert late.params["acceptance_date"] == "2026-03-25"
    assert FieldRef("case", "acceptance_date") in late.fields


def test_date_order_is_skipped_without_dates() -> None:
    findings = run_all(case(inv=invoice()), TODAY)
    assert {f.status for f in only(findings, "X-DATE-ORDER")} == {Status.SKIPPED}


# ---------------------------------------------------------------- X-RECEIVER-ACK


@pytest.mark.parametrize(
    ("stamp", "signature", "status"),
    [
        ("yes", "no", Status.PASSED),
        ("no", "yes", Status.PASSED),
        ("no", "unknown", Status.NEEDS_REVIEW),
        ("unknown", None, Status.NEEDS_REVIEW),
    ],
)
def test_receiver_stamp_or_signature(stamp: str, signature: str | None, status: Status) -> None:
    findings = run_all(
        full_case(ch=challan(receiver_stamp_present=stamp, receiver_signature_present=signature)),
        TODAY,
    )
    ack = only(findings, "X-RECEIVER-ACK")[0]
    assert ack.status is status
    assert ack.severity is Severity.WARNING


def test_receiver_ack_is_skipped_without_a_challan() -> None:
    assert only(run_all(case(inv=invoice()), TODAY), "X-RECEIVER-ACK")[0].status is Status.SKIPPED


def test_reference_groups_stay_separate_so_different_numbers_do_not_collide() -> None:
    from munim_core.verify.cross import normalise_reference

    assert normalise_reference("1/02") != normalise_reference("12")
    assert normalise_reference("SF/2025-26/0412") == normalise_reference("sf 2025 26 412")
