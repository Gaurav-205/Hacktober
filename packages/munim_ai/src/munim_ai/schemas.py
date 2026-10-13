"""What the model may return, as Pydantic models (docs/AI_SPEC.md section 3).

The model only transcribes: every field is a string as printed (or null) with an optional box on
a 0 to 1000 grid. Nothing here interprets a value; normalisation and checks happen elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "FIELD_SPECS",
    "LINE_FIELDS",
    "PAPER_FIELDS",
    "Box",
    "ChallanRead",
    "FieldSpec",
    "Field_",
    "InvoiceRead",
    "LineItem",
    "PORead",
    "PaperKind",
    "PaperRead",
    "compact_schema",
    "parse_box",
    "read_model_for",
]

PaperKind = Literal["invoice", "challan", "po"]
MAX_VALUE_CHARS = 200
MAX_NOTE_CHARS = 120
MAX_LINES = 12


class Box(BaseModel):
    """[y1, x1, y2, x2] on a 1000 x 1000 grid over the image the model was given."""

    model_config = ConfigDict(frozen=True)

    y1: int = Field(ge=0, le=1000)
    x1: int = Field(ge=0, le=1000)
    y2: int = Field(ge=0, le=1000)
    x2: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def _ordered(self) -> Box:
        if not (self.y1 < self.y2 and self.x1 < self.x2):
            raise ValueError("box corners are not in order")
        return self

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.y1, self.x1, self.y2, self.x2)


def parse_box(raw: object) -> Box | None:
    """A valid box from the model's list, or None (a bad box is dropped; the value stays)."""
    if not isinstance(raw, list | tuple) or len(raw) != 4:
        return None
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in raw):
        return None
    try:
        return Box(y1=round(raw[0]), x1=round(raw[1]), y2=round(raw[2]), x2=round(raw[3]))
    except ValueError:
        return None


class Field_(BaseModel):  # noqa: N801 - the trailing underscore avoids clashing with pydantic.Field
    """One transcribed value. `runaway` is set when an over-long value was dropped."""

    value: str | None = None
    box_2d: Box | None = None
    note: str | None = None
    runaway: bool = False

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if data is None:
            return {"value": None}
        if isinstance(data, str | int | float) and not isinstance(data, bool):
            return {"value": str(data)}
        if isinstance(data, bool):
            return {"value": "yes" if data else "no"}
        if isinstance(data, dict):
            out = dict(data)
            value = out.get("value")
            if isinstance(value, bool):
                out["value"] = "yes" if value else "no"
            elif isinstance(value, int | float):
                out["value"] = str(value)
            out["box_2d"] = parse_box(out.get("box_2d"))
            note = out.get("note")
            out["note"] = note[:MAX_NOTE_CHARS] if isinstance(note, str) else None
            text = out.get("value")
            if isinstance(text, str) and len(text) > MAX_VALUE_CHARS:
                out["value"], out["runaway"] = None, True
            return out
        return data


OptField = Field_ | None


class LineItem(BaseModel):
    description: OptField = None
    hsn_sac: OptField = None
    quantity: OptField = None
    unit: OptField = None
    rate: OptField = None
    amount: OptField = None


class _PaperRead(BaseModel):
    line_items: list[LineItem] = Field(default_factory=list, max_length=MAX_LINES)

    @field_validator("line_items", mode="before")
    @classmethod
    def _lines(cls, value: Any) -> Any:
        return [] if value is None else value


class InvoiceRead(_PaperRead):
    kind: Literal["invoice"] = "invoice"
    supplier_name: OptField = None
    supplier_gstin: OptField = None
    supplier_pan: OptField = None
    buyer_name: OptField = None
    buyer_gstin: OptField = None
    invoice_number: OptField = None
    invoice_date: OptField = None
    place_of_supply: OptField = None
    taxable_total: OptField = None
    cgst: OptField = None
    sgst: OptField = None
    igst: OptField = None
    round_off: OptField = None
    invoice_total: OptField = None
    po_reference: OptField = None
    challan_reference: OptField = None
    bank_ifsc: OptField = None


