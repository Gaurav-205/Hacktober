"""Dates as printed on Indian papers (docs/DOMAIN_RULES.md 3.2 DATE-AMBIGUOUS and 5.3).

Numeric dates are read day first, as Indian papers print them. When the day and the month are
both 12 or less and differ ("04/07/2026"), the other reading is kept in `alt` and the date is
marked ambiguous, so a person can choose. Core never formats dates for display.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta

from munim_core.text import to_ascii_digits

__all__ = ["DateParseError", "ParsedDate", "add_months", "parse_date_dayfirst"]

_MONTHS: dict[str, int] = {}
for _number, _names in enumerate(
    (
        ("jan", "january", "जनवरी"),
        ("feb", "february", "फरवरी", "फ़रवरी"),
        ("mar", "march", "मार्च"),
        ("apr", "april", "अप्रैल", "अप्रेल"),
        ("may", "मई"),
        ("jun", "june", "जून"),
        ("jul", "july", "जुलाई"),
        ("aug", "august", "अगस्त"),
        ("sep", "sept", "september", "सितंबर", "सितम्बर"),
        ("oct", "october", "अक्टूबर", "अक्तूबर"),
        ("nov", "november", "नवंबर", "नवम्बर"),
        ("dec", "december", "दिसंबर", "दिसम्बर"),
    ),
    start=1,
):
    for _name in _names:
        _MONTHS[_name] = _number

_SEP = r"\s*[/\-.]\s*"
_NUMERIC = re.compile(rf"^(\d{{1,2}}){_SEP}(\d{{1,2}}){_SEP}(\d{{2}}|\d{{4}})$")
_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
# Month words are any run without separators or digits: Devanagari vowel signs are combining
# marks, which \w does not match.
_DAY_WORD_YEAR = re.compile(
    r"^(\d{1,2})(?:st|nd|rd|th)?[\s\-/.,]+([^\s\d/.,\-]+\.?)[\s\-/.,]+(\d{2}|\d{4})$"
)
_WORD_DAY_YEAR = re.compile(
    r"^([^\s\d/.,\-]+\.?)[\s\-/.]+(\d{1,2})(?:st|nd|rd|th)?,?[\s\-/.]+(\d{4})$"
)


class DateParseError(ValueError):
    """The text is not a date Munim can read."""


@dataclass(frozen=True)
class ParsedDate:
    """A date read from a paper: the day-first reading, and the other reading if ambiguous."""

    value: date
    ambiguous: bool = False
    alt: date | None = None


def _year(text: str) -> int:
    year = int(text)
    if len(text) == 2:
        return 2000 + year if year < 70 else 1900 + year
    return year


def _make(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _month(word: str) -> int:
    month = _MONTHS.get(word.rstrip(".").casefold())
    if month is None:
        raise DateParseError("the month name is not one Munim knows")
    return month


def parse_date_dayfirst(text: str) -> ParsedDate:
    """Read a printed date, day first. Raise DateParseError when no reading is a real date."""
    cleaned = to_ascii_digits(text).strip()
    if match := _ISO.match(cleaned):
        value = _make(int(match[1]), int(match[2]), int(match[3]))
        if value is None:
            raise DateParseError("not a real date")
        return ParsedDate(value)
    if match := _NUMERIC.match(cleaned):
        first, second, year = int(match[1]), int(match[2]), _year(match[3])
        day_first = _make(year, second, first)
        month_first = _make(year, first, second)
        if day_first is None:
            if month_first is None:
                raise DateParseError("not a real date")
            return ParsedDate(month_first)
        if month_first is not None and month_first != day_first:
            return ParsedDate(day_first, ambiguous=True, alt=month_first)
        return ParsedDate(day_first)
    if match := _DAY_WORD_YEAR.match(cleaned):
        value = _make(_year(match[3]), _month(match[2]), int(match[1]))
    elif match := _WORD_DAY_YEAR.match(cleaned):
        value = _make(int(match[3]), _month(match[1]), int(match[2]))
    else:
        raise DateParseError("not a date format Munim reads")
    if value is None:
        raise DateParseError("not a real date")
    return ParsedDate(value)


def add_months(d: date, n: int) -> date:
    """Add n calendar months, clamping to the last day of a shorter month (31 Jan + 1 = 28 Feb)."""
    result: date = d + relativedelta(months=n)
    return result
