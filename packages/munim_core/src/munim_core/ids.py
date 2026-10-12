"""Indian business identifiers: GSTIN, PAN, Aadhaar masking, Udyam and IFSC formats.

docs/DOMAIN_RULES.md 3.1. GSTIN checks use python-stdnum's format pattern, PAN validation and
check-character algorithm, reported as three separate rules so the person sees which part is
wrong:
- GSTIN-FORMAT: length, character pattern and fixed components (no registration number 0, a Z
  at position 14, a well-formed PAN);
- GSTIN-STATE: the first two digits are a GST state or territory code;
- GSTIN-CHECKSUM: the last character is the check character of the first 14.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from stdnum import luhn
from stdnum.exceptions import ValidationError
from stdnum.in_ import aadhaar
from stdnum.in_ import pan as stdnum_pan

from munim_core.text import to_ascii_digits

__all__ = [
    "GSTIN_STATE_CODES",
    "LOOKALIKE_PAIRS",
    "GstinResult",
    "check_gstin",
    "check_ifsc_format",
    "check_pan",
    "check_udyam",
    "lookalike_candidates",
    "mask_aadhaar",
    "normalise_gstin",
]

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_SHAPE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]{3}$")
# python-stdnum 2.2 lists codes 01 to 37. GST also uses 38 (Ladakh) and 97 (Other Territory);
# without them a real Ladakh GSTIN would be reported as wrong.
GSTIN_STATE_CODES = frozenset(f"{n:02d}" for n in range(1, 38)) | {"38", "97"}
# Characters often confused in print (DOMAIN_RULES 3.1). Substitution works both ways.
LOOKALIKE_PAIRS: tuple[tuple[str, str], ...] = (
    ("0", "O"),
    ("1", "I"),
    ("5", "S"),
    ("8", "B"),
    ("2", "Z"),
    ("6", "G"),
)
_LOOKALIKE = dict(LOOKALIKE_PAIRS) | {b: a for a, b in LOOKALIKE_PAIRS}

_GSTIN_JUNK = re.compile(r"[\s\-]+")
_AADHAAR = re.compile(r"(?<!\d)(\d{4})[ -]?(\d{4})[ -]?(\d{4})(?!\d)")
_UDYAM = re.compile(r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$")
_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


@dataclass(frozen=True)
class GstinResult:
    """The outcome of the GSTIN rules for one value.

    `errors` holds the ids of the rules that failed, in rule order. `state_code` and `pan` are
    set only when the value has the right shape.
    """

    ok: bool
    errors: tuple[str, ...]
    normalised: str
    normalisation_applied: bool
    state_code: str | None
    pan: str | None


def normalise_gstin(raw: str) -> str:
    """Upper-case and remove whitespace and hyphens, as stdnum's compact does for ASCII.

    Unicode is folded with NFKC and other scripts' digits become ASCII, so the result is the
    same however often it is normalised (stdnum's compact is not, for some Greek letters).
    """
    text = to_ascii_digits(unicodedata.normalize("NFKC", raw))
    return unicodedata.normalize("NFKC", _GSTIN_JUNK.sub("", text).upper())


def _components_ok(number: str) -> bool:
    if number[12] == "0" or number[13] != "Z":
        return False
    try:
        stdnum_pan.validate(number[2:12])
    except ValidationError:
        return False
    return True


def check_gstin(raw: str) -> GstinResult:
    """Run GSTIN-FORMAT, GSTIN-STATE and GSTIN-CHECKSUM on a value as read."""
    number = normalise_gstin(raw)
    applied = number != raw
    if len(number) != 15 or not _GSTIN_SHAPE.match(number):
        return GstinResult(False, ("GSTIN-FORMAT",), number, applied, None, None)
    errors: list[str] = []
    if not _components_ok(number):
        errors.append("GSTIN-FORMAT")
    if number[:2] not in GSTIN_STATE_CODES:
        errors.append("GSTIN-STATE")
    if not luhn.is_valid(number, _ALPHABET):
        errors.append("GSTIN-CHECKSUM")
    return GstinResult(not errors, tuple(errors), number, applied, number[:2], number[2:12])


def lookalike_candidates(gstin: str) -> list[str]:
    """Return every GSTIN one look-alike substitution away that passes all three rules.

    The repair accepts a candidate only when this list has exactly one entry, and still marks
    the field for review, because a checksum can pass for a wrong string.
    """
    number = normalise_gstin(gstin)
    if check_gstin(number).ok:
        return []
    found: set[str] = set()
    for index, char in enumerate(number):
        swap = _LOOKALIKE.get(char)
        if swap is None:
            continue
        candidate = number[:index] + swap + number[index + 1 :]
        if check_gstin(candidate).ok:
            found.add(candidate)
    return sorted(found)


def mask_aadhaar(text: str) -> str:
    """Mask every Aadhaar-like number (12 digits, Verhoeff-valid) as "XXXX XXXX 1234"."""

    def replace(match: re.Match[str]) -> str:
        digits = "".join(match.groups())
        if aadhaar.is_valid(digits):
            return f"XXXX XXXX {digits[-4:]}"
        return match.group(0)

    return _AADHAAR.sub(replace, text)


def check_pan(raw: str) -> bool:
    """PAN-FORMAT: ten characters in the PAN pattern with a known holder type."""
    return bool(stdnum_pan.is_valid(raw))


def check_udyam(raw: str) -> bool:
    """UDYAM-FORMAT: UDYAM-XX-00-0000000. Munim cannot check that the registration exists."""
    return bool(_UDYAM.match(raw.strip().upper()))


def check_ifsc_format(raw: str) -> bool:
    """IFSC shape: 4 letters, a zero, 6 letters or digits."""
    return bool(_IFSC.match(raw.strip().upper()))
