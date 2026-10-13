"""Tests for cross-paper line item discrepancy heatmap (pure core)."""

from munim_core.discrepancy import (
    build_discrepancy_map,
)


def test_perfect_line_match() -> None:
    inv_lines = [
        {
            "description": "Mild Steel Hex Bolt M10",
            "quantity": "100",
            "unit": "nos",
            "rate": "5.50",
            "amount": "550.00",
        },
        {
            "description": "Stainless Steel Washer",
            "quantity": "200",
            "unit": "pcs",
            "rate": "1.20",
            "amount": "240.00",
        },
    ]
    ch_lines = [
        {"description": "Mild Steel Hex Bolt M10", "quantity": "100", "unit": "nos"},
        {"description": "Stainless Steel Washer", "quantity": "200", "unit": "pcs"},
    ]

    heatmap = build_discrepancy_map(inv_lines, ch_lines)
    assert heatmap.total_items == 2
    assert heatmap.matched_items == 2
    assert heatmap.discrepant_items == 0
    assert heatmap.missing_items == 0
    assert heatmap.overall_match_ratio == 1.0
    assert heatmap.items[0].status == "match"
    assert heatmap.items[1].status == "match"


def test_quantity_mismatch() -> None:
    inv_lines = [
        {"description": "Cast Iron Valve 25mm", "quantity": "50", "unit": "nos"},
    ]
    ch_lines = [
        # Only 40 delivered according to challan
        {"description": "Cast Iron Valve 25mm", "quantity": "40", "unit": "nos"},
    ]

    heatmap = build_discrepancy_map(inv_lines, ch_lines)
    assert heatmap.total_items == 1
    assert heatmap.matched_items == 0
    assert heatmap.discrepant_items == 1
    assert heatmap.items[0].status == "qty_mismatch"
    assert "Delivered 40 vs Billed 50" in heatmap.items[0].notes


def test_unmatched_missing_item() -> None:
    inv_lines = [
        {"description": "Hydraulic Hose 1/2 inch", "quantity": "5", "unit": "m"},
    ]
    ch_lines = [
        {"description": "Copper Tubing 10mm", "quantity": "20", "unit": "m"},
    ]

    heatmap = build_discrepancy_map(inv_lines, ch_lines)
    assert heatmap.total_items == 1
    assert heatmap.missing_items == 1
    assert heatmap.items[0].status == "unmatched"
    assert heatmap.items[0].challan_index is None
