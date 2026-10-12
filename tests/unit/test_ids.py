"""Unit tests for munim_core.ids (docs/DOMAIN_RULES.md 3.1, docs/TESTING.md section 2)."""

from __future__ import annotations

import pytest
from stdnum import verhoeff

from munim_core.ids import (
    GSTIN_STATE_CODES,
    check_gstin,
    check_ifsc_format,
    check_pan,
    check_udyam,
    lookalike_candidates,
    mask_aadhaar,
    normalise_gstin,
)
from tests.ref_gstin import check_character

pytestmark = pytest.mark.unit

VECTORS = ["27AAPFU0939F1ZV", "27AABCU9603R1ZN", "09AAACT2727Q1ZU"]


@pytest.mark.parametrize("gstin", VECTORS)
def test_published_vectors_pass(gstin: str) -> None:
    result = check_gstin(gstin)
    assert result.ok is True
    assert result.errors == ()
    assert result.state_code == gstin[:2]
    assert result.pan == gstin[2:12]


@pytest.mark.parametrize("gstin", VECTORS)
def test_reference_algorithm_reproduces_the_published_check_characters(gstin: str) -> None:
    assert check_character(gstin[:14]) == gstin[14]


@pytest.mark.parametrize("gstin", VECTORS)
def test_changing_the_check_character_fails_the_checksum(gstin: str) -> None:
    wrong = gstin[:14] + ("A" if gstin[14] != "A" else "B")
    result = check_gstin(wrong)
    assert result.ok is False
    assert result.errors == ("GSTIN-CHECKSUM",)


@pytest.mark.parametrize("gstin", ["27AAPFU0939F1Z", "27AAPFU0939F1ZVX", "", "27AAPFUO939F1ZV"])
def test_bad_length_or_shape_fails_format_only(gstin: str) -> None:
    result = check_gstin(gstin)
    assert result.ok is False
    assert result.errors == ("GSTIN-FORMAT",)
    assert result.state_code is None and result.pan is None


@pytest.mark.parametrize("code", ["99", "00", "40"])
def test_unknown_state_code_fails_state(code: str) -> None:
    body = code + "AAPFU0939F1Z"
    result = check_gstin(body + check_character(body))
    assert result.errors == ("GSTIN-STATE",)


def test_state_and_checksum_failures_are_both_reported() -> None:
    result = check_gstin("99AAPFU0939F1ZV")
    assert set(result.errors) == {"GSTIN-STATE", "GSTIN-CHECKSUM"}


@pytest.mark.parametrize(
    ("body", "reason"),
    [("27AAPFU0939F0Z", "registration number 0"), ("27AAPFU0939F1Y", "no Z at position 14")],
)
def test_structural_components_fail_format(body: str, reason: str) -> None:
    result = check_gstin(body + check_character(body))
    assert result.errors == ("GSTIN-FORMAT",), reason


def test_ladakh_and_other_territory_codes_are_known_although_stdnum_2_2_omits_them() -> None:
    from stdnum.in_ import gstin as stdnum_gstin

    assert {"38", "97"} <= GSTIN_STATE_CODES
    body = "38AAPFU0939F1Z"
    ladakh = body + check_character(body)
    assert check_gstin(ladakh).ok is True
    assert stdnum_gstin.is_valid(ladakh) is False  # the documented difference


@pytest.mark.parametrize(
    ("raw", "normalised"),
    [
        ("27aapfu0939f1zv", "27AAPFU0939F1ZV"),
        ("27 AAPFU 0939F 1ZV", "27AAPFU0939F1ZV"),
        ("27-AAPFU-0939F-1ZV", "27AAPFU0939F1ZV"),
        ("  27AAPFU0939F1ZV\n", "27AAPFU0939F1ZV"),
    ],
)
def test_case_spaces_and_hyphens_are_normalised_and_recorded(raw: str, normalised: str) -> None:
    assert normalise_gstin(raw) == normalised
    result = check_gstin(raw)
    assert result.ok is True
    assert result.normalised == normalised
    assert result.normalisation_applied is True


def test_clean_input_records_no_normalisation() -> None:
    assert check_gstin("27AAPFU0939F1ZV").normalisation_applied is False


def test_pan_is_characters_three_to_twelve() -> None:
    assert check_gstin("09AAACT2727Q1ZU").pan == "AAACT2727Q"


