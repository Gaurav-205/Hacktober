"""GST state and territory codes, used to read a printed place of supply.

The codes are the first two digits of a GSTIN. Names are matched case-insensitively, with
common alternative spellings.
"""

from __future__ import annotations

import re

__all__ = ["STATE_NAMES", "state_code_from_text"]

STATE_NAMES: dict[str, tuple[str, ...]] = {
    "01": ("Jammu and Kashmir", "J&K"),
    "02": ("Himachal Pradesh",),
    "03": ("Punjab",),
    "04": ("Chandigarh",),
    "05": ("Uttarakhand", "Uttaranchal"),
    "06": ("Haryana",),
    "07": ("Delhi", "New Delhi", "NCT of Delhi"),
    "08": ("Rajasthan",),
    "09": ("Uttar Pradesh",),
    "10": ("Bihar",),
    "11": ("Sikkim",),
    "12": ("Arunachal Pradesh",),
    "13": ("Nagaland",),
    "14": ("Manipur",),
    "15": ("Mizoram",),
    "16": ("Tripura",),
    "17": ("Meghalaya",),
    "18": ("Assam",),
    "19": ("West Bengal",),
    "20": ("Jharkhand",),
    "21": ("Odisha", "Orissa"),
    "22": ("Chhattisgarh", "Chattisgarh"),
    "23": ("Madhya Pradesh",),
    "24": ("Gujarat",),
    "25": ("Daman and Diu",),
    "26": ("Dadra and Nagar Haveli and Daman and Diu", "Dadra and Nagar Haveli"),
    "27": ("Maharashtra",),
    "28": ("Andhra Pradesh (before 2014)",),
    "29": ("Karnataka",),
    "30": ("Goa",),
    "31": ("Lakshadweep",),
    "32": ("Kerala",),
    "33": ("Tamil Nadu",),
    "34": ("Puducherry", "Pondicherry"),
    "35": ("Andaman and Nicobar Islands",),
    "36": ("Telangana",),
    "37": ("Andhra Pradesh",),
    "38": ("Ladakh",),
    "97": ("Other Territory",),
}

_CODE = re.compile(r"(?<!\d)(\d{2})(?!\d)")


def _norm(text: str) -> str:
    text = text.lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text).split())


_BY_NAME = sorted(
    ((_norm(name), code) for code, names in STATE_NAMES.items() for name in names),
    key=lambda item: -len(item[0]),
)


def state_code_from_text(text: str) -> str | None:
    """Return the state code a printed place of supply names, or None if it names none.

    A two-digit code wins over a name ("27-Maharashtra" is 27). Longer names are tried first,
    so "Andhra Pradesh" never matches inside "Arunachal Pradesh" by accident.
    """
    for match in _CODE.finditer(text):
        if match.group(1) in STATE_NAMES:
            return match.group(1)
    padded = f" {_norm(text)} "
    for name, code in _BY_NAME:
        if f" {name} " in padded:
            return code
    return None
