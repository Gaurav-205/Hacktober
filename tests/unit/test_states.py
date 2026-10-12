"""Place-of-supply reading (munim_core.states)."""

from __future__ import annotations

import pytest

from munim_core.ids import GSTIN_STATE_CODES
from munim_core.states import STATE_NAMES, state_code_from_text

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("27-Maharashtra", "27"),
        ("MAHARASHTRA (27)", "27"),
        ("Maharashtra", "27"),
        ("Karnataka", "29"),
        ("Andhra Pradesh", "37"),
        ("Arunachal Pradesh", "12"),
        ("Orissa", "21"),
        ("J&K", "01"),
        ("New Delhi", "07"),
        ("Place of supply: 09", "09"),
    ],
)
def test_state_code_from_printed_place_of_supply(text: str, code: str) -> None:
    assert state_code_from_text(text) == code


@pytest.mark.parametrize("text", ["", "Somewhere", "99", "Mahara"])
def test_unknown_places_give_no_code(text: str) -> None:
    assert state_code_from_text(text) is None


def test_every_named_state_is_a_known_gstin_state_code() -> None:
    assert set(STATE_NAMES) == set(GSTIN_STATE_CODES)