def test_lookalike_fixes_a_letter_o_in_a_digit_position_exactly_once() -> None:
    misread = "27AAPFUO939F1ZV"  # the 0 at position 8 (1-indexed) read as O
    assert check_gstin(misread).errors == ("GSTIN-FORMAT",)
    assert lookalike_candidates(misread) == ["27AAPFU0939F1ZV"]


def test_two_errors_are_not_fixed_by_one_substitution() -> None:
    assert lookalike_candidates("27AAPFUO939F1ZW") == []


def test_check_character_misread_outside_the_map_has_no_candidates() -> None:
    misread = "27AAPFU0939F1ZK"  # V read as K: not a look-alike pair
    assert check_gstin(misread).errors == ("GSTIN-CHECKSUM",)
    assert lookalike_candidates(misread) == []


def test_several_passing_candidates_are_all_returned_so_none_is_unique() -> None:
    # Search a family of synthetic GSTINs for one where two substitutions both pass, and
    # check the function reports both rather than choosing one.
    found = None
    for serial in range(1000, 9999):
        body = f"27AAPFU{serial}F1Z"
        valid = body + check_character(body)
        for i, char in enumerate(valid):
            if char in "0O1I5S8B2Z6G" and i not in (13,):
                swap = {"0": "O", "O": "0", "1": "I", "I": "1", "5": "S", "S": "5"}.get(char)
                if swap is None:
                    continue
                broken = valid[:i] + swap + valid[i + 1 :]
                if len(lookalike_candidates(broken)) > 1:
                    found = broken
                    break
        if found:
            break
    assert found is not None
    candidates = lookalike_candidates(found)
    assert len(candidates) >= 2
    assert all(check_gstin(c).ok for c in candidates)


def test_valid_gstin_has_no_lookalike_candidates() -> None:
    assert lookalike_candidates("27AAPFU0939F1ZV") == []


def synthetic_aadhaar(first11: str) -> str:
    return first11 + verhoeff.calc_check_digit(first11)


def test_valid_aadhaar_numbers_are_masked_to_the_last_four_digits() -> None:
    number = synthetic_aadhaar("23456789012")  # synthetic
    masked = mask_aadhaar(f"ID {number} on file")
    assert masked == f"ID XXXX XXXX {number[-4:]} on file"
    grouped = f"{number[:4]} {number[4:8]} {number[8:]}"
    assert mask_aadhaar(grouped) == f"XXXX XXXX {number[-4:]}"
    hyphenated = f"{number[:4]}-{number[4:8]}-{number[8:]}"
    assert mask_aadhaar(hyphenated) == f"XXXX XXXX {number[-4:]}"


def test_invalid_twelve_digit_runs_are_untouched() -> None:
    number = synthetic_aadhaar("23456789012")  # synthetic
    wrong = number[:-1] + str((int(number[-1]) + 1) % 10)
    assert mask_aadhaar(wrong) == wrong
    assert mask_aadhaar("123456789012") == "123456789012"  # starts with 1
    assert mask_aadhaar(number + "5") == number + "5"  # thirteen digits


def test_masking_text_without_numbers_changes_nothing() -> None:
    assert mask_aadhaar("Delta Textiles Ltd") == "Delta Textiles Ltd"


@pytest.mark.parametrize(
    ("pan", "ok"),
    [("AAPFU0939F", True), ("aapfu0939f", True), ("AAPFU093F", False), ("AAPXU0939F", False)],
)
def test_pan_format(pan: str, ok: bool) -> None:
    assert check_pan(pan) is ok


@pytest.mark.parametrize(
    ("udyam", "ok"),
    [
        ("UDYAM-UP-05-0001234", True),
        ("udyam-up-05-0001234", True),
        ("UDYAM-UP-5-0001234", False),
        ("UDYAM-U1-05-0001234", False),
    ],
)
def test_udyam_format(udyam: str, ok: bool) -> None:
    assert check_udyam(udyam) is ok


@pytest.mark.parametrize(
    ("ifsc", "ok"), [("SBIN0001234", True), ("SBIN1001234", False), ("SBI00012345", False)]
)
def test_ifsc_format(ifsc: str, ok: bool) -> None:
    assert check_ifsc_format(ifsc) is ok