class ChallanRead(_PaperRead):
    kind: Literal["challan"] = "challan"
    supplier_name: OptField = None
    supplier_gstin: OptField = None
    buyer_name: OptField = None
    buyer_gstin: OptField = None
    challan_number: OptField = None
    challan_date: OptField = None
    invoice_reference: OptField = None
    po_reference: OptField = None
    receiver_stamp_present: OptField = None
    receiver_signature_present: OptField = None
    received_date: OptField = None
    vehicle_number: OptField = None


class PORead(_PaperRead):
    kind: Literal["po"] = "po"
    buyer_name: OptField = None
    buyer_gstin: OptField = None
    po_number: OptField = None
    po_date: OptField = None
    supplier_name: OptField = None
    supplier_gstin: OptField = None
    payment_terms_text: OptField = None
    credit_days: OptField = None
    delivery_date: OptField = None


PaperRead = InvoiceRead | ChallanRead | PORead
_MODELS: dict[str, type[_PaperRead]] = {
    "invoice": InvoiceRead,
    "challan": ChallanRead,
    "po": PORead,
}

PAPER_FIELDS: dict[str, tuple[str, ...]] = {
    kind: tuple(n for n in model.model_fields if n not in ("kind", "line_items"))
    for kind, model in _MODELS.items()
}
LINE_FIELDS: dict[str, tuple[str, ...]] = {
    "invoice": ("description", "hsn_sac", "quantity", "unit", "rate", "amount"),
    "challan": ("description", "quantity", "unit"),
    "po": ("description", "quantity", "unit", "rate"),
}
# Fields a read must contain for a partial result to be kept (AI_SPEC 6, PLAN_REVIEW).
ANCHORS: dict[str, tuple[str, ...]] = {
    "invoice": ("invoice_total", "supplier_gstin", "buyer_gstin"),
    "challan": ("challan_number", "supplier_gstin"),
    "po": ("po_number", "buyer_gstin"),
}


def read_model_for(kind: str) -> type[_PaperRead]:
    return _MODELS[kind]


@dataclass(frozen=True)
class FieldSpec:
    """A field to re-read on its own: its name, a plain label and the format hint for the prompt."""

    name: str
    label: str
    format_hint: str = ""


_GSTIN_HINT = (
    "A GSTIN is 15 characters: 2 digits, 5 letters, 4 digits, 1 letter, 1 letter or digit, "
    "the letter Z, 1 letter or digit."
)
FIELD_SPECS: dict[str, FieldSpec] = {
    "supplier_gstin": FieldSpec("supplier_gstin", "supplier's GSTIN", _GSTIN_HINT),
    "buyer_gstin": FieldSpec("buyer_gstin", "buyer's GSTIN", _GSTIN_HINT),
    "invoice_total": FieldSpec("invoice_total", "invoice total amount", "An amount in rupees."),
    "taxable_total": FieldSpec("taxable_total", "taxable value total", "An amount in rupees."),
    "invoice_date": FieldSpec("invoice_date", "invoice date", "A date as printed."),
    "challan_date": FieldSpec("challan_date", "challan date", "A date as printed."),
}


def field_spec(name: str) -> FieldSpec:
    return FIELD_SPECS.get(name, FieldSpec(name, name.replace("_", " ")))


def compact_schema(kind: str) -> str:
    """The JSON shape the prompt asks for, written compactly from the Pydantic model."""
    field_shape = '{"value": string|null, "box_2d": [y1,x1,y2,x2]|null}'
    parts = [f'"kind": "{kind}"']
    for name in PAPER_FIELDS[kind]:
        if name in ("receiver_stamp_present", "receiver_signature_present"):
            parts.append(f'"{name}": {{"value": "yes"|"no"|"unknown", "box_2d": null}}')
        else:
            parts.append(f'"{name}": {field_shape}')
    line = ", ".join(f'"{n}": {field_shape}' for n in LINE_FIELDS[kind])
    parts.append(f'"line_items": [{{{line}}}] (at most {MAX_LINES})')
    return "{" + ", ".join(parts) + "}"
