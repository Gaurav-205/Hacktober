"""Money as integer paise (docs/DOMAIN_RULES.md section 1).

Floating point is never used for money. Amounts are stored and computed as integer paise;
Decimal is used only inside calculations, built from strings or integers, and rounded half up.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from munim_core.text import to_ascii_digits

__all__ = [
    "MoneyParseError",
    "Paise",
    "format_inr",
    "parse_inr",
    "parse_quantity",
    "parse_rate_paise",
    "parse_signed_inr",
    "round_half_up",
]

Paise = int

_PREFIX = re.compile(r"^(?:₹|rs\.?|inr)\s*", re.IGNORECASE)
_SUFFIX = re.compile(r"\s*/\s*[-=]\s*$")
_NEGATIVE = re.compile(r"[-−–(]")
# Integer part: plain digits, Indian grouping (12,50,000) or Western grouping (1,250,000).
_INTEGER = re.compile(r"^(?:\d+|\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+)$")


class MoneyParseError(ValueError):
    """The text is not an amount Munim can read exactly."""


def parse_inr(text: str) -> Paise:
    """Parse an amount as printed on an Indian paper into integer paise.

    Accepts "12,50,000", "1250000", "12,50,000.50", "₹ 12,50,000/-", "Rs. 1,000", Western
    grouping and Devanagari digits. Rejects negative amounts, more than two decimals, digit
    groups that are neither Indian nor Western, and anything that is not a number.
    """
    cleaned = to_ascii_digits(text).strip()
    cleaned = _SUFFIX.sub("", cleaned)
    if _NEGATIVE.search(cleaned):
        raise MoneyParseError("negative or bracketed amounts are not accepted")
    cleaned = _PREFIX.sub("", cleaned).strip()
    if cleaned.endswith(".") and cleaned.count(".") == 1:
        cleaned = cleaned[:-1]
    if not cleaned:
        raise MoneyParseError("no amount found")
    whole, dot, fraction = cleaned.partition(".")
    if dot and not fraction.isdigit():
        raise MoneyParseError("the part after the decimal point is not digits")
    if len(fraction) > 2:
        raise MoneyParseError("more than two decimal places")
    if whole and not _INTEGER.match(whole):
        raise MoneyParseError("digits are not grouped as an Indian or Western amount")
    if not whole and not fraction:
        raise MoneyParseError("no digits")
    rupees = int(whole.replace(",", "")) if whole else 0
    return rupees * 100 + int(fraction.ljust(2, "0") or "0")


_SIGN = re.compile(r"^\s*([-−–+])\s*")
_BRACKETS = re.compile(r"^\s*\((.*)\)\s*$")
_QUANTITY = re.compile(r"^(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d+)?$")


def parse_signed_inr(text: str) -> Paise:
    """Parse an amount that may be negative, such as a round-off line: "-0.22", "(0.22)"."""
    cleaned = to_ascii_digits(text).strip()
    negative = False
    if match := _BRACKETS.match(cleaned):
        cleaned, negative = match.group(1), True
    elif match := _SIGN.match(cleaned):
        negative = match.group(1) != "+"
        cleaned = cleaned[match.end() :]
    paise = parse_inr(cleaned)
    return -paise if negative else paise


def parse_quantity(text: str) -> Decimal:
    """Parse a printed quantity (digits, optional grouping and decimals) into a Decimal."""
    cleaned = to_ascii_digits(text).strip()
    if not _QUANTITY.match(cleaned):
        raise MoneyParseError("not a quantity")
    return Decimal(cleaned.replace(",", ""))


def parse_rate_paise(text: str) -> Decimal:
    """Parse a unit rate, which may have more than two decimals ("247.458"), into paise."""
    cleaned = to_ascii_digits(text).strip()
    cleaned = _SUFFIX.sub("", cleaned)
    if _NEGATIVE.search(cleaned):
        raise MoneyParseError("negative rates are not accepted")
    cleaned = _PREFIX.sub("", cleaned).strip()
    if not _QUANTITY.match(cleaned):
        raise MoneyParseError("not a rate")
    return Decimal(cleaned.replace(",", "")) * 100


def _group_indian(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    pairs: list[str] = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head, *pairs, tail])


def format_inr(p: Paise) -> str:
    """Format integer paise as rupees with Indian grouping and two decimals: "₹12,50,000.00"."""
    sign = "-" if p < 0 else ""
    rupees, paise = divmod(abs(p), 100)
    return f"{sign}₹{_group_indian(str(rupees))}.{paise:02d}"


def round_half_up(value: Decimal) -> int:
    """Round a Decimal to the nearest integer, halves away from zero (ROUND_HALF_UP)."""
    if not isinstance(value, Decimal):
        raise TypeError("round_half_up takes a Decimal; build it from a string or an int")
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
