"""Tests for MSME Samadhaan packet generation (pure core)."""

from datetime import date

from munim_core.samadhaan import (
    SamadhaanInput,
    build_samadhaan_packet,
)


def test_build_samadhaan_packet_basic() -> None:
    inp = SamadhaanInput(
        supplier_name="Sharma Engineering Works",
        supplier_udyam="UDYAM-MH-12-0012345",
        supplier_gstin="27AAACS1234A1Z5",
        supplier_state="Maharashtra",
        buyer_name="Mega Infra Private Limited",
        buyer_gstin="27AABCM5678B1Z2",
        buyer_type="Private Limited Company",
        po_number="PO-2024-001",
        po_date=date(2024, 1, 10),
        invoice_number="INV/2024/042",
        invoice_date=date(2024, 1, 15),
        invoice_amount_paise=150_000_00,  # ₹1,50,000.00
        delivery_date=date(2024, 1, 18),
        due_date=date(2024, 2, 2),
        as_on_date=date(2024, 4, 15),
        principal_claimed_paise=150_000_00,
        interest_claimed_paise=6_432_50,  # ₹6,432.50
    )

    packet = build_samadhaan_packet(inp)

    assert packet.supplier_udyam == "UDYAM-MH-12-0012345"
    assert packet.buyer_name == "Mega Infra Private Limited"
    assert packet.total_claimed_paise == 156_432_50
    assert packet.invoice_number == "INV/2024/042"
    assert "MSMED Act, 2006" in packet.statement_of_claim
    assert "₹1,50,000" in packet.statement_of_claim or "150000" in packet.statement_of_claim

    # Verify fields exist and are within length limits
    for field in packet.fields:
        if field.max_length is not None:
            assert len(field.value) <= field.max_length


def test_statement_of_claim_truncation_safety() -> None:
    # Extremely long buyer name and details
    long_desc = "A" * 2000
    inp = SamadhaanInput(
        supplier_name="Sharma Tools",
        supplier_udyam="UDYAM-MH-12-0012345",
        supplier_gstin="27AAACS1234A1Z5",
        supplier_state="Maharashtra",
        buyer_name=long_desc,
        buyer_gstin="27AABCM5678B1Z2",
        buyer_type="Proprietorship",
        po_number="PO-1",
        po_date=None,
        invoice_number="INV-1",
        invoice_date=date(2024, 1, 1),
        invoice_amount_paise=10_000_00,
        delivery_date=date(2024, 1, 2),
        due_date=date(2024, 1, 17),
        as_on_date=date(2024, 3, 1),
        principal_claimed_paise=10_000_00,
        interest_claimed_paise=500_00,
    )

    packet = build_samadhaan_packet(inp)
    assert len(packet.statement_of_claim) <= 1000
