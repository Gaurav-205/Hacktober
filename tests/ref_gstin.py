"""Pure-Python reference for the GSTIN check character (docs/DOMAIN_RULES.md 3.1).

Written from the text of the algorithm only, so it can cross-check python-stdnum. It lives in
tests/ on purpose: production code calls stdnum.
"""

from __future__ import annotations

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def check_character(first14: str) -> str:
    """Return the check character for the first 14 characters of a GSTIN."""
    total = 0
    for position, char in enumerate(first14, start=1):
        value = ALPHABET.index(char)
        weight = 1 if position % 2 == 1 else 2
        product = value * weight
        total += product // 36 + product % 36
    return ALPHABET[(36 - total % 36) % 36]


def checksum_ok(gstin: str) -> bool:
    """Return True when the 15th character is the check character of the first 14."""
    if len(gstin) != 15 or any(c not in ALPHABET for c in gstin):
        return False
    return check_character(gstin[:14]) == gstin[14]
