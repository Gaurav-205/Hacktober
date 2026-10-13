"""Generate Munim's synthetic evaluation set (docs/AI_SPEC.md section 8.1).

Everything here is synthetic: invented company names, GSTINs built with the checksum
algorithm on the pattern AAAPZ####Z, invented amounts. Output under eval/fixtures/:

- papers/<id>.jpg and demo/{invoice,challan,po}.jpg: rendered papers with seeded photo damage;
- truth/<id>.json: every printed value with its box ([y1, x1, y2, x2] on the 0-1000 grid of the
  final image), the simulated misreads in that paper's recording, and any injected fault;
- replay/*.json: the recorded responses the replay reader returns (recorded_from "synthetic");
- samples/invoice_sample.pdf: one PDF sample (Latin text only);
- manifest.json: files with sha256 and size, papers, cases and injected variants.

The recordings are hand-built from the truth with a seeded set of misreads, so evaluation
numbers on this set prove the harness, not the model. The same seed gives byte-identical files
on the same machine. Exit codes: 0 written, 1 refused (files exist; use --force), 2 error.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from fontTools.ttLib import TTFont  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from munim_ai.prompts import extraction_prompt, load  # noqa: E402
from munim_ai.providers.base import ReadContext  # noqa: E402
from munim_ai.providers.replay import write_recording  # noqa: E402
from munim_ai.schemas import PaperKind  # noqa: E402
from munim_core.ids import check_gstin, lookalike_candidates  # noqa: E402
from munim_core.money import format_inr  # noqa: E402
from tests.ref_gstin import check_character  # noqa: E402

OUT = ROOT / "eval" / "fixtures"
FONTS = ROOT / "packages/munim_web/src/munim_web/static/fonts"
SEED = 20261013
WIDTH, HEIGHT = 900, 1273
RECORDED_AT = "2026-10-13T00:00:00+00:00"
MISREAD_RATE = 0.07
CONFUSIONS = {"0": "O", "O": "0", "1": "I", "I": "1", "5": "S", "S": "5", "8": "B", "B": "8"}
STATES = {"09": "Uttar Pradesh", "27": "Maharashtra", "24": "Gujarat", "29": "Karnataka"}
SUPPLIERS = [
    "Sample Fabricators Pvt Ltd",
    "Example Castings LLP",
    "Specimen Polymers Pvt Ltd",
    "Placeholder Tools & Dies",
    "Model Wire Products",
    "Mock Packaging Works",
]
BUYERS = ["Demo Textiles Ltd", "Trial Motors Pvt Ltd", "Instance Foods Ltd", "Pattern Pumps Ltd"]
ITEMS = [
    ("MS angle 40x40x5", "7216", "kg"),
    ("MS flat 50x6", "7211", "lot"),
    ("HDPE granules", "3901", "kg"),
    ("Copper wire 2.5 mm", "7408", "m"),
    ("Corrugated box 5 ply", "4819", "nos"),
    ("Brass fitting 1/2 in", "7412", "nos"),
    ("Steel bolt M12", "7318", "nos"),
]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def require(condition: bool, message: str) -> None:
    """Stop with an error when a fixture invariant does not hold (asserts vanish under -O)."""
    if not condition:
        raise ValueError(message)


# ---------------------------------------------------------------- fonts
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    font = TTFont(str(FONTS / name))
    font.flavor = None
    data = io.BytesIO()
    font.save(data)
    data.seek(0)
    return ImageFont.truetype(data, size)


class Fonts:
    def __init__(self) -> None:
        self.text = _font("mukta-latin-400-normal.woff2", 19)
        self.bold = _font("mukta-latin-600-normal.woff2", 21)
        self.title = _font("mukta-latin-600-normal.woff2", 30)
        self.hindi = _font("mukta-devanagari-500-normal.woff2", 24)


# ---------------------------------------------------------------- synthetic values
def gstin(state: str, number: int) -> str:
    prefix = f"{state}AAAPZ{number:04d}Z1Z"
    return prefix + check_character(prefix)


def amount(paise: int) -> str:
    """Indian grouping without the rupee sign, as printed on a bill: 3,00,000.00."""
    return format_inr(paise).replace("₹", "")


def numeric_date(day: int, month: int, year: int = 2026) -> str:
    return f"{day:02d}/{month:02d}/{year}"


def word_date(day: int, month: int, year: int = 2026) -> str:
    return f"{day:02d} {MONTHS[month - 1]} {year}"


@dataclass
class Line:
    description: str
    hsn: str
    unit: str
    qty: int
    rate_paise: int

    @property
    def amount_paise(self) -> int:
        return self.qty * self.rate_paise


@dataclass
class Case:
    id: str
    supplier: str
    supplier_gstin: str
    buyer: str
    buyer_gstin: str
    po_number: str
    po_date: tuple[int, int]
    challan_number: str
    challan_date: tuple[int, int]
    invoice_number: str
    invoice_date: tuple[int, int]
    credit_days: int
    lines: list[Line]
    kinds: tuple[str, ...]
    stamp: bool = True
    ambiguous_invoice_date: bool = False
    demo: bool = False


def demo_case() -> Case:
    return Case(
        id="demo",
        supplier="Sample Fabricators Pvt Ltd",
        supplier_gstin=gstin("09", 1234),
        buyer="Demo Textiles Ltd",
        buyer_gstin=gstin("27", 5678),
        po_number="PO-2026-0117",
        po_date=(2, 3),
        challan_number="CH-0412",
        challan_date=(20, 3),
        invoice_number="SF/2025-26/0412",
        invoice_date=(21, 3),
        credit_days=30,
        lines=[
            Line("MS angle 40x40x5", "7216", "kg", 1200, 25_000),
            Line("MS flat 50x6", "7211", "lot", 1, 12_372_900),
        ],
        kinds=("invoice", "challan", "po"),
        demo=True,
    )


def random_case(rng: random.Random, index: int, kinds: tuple[str, ...]) -> Case:
    supplier_state, buyer_state = rng.choice(
        [("09", "27"), ("27", "27"), ("24", "29"), ("29", "29")]
    )
    month = rng.randint(4, 9)
    challan_day = rng.randint(13, 24)
    lines = []
    for item in rng.sample(ITEMS, rng.randint(1, 3)):
        qty = rng.randint(2, 900)
        rate = rng.randint(40, 2500) * 100 + rng.choice([0, 50])
        lines.append(Line(item[0], item[1], item[2], qty, rate))
    return Case(
        id=f"case-{index:02d}",
        supplier=rng.choice(SUPPLIERS[1:]),
        supplier_gstin=gstin(supplier_state, 2000 + index * 37),
        buyer=rng.choice(BUYERS[1:]),
        buyer_gstin=gstin(buyer_state, 6000 + index * 41),
        po_number=f"PO-2026-{rng.randint(200, 999):04d}",
        po_date=(rng.randint(1, 12), month),
        challan_number=f"DC-{rng.randint(1000, 9999)}",
        challan_date=(challan_day, month),
        invoice_number=f"INV/26-27/{rng.randint(10, 999):03d}",
        invoice_date=(challan_day + rng.randint(0, 3), month),
        credit_days=rng.choice([15, 30, 45, 60]),
        lines=lines,
        kinds=kinds,
        stamp=rng.random() > 0.2,
    )


def taxes(case: Case) -> dict[str, int]:
    taxable = sum(line.amount_paise for line in case.lines)
    inter = case.supplier_gstin[:2] != case.buyer_gstin[:2]
    if inter:
        igst = (taxable * 18 + 50) // 100
        tax = {"igst": igst}
    else:
        half = (taxable * 9 + 50) // 100
        tax = {"cgst": half, "sgst": half}
    gross = taxable + sum(tax.values())
    total = (gross + 50) // 100 * 100  # nearest whole rupee
    return {"taxable": taxable, **tax, "round_off": total - gross, "total": total}


# ---------------------------------------------------------------- rendering
@dataclass
class Sheet:
    fonts: Fonts
    image: Image.Image = field(init=False)
    draw: ImageDraw.ImageDraw = field(init=False)
    boxes: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)
    values: dict[str, str] = field(default_factory=dict)
    lines: list[dict[str, dict[str, Any]]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.image = Image.new("RGB", (WIDTH, HEIGHT), (250, 249, 245))
        self.draw = ImageDraw.Draw(self.image)

    def text(
        self, xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont
    ) -> tuple[int, int, int, int]:
        self.draw.text(xy, text, fill=(25, 25, 30), font=font)
        box = self.draw.textbbox(xy, text, font=font)
        return (int(box[0]), int(box[1]), int(box[2]), int(box[3]))

    def value(self, name: str, xy: tuple[int, int], label: str, text: str) -> None:
        label_box = self.text(xy, f"{label}:", self.fonts.text)
        box = self.text((label_box[2] + 8, xy[1]), text, self.fonts.bold)
        self.boxes[name] = box
        self.values[name] = text

    def title(self, hindi: str, english: str) -> None:
        self.draw.text((60, 40), hindi, fill=(25, 25, 30), font=self.fonts.hindi)
        self.text((60, 80), english, self.fonts.title)
        self.draw.line((60, 128, WIDTH - 60, 128), fill=(40, 40, 40), width=2)

    def table(
        self, top: int, header: list[tuple[str, int]], rows: list[list[tuple[str, str]]]
    ) -> int:
        y = top
        for label, x in header:
            self.text((x, y), label, self.fonts.bold)
        y += 34
        self.draw.line((60, y - 4, WIDTH - 60, y - 4), fill=(120, 120, 120), width=1)
        for row in rows:
            cells: dict[str, dict[str, Any]] = {}
            for (name, text), (_, x) in zip(row, header, strict=True):
                box = self.text((x, y), text, self.fonts.text)
                cells[name] = {"value": text, "box": box}
            self.lines.append(cells)
            y += 32
        self.draw.line((60, y, WIDTH - 60, y), fill=(120, 120, 120), width=1)
        return y + 20


def render_invoice(case: Case, fonts: Fonts, overrides: dict[str, str]) -> Sheet:
    s = Sheet(fonts)
    s.title("कर बीजक", "TAX INVOICE")
    t = taxes(case)
    day, month = case.invoice_date
    date_text = (
        numeric_date(month, day) if case.ambiguous_invoice_date else numeric_date(day, month)
    )
    v = {
        "supplier_name": case.supplier,
        "supplier_gstin": case.supplier_gstin,
        "buyer_name": case.buyer,
        "buyer_gstin": case.buyer_gstin,
        "invoice_number": case.invoice_number,
        "invoice_date": date_text,
        "place_of_supply": f"{case.buyer_gstin[:2]}-{STATES[case.buyer_gstin[:2]]}",
        "po_reference": case.po_number,
        "challan_reference": case.challan_number if "challan" in case.kinds else "",
        "taxable_total": amount(t["taxable"]),
        "invoice_total": amount(t["total"]),
        "round_off": amount(t["round_off"])
        if t["round_off"] >= 0
        else "-" + amount(-t["round_off"]),
        "bank_ifsc": "SBIN0001234",
    }
    for tax in ("igst", "cgst", "sgst"):
        if tax in t:
            v[tax] = amount(t[tax])
    v.update(overrides)
    s.value("supplier_name", (60, 150), "Supplier", v["supplier_name"])
    s.value("supplier_gstin", (60, 182), "GSTIN", v["supplier_gstin"])
    s.value("invoice_number", (520, 150), "Invoice No", v["invoice_number"])
    s.value("invoice_date", (520, 182), "Date", v["invoice_date"])
    s.value("buyer_name", (60, 240), "Bill to", v["buyer_name"])
    s.value("buyer_gstin", (60, 272), "GSTIN", v["buyer_gstin"])
    s.value("place_of_supply", (60, 304), "Place of supply", v["place_of_supply"])
    s.value("po_reference", (520, 240), "PO No", v["po_reference"])
    if v["challan_reference"]:
        s.value("challan_reference", (520, 272), "Challan No", v["challan_reference"])
    header = [
        ("Description", 60),
        ("HSN", 330),
        ("Qty", 420),
        ("Unit", 510),
        ("Rate", 590),
        ("Amount", 720),
    ]
    rows = [
        [
            ("description", line.description),
            ("hsn_sac", line.hsn),
            ("quantity", f"{line.qty:,}"),
            ("unit", line.unit),
            ("rate", amount(line.rate_paise)),
            ("amount", amount(line.amount_paise)),
        ]
        for line in case.lines
    ]
    y = s.table(360, header, rows)
    s.value("taxable_total", (500, y), "Taxable value", v["taxable_total"])
    y += 34
    for tax, label in (("igst", "IGST @ 18%"), ("cgst", "CGST @ 9%"), ("sgst", "SGST @ 9%")):
        if tax in v:
            s.value(tax, (500, y), label, v[tax])
            y += 34
    s.value("round_off", (500, y), "Round off", v["round_off"])
    y += 40
    s.value("invoice_total", (500, y), "Total", v["invoice_total"])
    s.value("bank_ifsc", (60, HEIGHT - 160), "Bank IFSC", v["bank_ifsc"])
    s.text((60, HEIGHT - 110), "Synthetic test paper. Not a real invoice.", fonts.text)
    return s


def render_challan(case: Case, fonts: Fonts, overrides: dict[str, str]) -> Sheet:
    s = Sheet(fonts)
    s.title("डिलीवरी चालान", "DELIVERY CHALLAN")
    v = {
        "supplier_name": case.supplier,
        "supplier_gstin": case.supplier_gstin,
        "buyer_name": case.buyer,
        "buyer_gstin": case.buyer_gstin,
        "challan_number": case.challan_number,
        "challan_date": numeric_date(*case.challan_date),
        "po_reference": case.po_number,
        "vehicle_number": "MH12 AB 0000",
    }
    v.update(overrides)
    s.value("supplier_name", (60, 150), "From", v["supplier_name"])
    s.value("supplier_gstin", (60, 182), "GSTIN", v["supplier_gstin"])
    s.value("challan_number", (520, 150), "Challan No", v["challan_number"])
    s.value("challan_date", (520, 182), "Date", v["challan_date"])
    s.value("buyer_name", (60, 240), "To", v["buyer_name"])
    s.value("buyer_gstin", (60, 272), "GSTIN", v["buyer_gstin"])
    s.value("po_reference", (520, 240), "PO No", v["po_reference"])
    s.value("vehicle_number", (520, 272), "Vehicle", v["vehicle_number"])
    qty = overrides.get("_qty")
    rows = [
        [
            ("description", line.description),
            ("quantity", qty if (qty and i == 0) else f"{line.qty:,}"),
            ("unit", line.unit),
        ]
        for i, line in enumerate(case.lines)
    ]
    y = s.table(340, [("Description", 60), ("Qty", 460), ("Unit", 600)], rows)
    s.text((60, y + 40), "Received the goods in good condition.", fonts.text)
    if case.stamp:
        box = (560, y + 90, 820, y + 200)
        s.draw.rounded_rectangle(box, radius=10, outline=(40, 60, 140), width=4)
        s.draw.text((580, y + 110), "RECEIVED", fill=(40, 60, 140), font=fonts.title)
        s.draw.text((580, y + 150), case.buyer[:22], fill=(40, 60, 140), font=fonts.text)
        s.boxes["receiver_stamp_present"] = box
        s.boxes["receiver_signature_present"] = (560, y + 210, 820, y + 250)
        s.draw.line((580, y + 240, 700, y + 222, 760, y + 238), fill=(30, 30, 30), width=2)
    s.values["receiver_stamp_present"] = "yes" if case.stamp else "no"
    s.values["receiver_signature_present"] = "yes" if case.stamp else "no"
    s.text((60, HEIGHT - 110), "Synthetic test paper. Not a real challan.", fonts.text)
    return s


def render_po(case: Case, fonts: Fonts, overrides: dict[str, str]) -> Sheet:
    s = Sheet(fonts)
    s.title("क्रय आदेश", "PURCHASE ORDER")
    v = {
        "buyer_name": case.buyer,
        "buyer_gstin": case.buyer_gstin,
        "po_number": case.po_number,
        "po_date": word_date(*case.po_date),
        "supplier_name": case.supplier,
        "supplier_gstin": case.supplier_gstin,
        "payment_terms_text": f"Payment within {case.credit_days} days of delivery",
        "credit_days": str(case.credit_days),
    }
    v.update(overrides)
    s.value("buyer_name", (60, 150), "Buyer", v["buyer_name"])
    s.value("buyer_gstin", (60, 182), "GSTIN", v["buyer_gstin"])
    s.value("po_number", (520, 150), "PO No", v["po_number"])
    s.value("po_date", (520, 182), "Date", v["po_date"])
    s.value("supplier_name", (60, 240), "Supplier", v["supplier_name"])
    s.value("supplier_gstin", (60, 272), "GSTIN", v["supplier_gstin"])
    rows = [
        [
            ("description", line.description),
            ("quantity", f"{line.qty:,}"),
            ("unit", line.unit),
            ("rate", amount(line.rate_paise)),
        ]
        for line in case.lines
    ]
    y = s.table(340, [("Description", 60), ("Qty", 420), ("Unit", 540), ("Rate", 660)], rows)
    s.value("payment_terms_text", (60, y + 20), "Terms", v["payment_terms_text"])
    s.value("credit_days", (60, y + 56), "Credit days", v["credit_days"])
    s.text((60, HEIGHT - 110), "Synthetic test paper. Not a real order.", fonts.text)
    return s


RENDER = {"invoice": render_invoice, "challan": render_challan, "po": render_po}


# ---------------------------------------------------------------- photo damage
def degrade(
    sheet: Sheet, rng: random.Random, mild: bool
) -> tuple[Image.Image, dict[str, list[int]], list[dict[str, Any]]]:
    """Rotate, light unevenly, stain, shadow and blur; move every box with the rotation."""
    image = sheet.image
    angle = rng.uniform(-1.2, 1.2) if mild else rng.uniform(-6, 6)
    rotated = image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=(205, 200, 190))
    cx, cy = WIDTH / 2, HEIGHT / 2
    rad = math.radians(angle)

    def move(box: tuple[int, int, int, int]) -> list[int]:
        xs, ys = [], []
        for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
            dx, dy = x - cx, y - cy
            xs.append(cx + dx * math.cos(rad) + dy * math.sin(rad))
            ys.append(cy - dx * math.sin(rad) + dy * math.cos(rad))
        left, top = max(0.0, min(xs)), max(0.0, min(ys))
        right, bottom = min(float(WIDTH), max(xs)), min(float(HEIGHT), max(ys))
        return [
            round(top / HEIGHT * 1000),
            round(left / WIDTH * 1000),
            max(round(bottom / HEIGHT * 1000), round(top / HEIGHT * 1000) + 1),
            max(round(right / WIDTH * 1000), round(left / WIDTH * 1000) + 1),
        ]

    # Uneven lighting: a horizontal gradient multiplied in.
    light = Image.linear_gradient("L").rotate(90).resize((WIDTH, HEIGHT))
    strength = 0.08 if mild else rng.uniform(0.15, 0.35)
    shade = light.point(lambda v: int(255 - v * strength))
    out = Image.composite(rotated, Image.new("RGB", rotated.size, (0, 0, 0)), shade)
    out = Image.blend(rotated, out, 0.9)
    if not mild:
        draw = ImageDraw.Draw(out, "RGBA")
        sx, sy, r = (
            rng.randint(100, WIDTH - 100),
            rng.randint(300, HEIGHT - 200),
            rng.randint(40, 80),
        )
        draw.ellipse(
            (sx - r, sy - r, sx + r, sy + r), outline=(140, 100, 60, 90), width=rng.randint(5, 10)
        )
        if rng.random() < 0.5:
            draw.polygon([(0, 0), (WIDTH // 3, 0), (0, HEIGHT // 2)], fill=(0, 0, 0, 40))
        out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.1)))
    boxes = {name: move(box) for name, box in sheet.boxes.items()}
    lines = [
        {name: {"value": cell["value"], "box": move(cell["box"])} for name, cell in row.items()}
        for row in sheet.lines
    ]
    return out, boxes, lines


def jpeg(image: Image.Image, rng: random.Random, mild: bool) -> bytes:
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=82 if mild else rng.randint(62, 78), optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------- recordings
def misread(value: str, rng: random.Random, name: str) -> str | None:
    """A plausible model misread of a printed value, or None when none applies."""
    if name.endswith("_date") and "/" in value:
        d, m, y = value.split("/")
        return f"{m}/{d}/{y}" if d != m and int(d) <= 12 else None
    spots = [i for i, ch in enumerate(value) if ch in CONFUSIONS]
    if spots and rng.random() < 0.7:
        i = rng.choice(spots)
        return value[:i] + CONFUSIONS[value[i]] + value[i + 1 :]
    digits = [i for i, ch in enumerate(value) if ch.isdigit()]
    if len(digits) > 2:
        i = rng.choice(digits[1:])
        return value[:i] + value[i + 1 :]
    if len(value) > 4 and value.isascii():
        i = rng.randint(1, len(value) - 2)
        return value[:i] + value[i + 1 :]
    return None


def answer_json(fields: dict[str, dict[str, Any]], lines: list[dict[str, Any]], kind: str) -> str:
    body: dict[str, Any] = {"kind": kind}
    for name, cell in fields.items():
        body[name] = {"value": cell["value"], "box_2d": cell["box"]}
    body["line_items"] = [
        {n: {"value": c["value"], "box_2d": c["box"]} for n, c in row.items()} for row in lines
    ]
    return json.dumps(body, ensure_ascii=False)


def record(directory: Path, ctx: ReadContext, text: str) -> None:
    write_recording(
        directory,
        ctx,
        text,
        provider="synthetic",
        model="none",
        recorded_from="synthetic",
        recorded_at=RECORDED_AT,
    )


# ---------------------------------------------------------------- the set
@dataclass
class Paper:
    id: str
    kind: str
    case: Case
    overrides: dict[str, str] = field(default_factory=dict)
    injected: list[dict[str, str]] = field(default_factory=list)
    special: str | None = None
    path: str = ""


def build_cases(rng: random.Random) -> list[Case]:
    cases = [demo_case()]
    plan = [("invoice", "challan", "po")] * 7 + [("invoice", "challan")] * 2 + [("invoice",)] * 2
    for index, kinds in enumerate(plan, start=1):
        cases.append(random_case(rng, index, kinds))
    cases[3].ambiguous_invoice_date = True
    cases[8].ambiguous_invoice_date = True
    for case in (cases[3], cases[8]):  # day <= 12 so the printed date reads both ways
        case.invoice_date = (rng.randint(1, 11), case.invoice_date[1])
        case.invoice_date = (case.invoice_date[0], case.invoice_date[0] + 1)
        case.challan_date = (13, case.invoice_date[1] - 1)
        case.po_date = (2, case.invoice_date[1] - 1)
    return cases


def injected_papers(cases: list[Case]) -> list[Paper]:
    base = cases[1]
    g = base.supplier_gstin
    digit_zero = next(i for i in range(2, 11) if g[i] == "0" and i not in range(2, 7))
    lookalike = g[:digit_zero] + "O" + g[digit_zero + 1 :]
    require(lookalike_candidates(lookalike) == [g], "the injected look-alike must have one fix")
    other = g[:-1] + ("M" if g[-1] != "M" else "K")
    require(
        lookalike_candidates(other) == [] and not check_gstin(other).ok, "fixture invariant failed"
    )
    t = taxes(base)
    day, month = base.invoice_date
    return [
        Paper(
            "inj-gstin-lookalike",
            "invoice",
            base,
            {"supplier_gstin": lookalike},
            [{"field": "supplier_gstin", "fault": "lookalike", "truth": g}],
        ),
        Paper(
            "inj-gstin-other",
            "invoice",
            base,
            {"supplier_gstin": other},
            [{"field": "supplier_gstin", "fault": "checksum", "truth": g}],
        ),
        Paper(
            "inj-total",
            "invoice",
            base,
            {"invoice_total": amount(t["total"] + 10_000)},
            [{"field": "invoice_total", "fault": "total", "truth": amount(t["total"])}],
        ),
        Paper(
            "inj-date-swap",
            "invoice",
            base,
            {
                "invoice_date": numeric_date(month, day)
                if day <= 12
                else f"{month:02d}/{day:02d}/2026"
            },
            [
                {
                    "field": "invoice_date",
                    "fault": "day_month_swapped",
                    "truth": numeric_date(day, month),
                }
            ],
        ),
        Paper(
            "inj-qty",
            "challan",
            base,
            {"_qty": f"{base.lines[0].qty + 5:,}"},
            [
                {
                    "field": "quantity",
                    "index": "0",
                    "fault": "quantity_mismatch",
                    "truth": f"{base.lines[0].qty:,}",
                }
            ],
        ),
    ]


def generate(out: Path, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)  # noqa: S311 - seeded synthetic data, not security
    fonts = Fonts()
    cases = build_cases(rng)
    papers: list[Paper] = []
    for case in cases:
        for kind in case.kinds:
            papers.append(Paper(f"{case.id}-{kind}", kind, case))
    papers[4].special = "malformed_then_valid"
    papers[7].special = "malformed_twice"
    papers[10].special = "runaway"
    papers += injected_papers(cases)
    replay_dir = out / "replay"
    reread_version = load("reread.system.md").version
    manifest_papers: list[dict[str, Any]] = []
    for paper in papers:
        mild = paper.case.demo
        kind = cast(PaperKind, paper.kind)
        sheet = RENDER[paper.kind](paper.case, fonts, paper.overrides)
        image, boxes, lines = degrade(sheet, rng, mild)
        data = jpeg(image, rng, mild)
        rel = f"demo/{paper.kind}.jpg" if paper.case.demo else f"papers/{paper.id}.jpg"
        paper.path = rel
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        fields: dict[str, dict[str, Any]] = {
            n: {"value": sheet.values[n], "box": boxes.get(n)}
            for n in sheet.values
            if not n.startswith("_")
        }
        # The recording: the truth, with seeded misreads (never on injected variants).
        read: dict[str, dict[str, Any]] = {n: dict(c) for n, c in fields.items()}
        misreads: list[dict[str, Any]] = []
        if paper.case.demo and paper.kind == "invoice":
            printed = read["buyer_gstin"]["value"]
            wrong = printed[:-1] + ("M" if printed[-1] != "M" else "K")
            require(lookalike_candidates(wrong) == [], "the demo misread must be outside the map")
            require(check_gstin(wrong).errors == ("GSTIN-CHECKSUM",), "fixture invariant failed")
            read["buyer_gstin"]["value"] = wrong
            misreads.append(
                {"field": "buyer_gstin", "index": None, "printed": printed, "read": wrong}
            )
        elif not paper.injected and not paper.case.demo:
            for name, cell in fields.items():
                if (
                    cell["value"]
                    and rng.random() < MISREAD_RATE
                    and name not in ("receiver_stamp_present", "receiver_signature_present")
                ):
                    wrong = misread(cell["value"], rng, name)
                    if wrong and wrong != cell["value"]:
                        read[name]["value"] = wrong
                        misreads.append(
                            {"field": name, "index": None, "printed": cell["value"], "read": wrong}
                        )
        read_lines = [{n: dict(c) for n, c in row.items()} for row in lines]
        if not paper.injected and not paper.case.demo:
            for i, row in enumerate(read_lines):
                for name, cell in row.items():
                    if name in ("quantity", "amount") and rng.random() < MISREAD_RATE:
                        wrong = misread(cell["value"], rng, name)
                        if wrong and wrong != cell["value"]:
                            cell["value"] = wrong
                            misreads.append(
                                {
                                    "field": name,
                                    "index": i,
                                    "printed": lines[i][name]["value"],
                                    "read": wrong,
                                }
                            )
        if paper.special == "runaway":
            read["buyer_name"]["value"] = "Instance " * 40
        prompt_version = extraction_prompt(paper.kind).version
        ctx = ReadContext(original_sha256=sha, kind=kind, prompt_version=prompt_version)
        good = answer_json(read, read_lines, paper.kind)
        if paper.special == "malformed_then_valid":
            record(replay_dir, ctx, 'Here is the invoice data: {"kind": "' + paper.kind)
            record(replay_dir, ReadContext(sha, kind, prompt_version, attempt=2), good)
        elif paper.special == "malformed_twice":
            record(replay_dir, ctx, "I could not read this paper clearly.")
            record(replay_dir, ReadContext(sha, kind, prompt_version, attempt=2), '{"broken": ')
        else:
            record(replay_dir, ctx, good)
        # Re-read recordings: a faithful re-read returns what is printed.
        reread_fields = [m for m in misreads if m["index"] is None]
        reread_fields += [
            {"field": f["field"], "printed": paper.overrides[f["field"]]}
            for f in paper.injected
            if f["field"].endswith("_gstin")
        ]
        for m in reread_fields:
            box = read[m["field"]]["box"]
            if box is None:
                continue
            y1, x1, y2, x2 = (int(v) for v in box)
            rctx = ctx.for_reread(m["field"], (y1, x1, y2, x2), reread_version)
            record(
                replay_dir,
                rctx,
                json.dumps({"value": m["printed"], "box_2d": None}, ensure_ascii=False),
            )
        truth = {
            "id": paper.id,
            "kind": paper.kind,
            "case": paper.case.id,
            "synthetic": True,
            "image": rel,
            "sha256": sha,
            "fields": fields,
            "line_items": lines,
            "simulated_misreads": misreads,
            "special_recording": paper.special,
            "injected": paper.injected,
        }
        truth_path = out / "truth" / f"{paper.id}.json"
        truth_path.parent.mkdir(parents=True, exist_ok=True)
        truth_path.write_text(
            json.dumps(truth, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        manifest_papers.append(
            {
                "id": paper.id,
                "kind": paper.kind,
                "case": paper.case.id,
                "image": rel,
                "injected": bool(paper.injected),
            }
        )
    manifest_cases = []
    for case in cases:
        manifest_cases.append(
            {
                "id": case.id,
                "demo": case.demo,
                "papers": {k: f"{case.id}-{k}" for k in case.kinds},
                "injected": False,
                "credit_days": case.credit_days,
            }
        )
    for paper in papers:
        if paper.injected:
            members = {k: f"{paper.case.id}-{k}" for k in paper.case.kinds}
            members[paper.kind] = paper.id
            manifest_cases.append(
                {
                    "id": f"case-{paper.id}",
                    "demo": False,
                    "papers": members,
                    "injected": True,
                    "credit_days": paper.case.credit_days,
                }
            )
    write_pdf_sample(out / "samples" / "invoice_sample.pdf", cases[1])
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "manifest.json")
    manifest = {
        "synthetic": True,
        "note": "Synthetic papers and recordings made by scripts/gen_fixtures.py. Injected "
        "variants print a fault on the paper, so a faithful re-read returns the faulty value.",
        "seed": seed,
        "papers": manifest_papers,
        "cases": manifest_cases,
        "files": [
            {
                "path": p.relative_to(out).as_posix(),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "size": p.stat().st_size,
            }
            for p in files
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def write_pdf_sample(path: Path, case: Case) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(60, 790, "TAX INVOICE (synthetic sample)")
    pdf.setFont("Helvetica", 11)
    t = taxes(case)
    rows = [
        f"Supplier: {case.supplier}  GSTIN: {case.supplier_gstin}",
        f"Buyer: {case.buyer}  GSTIN: {case.buyer_gstin}",
        f"Invoice No: {case.invoice_number}  Date: {numeric_date(*case.invoice_date)}",
        f"Taxable value: {amount(t['taxable'])}",
        f"Total: {amount(t['total'])}",
    ]
    for i, row in enumerate(rows):
        pdf.drawString(60, 750 - i * 22, row)
    pdf.showPage()
    pdf.save()
    path.write_bytes(buffer.getvalue())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args(argv)
    if (args.out / "manifest.json").exists() and not args.force:
        print(f"gen_fixtures: {args.out} already has a manifest; use --force", file=sys.stderr)
        return 1
    try:
        manifest = generate(args.out, args.seed)
    except (OSError, ValueError) as exc:
        print(f"gen_fixtures: error: {exc}", file=sys.stderr)
        return 2
    images = [f for f in manifest["files"] if f["path"].endswith(".jpg")]
    kinds = {
        k: sum(p["kind"] == k for p in manifest["papers"]) for k in ("invoice", "challan", "po")
    }
    print(
        f"gen_fixtures: {len(manifest['papers'])} papers {kinds}, {len(manifest['cases'])} cases, "
        f"{sum(f['path'].startswith('replay/') for f in manifest['files'])} recordings, "
        f"{sum(f['size'] for f in images) / 1e6:.2f} MB of images"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
