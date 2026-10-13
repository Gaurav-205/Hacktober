"""Small text helpers shared by the parsers. Pure functions, no I/O."""

from __future__ import annotations

import unicodedata

__all__ = ["to_ascii_digits", "whole_number"]


def to_ascii_digits(text: str) -> str:
    """Replace every Unicode decimal digit (Devanagari, Gujarati, ...) with its ASCII digit.

    Papers in India mix scripts: an amount printed as "१२,५०,०००" is the same number as
    "12,50,000". Only characters in the Unicode category Nd are changed.
    """
    out: list[str] = []
    for char in text:
        if char.isdigit() and not char.isascii() and unicodedata.category(char) == "Nd":
            out.append(str(unicodedata.decimal(char)))
        else:
            out.append(char)
    return "".join(out)


def whole_number(text: str | None) -> int | None:
    """Read a whole number of days or similar, in any script's decimal digits; else None.

    ``str.isdigit()`` also accepts superscripts and circled numbers ("²", "①") that ``int()``
    rejects, so only ASCII digits after ``to_ascii_digits`` count.
    """
    if text is None:
        return None
    digits = to_ascii_digits(text.strip())
    if not digits or not (digits.isascii() and digits.isdecimal()):
        return None
    return int(digits)
