"""Schemas, normalisation and prompt files of the model layer (docs/AI_SPEC.md sections 3, 4)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from munim_ai.normalize import clean_value, drafts_from_read
from munim_ai.prompts import (
    USER_TURN,
    extraction_prompt,
    load,
    reread_prompt,
    strict_suffix,
)
from munim_ai.schemas import (
    ANCHORS,
    LINE_FIELDS,
    MAX_VALUE_CHARS,
    PAPER_FIELDS,
    Field_,
    InvoiceRead,
    compact_schema,
    field_spec,
    parse_box,
    read_model_for,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "packages/munim_core/src/munim_core/verify"


# ---------------------------------------------------------------- boxes
def test_parse_box_accepts_an_ordered_box_on_the_grid() -> None:
    box = parse_box([100, 200, 150, 400])
    assert box is not None
    assert box.as_tuple() == (100, 200, 150, 400)


@pytest.mark.parametrize(
    "raw",
    [
        [150, 200, 100, 400],  # inverted
        [100, 200, 100, 400],  # zero height
        [0, 0, 1001, 10],  # off the grid
        [-1, 0, 10, 10],
        [1, 2, 3],  # wrong length
        ["1", 2, 3, 4],  # not numbers
        [True, 2, 3, 4],
        None,
        "0,0,10,10",
    ],
)
def test_parse_box_drops_a_bad_box(raw: object) -> None:
    assert parse_box(raw) is None


# ---------------------------------------------------------------- fields
def test_field_keeps_value_and_drops_only_a_bad_box() -> None:
    field = Field_.model_validate({"value": "INV-7", "box_2d": [9, 9, 1, 1]})
    assert field.value == "INV-7"
    assert field.box_2d is None


@pytest.mark.parametrize(
    ("raw", "value"),
    [(True, "yes"), (False, "no"), (12, "12"), (12.5, "12.5"), ("x", "x"), (None, None)],
)
def test_field_coerces_bare_values_to_text(raw: object, value: str | None) -> None:
    assert Field_.model_validate(raw).value == value


def test_field_coerces_numbers_and_booleans_inside_an_object() -> None:
    assert Field_.model_validate({"value": 500000}).value == "500000"
    assert Field_.model_validate({"value": True}).value == "yes"


def test_runaway_value_is_dropped_and_flagged() -> None:
    field = Field_.model_validate({"value": "9" * (MAX_VALUE_CHARS + 1)})
    assert field.value is None
    assert field.runaway is True
    edge = Field_.model_validate({"value": "9" * MAX_VALUE_CHARS})
    assert edge.value == "9" * MAX_VALUE_CHARS
    assert edge.runaway is False


def test_note_is_capped_at_120_characters() -> None:
    assert Field_.model_validate({"value": "a", "note": "n" * 500}).note == "n" * 120


def test_invoice_read_ignores_unknown_fields_and_accepts_null_lines() -> None:
    read = InvoiceRead.model_validate(
        {"invoice_total": "5,00,000.00", "colour": "blue", "line_items": None}
    )
    assert read.invoice_total is not None
    assert read.invoice_total.value == "5,00,000.00"
    assert read.line_items == []


def test_more_than_twelve_lines_is_a_validation_error() -> None:
    with pytest.raises(ValueError):
        InvoiceRead.model_validate({"line_items": [{}] * 13})


def test_read_model_for_each_kind_and_unknown() -> None:
    assert {read_model_for(k).__name__ for k in ("invoice", "challan", "po")} == {
        "InvoiceRead",
        "ChallanRead",
        "PORead",
    }
    with pytest.raises(KeyError):
        read_model_for("receipt")


def test_every_field_the_core_rules_read_is_in_the_schema() -> None:
    names: set[str] = set()
    for path in VERIFY.glob("*.py"):
        names |= set(
            re.findall(
                r'"((?:supplier|buyer|invoice|challan|po|received|receiver|taxable|place|round|bank|credit|payment|delivery)_[a-z_]+)"',
                path.read_text(),
            )
        )
    known = set().union(*PAPER_FIELDS.values()) | {"cgst", "sgst", "igst"}
    missing = {n for n in names if n not in known and not n.endswith(("_key", "_paise", "_qty"))}
    assert not missing, sorted(missing)


def test_anchor_fields_exist_in_their_paper() -> None:
    for kind, anchors in ANCHORS.items():
        assert set(anchors) <= set(PAPER_FIELDS[kind])


@pytest.mark.parametrize("kind", ["invoice", "challan", "po"])
def test_compact_schema_names_every_field_once(kind: str) -> None:
    schema = compact_schema(kind)
    for name in (*PAPER_FIELDS[kind], *LINE_FIELDS[kind]):
        assert f'"{name}"' in schema
    assert f'"kind": "{kind}"' in schema
    assert schema.count('"invoice_total"') <= 1


# ---------------------------------------------------------------- normalisation
def test_clean_value_trims_folds_whitespace_and_converts_digits() -> None:
    assert clean_value("  ₹ १,२००.००\n kg ") == "₹ 1,200.00 kg"
    assert clean_value("   ") is None
    assert clean_value(None) is None


def test_clean_value_masks_an_aadhaar_like_number() -> None:
    synthetic = "Aadhaar " + "2345 6789 0124"  # synthetic test number, not a real Aadhaar
    cleaned = clean_value(synthetic)
    assert cleaned is not None
    assert "2345 6789" not in cleaned


@given(st.text(max_size=60))
def test_clean_value_is_idempotent(text: str) -> None:
    once = clean_value(text)
    assert clean_value(once) == once


def test_drafts_keep_boxes_as_returned_and_flag_runaways() -> None:
    read = InvoiceRead.model_validate(
        {
            "invoice_number": {"value": " SF/0412 ", "box_2d": [10, 20, 30, 40]},
            "supplier_name": {"value": "x" * 300},
            "line_items": [{"quantity": {"value": "1,200"}, "amount": "3,00,000.00"}],
        }
    )
    drafts = {(d.field, d.index): d for d in drafts_from_read("invoice", read)}
    number = drafts[("invoice_number", None)]
    assert (number.value, number.box) == ("SF/0412", (10, 20, 30, 40))
    assert drafts[("supplier_name", None)].flag == "runaway"
    assert drafts[("supplier_name", None)].value is None
    assert drafts[("quantity", 0)].value == "1,200"
    assert drafts[("amount", 0)].value == "3,00,000.00"
    assert drafts[("buyer_gstin", None)].value is None
    assert len(drafts) == len(PAPER_FIELDS["invoice"]) + len(LINE_FIELDS["invoice"])


# ---------------------------------------------------------------- prompts
@pytest.mark.parametrize("kind", ["invoice", "challan", "po"])
def test_extraction_prompt_has_version_schema_and_injection_guard(kind: str) -> None:
    prompt = extraction_prompt(kind)
    assert prompt.version.isdigit()
    assert compact_schema(kind) in prompt.text
    assert "{schema}" not in prompt.text
    assert "instruction" in prompt.text.lower()  # text on the paper is data, not instructions
    assert kind in USER_TURN


@pytest.mark.parametrize(
    "name",
    [
        "invoice.system.md",
        "challan.system.md",
        "po.system.md",
        "reread.system.md",
        "strict_suffix.md",
    ],
)
def test_prompts_ask_for_transcription_not_judgement(name: str) -> None:
    text = load(name).text.lower()
    for phrase in ("verify", "validate", "check whether", "is correct", "is valid"):
        assert phrase not in text, phrase


def test_reread_prompt_names_the_field_and_its_format_but_no_value() -> None:
    prompt = reread_prompt(field_spec("buyer_gstin"))
    assert "buyer's GSTIN" in prompt.text
    assert "15 characters" in prompt.text
    assert "{" + "field_label}" not in prompt.text
    assert field_spec("vehicle_number").label == "vehicle number"


def test_strict_suffix_asks_for_json_only() -> None:
    assert "JSON" in strict_suffix()
