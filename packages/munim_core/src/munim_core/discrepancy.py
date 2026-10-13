"""Cross-paper line item discrepancy heatmap (pure core).

Computes line-by-line matching and discrepancy analysis between Invoice and Delivery Challan
to pinpoint short deliveries, unbilled deliveries, or unit mismatches.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

from munim_core.verify.common import quantity
from munim_core.verify.cross import (
    LINE_THRESHOLD,
    _comparable,
    _unit,
    normalise_description,
)

__all__ = [
    "DiscrepancyHeatmap",
    "LineDiscrepancy",
    "build_discrepancy_map",
]


@dataclass(frozen=True, slots=True)
class LineDiscrepancy:
    """Discrepancy analysis for a single line item."""

    line_id: str
    invoice_index: int
    invoice_description: str
    invoice_quantity: str
    invoice_rate: str | None
    invoice_amount: str | None
    challan_index: int | None
    challan_description: str | None
    challan_quantity: str | None
    status: str  # "match" | "qty_mismatch" | "unmatched" | "unit_mismatch"
    match_score: int
    notes: str


@dataclass(frozen=True, slots=True)
class DiscrepancyHeatmap:
    """Aggregated discrepancy heatmap across all line items."""

    items: tuple[LineDiscrepancy, ...]
    total_items: int
    matched_items: int
    discrepant_items: int
    missing_items: int
    overall_match_ratio: float


def build_discrepancy_map(
    invoice_lines: list[Mapping[str, Any]],
    challan_lines: list[Mapping[str, Any]],
) -> DiscrepancyHeatmap:
    """Match line items between invoice and challan and calculate discrepancy metrics."""
    items: list[LineDiscrepancy] = []
    matched_count = 0
    discrepant_count = 0
    missing_count = 0

    norm_ch = [
        (j, ch, normalise_description(str(ch.get("description", ""))))
        for j, ch in enumerate(challan_lines)
        if ch.get("description")
    ]

    for i, inv in enumerate(invoice_lines):
        inv_desc = str(inv.get("description", ""))
        inv_qty_str = str(inv.get("quantity", ""))
        inv_qty = quantity(inv_qty_str)
        inv_rate = str(inv.get("rate")) if inv.get("rate") is not None else None
        inv_amt = str(inv.get("amount")) if inv.get("amount") is not None else None

        if not inv_desc:
            continue

        norm_inv = normalise_description(inv_desc)

        # Find best matching challan line
        best_match = None
        best_score = 0
        for j, ch, norm_c in norm_ch:
            score = round(fuzz.token_set_ratio(norm_inv, norm_c))
            if score > best_score:
                best_score = score
                best_match = (j, ch)

        line_id = f"line-{i + 1}"

        if best_match is None or best_score < LINE_THRESHOLD:
            missing_count += 1
            items.append(
                LineDiscrepancy(
                    line_id=line_id,
                    invoice_index=i,
                    invoice_description=inv_desc,
                    invoice_quantity=inv_qty_str,
                    invoice_rate=inv_rate,
                    invoice_amount=inv_amt,
                    challan_index=None,
                    challan_description=None,
                    challan_quantity=None,
                    status="unmatched",
                    match_score=best_score,
                    notes=f"Item '{inv_desc}' not found on delivery challan",
                )
            )
            continue

        j, ch = best_match
        ch_desc = str(ch.get("description", ""))
        ch_qty_str = str(ch.get("quantity", ""))
        ch_qty = quantity(ch_qty_str)

        if inv_qty is None or ch_qty is None:
            discrepant_count += 1
            items.append(
                LineDiscrepancy(
                    line_id=line_id,
                    invoice_index=i,
                    invoice_description=inv_desc,
                    invoice_quantity=inv_qty_str,
                    invoice_rate=inv_rate,
                    invoice_amount=inv_amt,
                    challan_index=j,
                    challan_description=ch_desc,
                    challan_quantity=ch_qty_str,
                    status="qty_mismatch",
                    match_score=best_score,
                    notes="Unparseable quantity on invoice or challan",
                )
            )
            continue

        converted_ch_qty, convertible = _comparable(
            ch_qty, _unit(ch.get("unit")), _unit(inv.get("unit"))
        )

        if not convertible:
            discrepant_count += 1
            items.append(
                LineDiscrepancy(
                    line_id=line_id,
                    invoice_index=i,
                    invoice_description=inv_desc,
                    invoice_quantity=inv_qty_str,
                    invoice_rate=inv_rate,
                    invoice_amount=inv_amt,
                    challan_index=j,
                    challan_description=ch_desc,
                    challan_quantity=ch_qty_str,
                    status="unit_mismatch",
                    match_score=best_score,
                    notes=f"Incompatible units: {inv.get('unit')} vs {ch.get('unit')}",
                )
            )
        elif converted_ch_qty == inv_qty:
            matched_count += 1
            items.append(
                LineDiscrepancy(
                    line_id=line_id,
                    invoice_index=i,
                    invoice_description=inv_desc,
                    invoice_quantity=inv_qty_str,
                    invoice_rate=inv_rate,
                    invoice_amount=inv_amt,
                    challan_index=j,
                    challan_description=ch_desc,
                    challan_quantity=ch_qty_str,
                    status="match",
                    match_score=best_score,
                    notes="Exact quantity delivered and billed",
                )
            )
        else:
            discrepant_count += 1
            items.append(
                LineDiscrepancy(
                    line_id=line_id,
                    invoice_index=i,
                    invoice_description=inv_desc,
                    invoice_quantity=inv_qty_str,
                    invoice_rate=inv_rate,
                    invoice_amount=inv_amt,
                    challan_index=j,
                    challan_description=ch_desc,
                    challan_quantity=ch_qty_str,
                    status="qty_mismatch",
                    match_score=best_score,
                    notes=f"Delivered {ch_qty_str} vs Billed {inv_qty_str}",
                )
            )

    total = len(items)
    ratio = (matched_count / total) if total > 0 else 0.0

    return DiscrepancyHeatmap(
        items=tuple(items),
        total_items=total,
        matched_items=matched_count,
        discrepant_items=discrepant_count,
        missing_items=missing_count,
        overall_match_ratio=ratio,
    )
