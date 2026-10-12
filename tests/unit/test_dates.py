"""Unit tests for munim_core.dates (docs/DOMAIN_RULES.md 3.2 DATE-AMBIGUOUS, docs/TESTING.md 2)."""

from __future__ import annotations

from datetime import date

import pytest

from munim_core.dates import DateParseError, add_months, parse_date_dayfirst

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "value", "alt"),
    [
        ("04/07/2026", date(2026, 7, 4), date(2026, 4, 7)),
        ("04-07-26", date(2026, 7, 4), date(2026, 4, 7)),
        ("04.07.2026", date(2026, 7, 4), date(2026, 4, 7)),
        ("4/7/2026", date(2026, 7, 4), date(2026, 4, 7)),
        ("02/03/2026", date(2026, 3, 2), date(2026, 2, 3)),
        ("०४/०७/२०२६", date(2026, 7, 4), date(2026, 4, 7)),
    ],
)
def test_numeric_dates_with_both_parts_twelve_or_less_are_ambiguous(
    text: str, value: date, alt: date
) -> None:
    parsed = parse_date_dayfirst(text)
    assert parsed.value == value
    assert parsed.ambiguous is True
    assert parsed.alt == alt


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("25/07/2026", date(2026, 7, 25)),
        ("20/03/2026", date(2026, 3, 20)),
        ("07/07/2026", date(2026, 7, 7)),
        ("4 Jul 2026", date(2026, 7, 4)),
        ("04 July 2026", date(2026, 7, 4)),
        ("02 Mar 2026", date(2026, 3, 2)),
        ("4-Jul-2026", date(2026, 7, 4)),
        ("4th July, 2026", date(2026, 7, 4)),
        ("Jul 4, 2026", date(2026, 7, 4)),
        ("2026-07-04", date(2026, 7, 4)),
        ("२०२६-०७-०४", date(2026, 7, 4)),
        ("4 जुलाई 2026", date(2026, 7, 4)),
        ("12 अक्टूबर 2026", date(2026, 10, 12)),
        ("  21/03/2026  ", date(2026, 3, 21)),
        ("12/31/2026", date(2026, 12, 31)),
    ],
)
def test_unambiguous_dates_have_one_reading(text: str, value: date) -> None:
    parsed = parse_date_dayfirst(text)
    assert parsed.value == value
    assert parsed.ambiguous is False
    assert parsed.alt is None


def test_two_digit_years_are_in_this_century() -> None:
    assert parse_date_dayfirst("21/03/26").value == date(2026, 3, 21)


@pytest.mark.parametrize(
    "text", ["", "abc", "31/02/2026", "13/13/2026", "00/01/2026", "4 Foo 2026", "2026-13-01", "1/2"]
)
def test_unreadable_dates_raise(text: str) -> None:
    with pytest.raises(DateParseError):
        parse_date_dayfirst(text)


def test_date_parse_error_is_a_value_error() -> None:
    assert issubclass(DateParseError, ValueError)


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 1, 31), 2, date(2026, 3, 31)),
        (date(2026, 3, 31), 1, date(2026, 4, 30)),
        (date(2026, 12, 15), 1, date(2027, 1, 15)),
        (date(2026, 1, 1), 12, date(2027, 1, 1)),
        (date(2026, 1, 1), 0, date(2026, 1, 1)),
    ],
)
def test_add_months_clamps_to_the_month_end(start: date, months: int, expected: date) -> None:
    assert add_months(start, months) == expected
