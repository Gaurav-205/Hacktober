"""Identifier rules (docs/DOMAIN_RULES.md 3.1): pass, fail, boundary and skipped for each."""

from __future__ import annotations

import pytest

from munim_core.verify import run_all
from munim_core.verify.models import CaseState, FieldRef, PaperState, Severity, Status
from tests.ref_gstin import check_character
from tests.unit.verify_helpers import (
    BUYER_GSTIN,
    TODAY,
    case,
    claim,
    invoice,
    only,
)

pytestmark = pytest.mark.unit


def with_check(body: str) -> str:
    return body + check_character(body)


def test_valid_gstins_pass_all_three_rules() -> None:
    findings = run_all(case(inv=invoice()), TODAY)
    for rule_id in ("GSTIN-FORMAT", "GSTIN-STATE", "GSTIN-CHECKSUM"):
        results = only(findings, rule_id, "buyer_gstin")
        assert [f.status for f in results] == [Status.PASSED]
        assert results[0].message_key == "check.passed"
        assert results[0].fields == (FieldRef("invoice", "buyer_gstin"),)
        assert results[0].rule_version == "1.0"


def test_misread_check_character_fails_only_the_checksum() -> None:
    misread = BUYER_GSTIN[:14] + ("K" if BUYER_GSTIN[14] != "K" else "M")
    findings = run_all(case(inv=invoice(buyer_gstin=misread)), TODAY)
    checksum = only(findings, "GSTIN-CHECKSUM", "buyer_gstin")[0]
    assert checksum.status is Status.FAILED
    assert checksum.severity is Severity.BLOCKING
    assert checksum.message_key == "rule.GSTIN-CHECKSUM"
    assert checksum.blocks is True
    assert only(findings, "GSTIN-FORMAT", "buyer_gstin")[0].status is Status.PASSED


def test_letter_o_in_a_digit_position_fails_the_format_and_skips_the_rest() -> None:
    findings = run_all(case(inv=invoice(buyer_gstin="27AAAPZ567OZ1Z1")), TODAY)
    assert only(findings, "GSTIN-FORMAT", "buyer_gstin")[0].status is Status.FAILED
    for rule_id in ("GSTIN-STATE", "GSTIN-CHECKSUM"):
        skipped = only(findings, rule_id, "buyer_gstin")[0]
        assert skipped.status is Status.SKIPPED
        assert skipped.message_key == "check.skipped"


def test_unknown_state_code_fails_state_with_the_code_as_a_param() -> None:
    findings = run_all(case(inv=invoice(buyer_gstin=with_check("99AAAPZ5678Z1Z"))), TODAY)
    state = only(findings, "GSTIN-STATE", "buyer_gstin")[0]
    assert state.status is Status.FAILED
    assert state.params == {"code": "99"}


def test_lowercase_and_spaced_gstin_is_normalised_before_checking() -> None:
    spaced = "27 aaapz 5678z 1z1"
    findings = run_all(case(inv=invoice(buyer_gstin=spaced)), TODAY)
    assert only(findings, "GSTIN-CHECKSUM", "buyer_gstin")[0].status is Status.PASSED


def test_missing_gstin_is_skipped() -> None:
    findings = run_all(case(inv=invoice(buyer_gstin=None)), TODAY)
    for rule_id in ("GSTIN-FORMAT", "GSTIN-STATE", "GSTIN-CHECKSUM"):
        assert only(findings, rule_id, "buyer_gstin")[0].status is Status.SKIPPED


def test_lookalike_repaired_value_stays_needs_review_even_though_checksum_passes() -> None:
    state = case(inv=invoice())
    inv = state.papers["invoice"]
    fields = dict(inv.fields)
    fields["buyer_gstin"] = claim(BUYER_GSTIN, flag="lookalike", source="repair")
    patched = CaseState(
        papers={"invoice": PaperState("invoice", fields, inv.lines)}, as_on=state.as_on
    )
    findings = run_all(patched, TODAY)
    lookalike = only(findings, "GSTIN-LOOKALIKE", "buyer_gstin")
    assert [f.status for f in lookalike] == [Status.NEEDS_REVIEW]
    assert lookalike[0].blocks is True
    assert lookalike[0].message_key == "rule.GSTIN-LOOKALIKE"
    assert only(findings, "GSTIN-CHECKSUM", "buyer_gstin")[0].status is Status.PASSED


def test_no_lookalike_finding_without_the_flag() -> None:
    assert only(run_all(case(inv=invoice()), TODAY), "GSTIN-LOOKALIKE") == []


def test_pan_inside_gstin_matching_the_printed_pan_passes() -> None:
    findings = run_all(case(inv=invoice(supplier_pan="AAAPZ1234Z")), TODAY)
    assert only(findings, "GSTIN-PAN")[0].status is Status.PASSED
    assert only(findings, "PAN-FORMAT")[0].status is Status.PASSED


def test_pan_inside_gstin_differing_from_the_printed_pan_fails_with_both() -> None:
    findings = run_all(case(inv=invoice(supplier_pan="AAAPZ9999Z")), TODAY)
    pan_rule = only(findings, "GSTIN-PAN")[0]
    assert pan_rule.status is Status.FAILED
    assert pan_rule.severity is Severity.BLOCKING
    assert pan_rule.params == {"pan_gstin": "AAAPZ1234Z", "pan_paper": "AAAPZ9999Z"}
    assert set(pan_rule.fields) == {
        FieldRef("invoice", "supplier_gstin"),
        FieldRef("invoice", "supplier_pan"),
    }


def test_badly_formed_pan_fails_pan_format_as_a_warning() -> None:
    findings = run_all(case(inv=invoice(supplier_pan="AAAPZ12Z")), TODAY)
    fmt = only(findings, "PAN-FORMAT")[0]
    assert (fmt.status, fmt.severity, fmt.blocks) == (Status.FAILED, Severity.WARNING, False)
    assert only(findings, "GSTIN-PAN")[0].status is Status.FAILED


def test_pan_rules_are_skipped_when_no_pan_is_printed() -> None:
    findings = run_all(case(inv=invoice()), TODAY)
    assert [f.status for f in only(findings, "GSTIN-PAN")] == [Status.SKIPPED]
    assert [f.status for f in only(findings, "PAN-FORMAT")] == [Status.SKIPPED]


@pytest.mark.parametrize(
    ("udyam", "status"),
    [
        ("UDYAM-UP-05-0001234", Status.PASSED),
        ("UDYAM-UP-5-12", Status.FAILED),
        (None, Status.SKIPPED),
    ],
)
def test_udyam_number_format(udyam: str | None, status: Status) -> None:
    findings = run_all(case(inv=invoice(), udyam=udyam), TODAY)
    result = only(findings, "UDYAM-FORMAT")
    assert [f.status for f in result] == [status]
    assert result[0].fields == (FieldRef("case", "udyam_number"),)
    assert result[0].severity is Severity.WARNING
