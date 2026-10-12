"""Unit tests for munim_core.money (docs/DOMAIN_RULES.md section 1, docs/TESTING.md section 2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from munim_core.money import (
    MoneyParseError,
    format_inr,
    parse_inr,
    parse_quantity,
    parse_rate_paise,
    parse_signed_inr,
    round_half_up,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "paise"),
    [
        ("12,50,000", 125_000_000),
        ("1250000", 125_000_000),
        ("12,50,000.50", 125_000_050),
        ("₹ 12,50,000/-", 125_000_000),
        ("₹ 12,50,000.50/-", 125_000_050),
        ("₹12,50,000.00", 125_000_000),
        ("१२,५०,०००", 125_000_000),
        ("Rs. 1,000", 100_000),
        ("INR 1,000.5", 100_050),
        ("1,250,000.00", 125_000_000),
        ("0", 0),
        ("0.05", 5),
        (".50", 50),
        ("1,000.", 100_000),
        ("  76,271.22  ", 7_627_122),
        ("4,23,729.00", 42_372_900),
        ("1,00,00,000.00", 1_00_00_000_00),
    ],
)
def test_parse_inr_accepts_printed_forms(text: str, paise: int) -> None:
    assert parse_inr(text) == paise


@pytest.mark.parametrize(
    "text",
    [
        "-5",
        "−5",
        "1.234",
        "",
        "   ",
        "abc",
        "1,2,3",
        "12,5,000",
        "1,00",
        "₹",
        "/-",
        "1..2",
        "1 000",
    ],
)
def test_parse_inr_rejects_invalid_input(text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_inr(text)


def test_money_parse_error_is_a_value_error() -> None:
    assert issubclass(MoneyParseError, ValueError)


@pytest.mark.parametrize(
    ("paise", "text"),
    [
        (0, "₹0.00"),
        (99, "₹0.99"),
        (100, "₹1.00"),
        (999_99, "₹999.99"),
        (1_00_000_00, "₹1,00,000.00"),
        (12_50_000_00, "₹12,50,000.00"),
        (1_00_00_000_00, "₹1,00,00,000.00"),
        (4_290_370, "₹42,903.70"),
        (54_290_370, "₹5,42,903.70"),
    ],
)
def test_format_inr_uses_indian_grouping_and_two_decimals(paise: int, text: str) -> None:
    assert format_inr(paise) == text


def test_format_inr_shows_a_minus_sign_for_negative_amounts() -> None:
    assert format_inr(-22) == "-₹0.22"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0.5"), 1),
        (Decimal("1.5"), 2),
        (Decimal("2.5"), 3),
        (Decimal("2.49999"), 2),
        (Decimal("-0.5"), -1),
        (Decimal("0.4"), 0),
    ],
)
def test_round_half_up_rounds_halves_away_from_zero(value: Decimal, expected: int) -> None:
    assert round_half_up(value) == expected


def test_round_half_up_in_paise_matches_the_catalogue_examples() -> None:
    # 0.005 rupees -> 0.01 rupees and 2.675 -> 2.68, expressed in paise.
    assert round_half_up(Decimal("0.005") * 100) == 1
    assert round_half_up(Decimal("2.675") * 100) == 268


def test_round_half_up_rejects_floats() -> None:
    with pytest.raises(TypeError):
        round_half_up(2.675)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "paise"),
    [
        ("-0.22", -22),
        ("−0.22", -22),
        ("(0.22)", -22),
        ("- ₹ 0.22", -22),
        ("0.22", 22),
        ("+0.22", 22),
        ("₹0.78", 78),
    ],
)
def test_parse_signed_inr_reads_round_off_lines(text: str, paise: int) -> None:
    assert parse_signed_inr(text) == paise


@pytest.mark.parametrize("text", ["--0.22", "(0.22", "-", "1.234", "abc"])
def test_parse_signed_inr_rejects_invalid_input(text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_signed_inr(text)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("120", Decimal("120")),
        ("1,200", Decimal("1200")),
        ("12.5", Decimal("12.5")),
        ("१२०", Decimal("120")),
        (" 0.250 ", Decimal("0.250")),
    ],
)
def test_parse_quantity_reads_decimal_quantities(text: str, value: Decimal) -> None:
    assert parse_quantity(text) == value


@pytest.mark.parametrize("text", ["", "-3", "12 kg", "1.2.3", "abc", "1,2"])
def test_parse_quantity_rejects_non_numbers(text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_quantity(text)


@pytest.mark.parametrize(
    ("text", "paise"),
    [
        ("247.458", Decimal("24745.800")),
        ("₹ 1,23,729.00", Decimal("12372900.00")),
        ("0.03", Decimal("3.00")),
    ],
)
def test_parse_rate_paise_keeps_extra_decimals(text: str, paise: Decimal) -> None:
    assert parse_rate_paise(text) == paise


@pytest.mark.parametrize("text", ["-1", "abc", "", "1,2"])
def test_parse_rate_paise_rejects_invalid_rates(text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_rate_paise(text)
