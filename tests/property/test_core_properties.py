"""Property tests for the pure core (docs/TESTING.md section 3)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from munim_core.clock import BankRate, ClockInput, compute
from munim_core.dates import add_months
from munim_core.ids import check_gstin, normalise_gstin
from munim_core.money import format_inr, parse_inr
from munim_core.text import to_ascii_digits
from munim_core.verify import run_all
from munim_core.verify.cross import normalise_description, normalise_name, normalise_reference
from munim_core.verify.models import CaseState, ClaimValue, PaperState, Status
from tests.ref_gstin import ALPHABET, check_character, checksum_ok

pytestmark = pytest.mark.property

RATE = (BankRate(date(2000, 1, 1), Decimal("6")),)
principals = st.integers(min_value=0, max_value=10**11)
starts = st.dates(min_value=date(2017, 7, 1), max_value=date(2030, 12, 31))


def interest(principal: int, acceptance: date, as_on: date) -> int:
    return compute(
        ClockInput(
            acceptance_date=acceptance,
            agreement="written",
            credit_days=0,
            principal_paise=principal,
            as_on=as_on,
            rates=RATE,
        )
    ).interest_paise


# 1. money round trip
@given(st.integers(min_value=0, max_value=10**12))
def test_parse_of_format_is_identity(paise: int) -> None:
    assert parse_inr(format_inr(paise)) == paise


# 2. interest is non-negative, non-decreasing in as_on, monotonic in principal
@given(principals, starts, st.integers(0, 800), st.integers(0, 60))
def test_interest_is_non_negative_and_non_decreasing_in_days(
    principal: int, acceptance: date, days: int, more: int
) -> None:
    a = interest(principal, acceptance, acceptance + timedelta(days=days))
    b = interest(principal, acceptance, acceptance + timedelta(days=days + more))
    assert 0 <= a <= b


@given(principals, principals, starts, st.integers(0, 800))
def test_interest_is_monotonic_in_principal(p1: int, p2: int, acceptance: date, days: int) -> None:
    low, high = sorted((p1, p2))
    as_on = acceptance + timedelta(days=days)
    assert interest(low, acceptance, as_on) <= interest(high, acceptance, as_on)


# 3. nothing is owed until a whole day after the due date has passed
@given(principals, starts, st.integers(0, 400))
def test_interest_is_zero_until_the_day_after_the_due_date(
    principal: int, due: date, back: int
) -> None:
    for as_on in (due - timedelta(days=back), due, due + timedelta(days=1)):
        assert interest(principal, due, as_on) == 0


# 4. monthly rounding stays within one paisa per month of the closed form
@given(principals, starts, st.integers(1, 36))
def test_whole_months_stay_close_to_the_closed_form(principal: int, due: date, months: int) -> None:
    start = due + timedelta(days=1)
    computed = interest(principal, due, add_months(start, months))
    closed = Decimal(principal) * ((1 + Decimal("0.015")) ** months - 1)
    assert abs(Decimal(computed) - closed) <= months


# 5. restarting at a month boundary with the new balance gives the same result
@given(
    principals,
    st.dates(min_value=date(2017, 7, 1), max_value=date(2030, 12, 31)).filter(
        lambda d: d.day <= 28
    ),
    st.integers(1, 24),
    st.integers(0, 24),
)
def test_restart_at_a_month_boundary_is_invariant(
    principal: int, start: date, k: int, rest: int
) -> None:
    due = start - timedelta(days=1)
    end = add_months(start, k + rest)
    straight = interest(principal, due, end)
    boundary = add_months(start, k)
    first = interest(principal, due, boundary)
    second = interest(principal + first, boundary - timedelta(days=1), end)
    assert straight == first + second


# 6. GSTIN checks agree with the pure-Python reference
gstin_bodies = st.builds(
    lambda state, letters, digits, letter, entity: f"{state:02d}{letters}{digits}{letter}{entity}Z",
    st.integers(1, 37),
    st.text("ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=5, max_size=5).map(lambda s: s[:3] + "P" + s[4]),
    st.text("0123456789", min_size=4, max_size=4).filter(lambda s: s != "0000"),
    st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    st.sampled_from("123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
)


@given(gstin_bodies)
def test_appending_the_reference_check_character_passes(body: str) -> None:
    assert check_gstin(body + check_character(body)).ok


@given(gstin_bodies, st.sampled_from(ALPHABET))
def test_checksum_verdict_matches_the_reference_for_any_last_character(
    body: str, last: str
) -> None:
    value = body + last
    assert ("GSTIN-CHECKSUM" in check_gstin(value).errors) == (not checksum_ok(value))


@given(st.text(max_size=20))
def test_gstin_check_never_raises(text: str) -> None:
    result = check_gstin(text)
    assert result.ok == (result.errors == ())


# 8. normalisers are idempotent
@given(st.text(max_size=40))
def test_normalisers_are_idempotent(text: str) -> None:
    for normalise in (
        normalise_gstin,
        normalise_name,
        normalise_reference,
        normalise_description,
        to_ascii_digits,
    ):
        once = normalise(text)
        assert normalise(once) == once, normalise.__name__


# 9. verify never raises on arbitrary text
INVOICE_FIELDS = (
    "supplier_gstin",
    "buyer_gstin",
    "invoice_number",
    "invoice_date",
    "place_of_supply",
    "taxable_total",
    "cgst",
    "sgst",
    "igst",
    "round_off",
    "invoice_total",
    "supplier_pan",
    "supplier_name",
    "buyer_name",
    "po_reference",
)
CHALLAN_FIELDS = (
    "supplier_gstin",
    "buyer_gstin",
    "challan_date",
    "received_date",
    "invoice_reference",
    "receiver_stamp_present",
    "receiver_signature_present",
    "buyer_name",
    "supplier_name",
    "po_reference",
)
PO_FIELDS = ("buyer_gstin", "po_number", "po_date", "buyer_name", "credit_days")
values = st.one_of(
    st.none(),
    st.text(max_size=24),
    st.sampled_from(["0", "1,00,000.00", "-0.22", "04/07/2026", "27AAPFU0939F1ZV", "yes"]),
)


def paper_strategy(
    kind: str, names: tuple[str, ...], line_names: tuple[str, ...]
) -> st.SearchStrategy[PaperState]:
    claim = values.map(lambda v: ClaimValue(raw=v, text=v, source="model"))
    return st.builds(
        lambda fields, lines: PaperState(kind, fields, tuple(lines)),
        st.fixed_dictionaries(dict.fromkeys(names, claim)),
        st.lists(st.fixed_dictionaries(dict.fromkeys(line_names, claim)), max_size=3),
    )


@given(
    paper_strategy(
        "invoice", INVOICE_FIELDS, ("description", "quantity", "unit", "rate", "amount")
    ),
    paper_strategy("challan", CHALLAN_FIELDS, ("description", "quantity", "unit")),
    paper_strategy("po", PO_FIELDS, ("description", "quantity", "unit", "rate")),
    st.one_of(st.none(), starts),
    st.one_of(st.none(), st.text(max_size=20)),
)
def test_verify_never_raises_on_arbitrary_values(
    inv: PaperState, ch: PaperState, order: PaperState, as_on: date | None, udyam: str | None
) -> None:
    state = CaseState({"invoice": inv, "challan": ch, "po": order}, as_on=as_on, udyam_number=udyam)
    findings = run_all(state, date(2026, 10, 13))
    assert findings
    for f in findings:
        assert f.status in set(Status)
        assert all(isinstance(v, str) for v in f.params.values())
        assert f.message_key.startswith(("rule.", "check."))
