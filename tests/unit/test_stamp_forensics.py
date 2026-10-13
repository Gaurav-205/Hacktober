"""Tests for delivery challan stamp forensics (pure core)."""

from munim_core.stamp_forensics import analyze_challan_stamp


def test_buyer_stamp_match() -> None:
    res = analyze_challan_stamp(
        stamp_text="For Mega Infra Projects Private Limited - Store Incharge",
        buyer_name="Mega Infra Projects Pvt Ltd",
        supplier_name="Sharma Tools",
    )
    assert res.is_stamped is True
    assert res.is_buyer_match is True
    assert res.is_supplier_self_stamp is False
    assert res.forensic_status == "verified_buyer"


def test_supplier_self_stamp_detected() -> None:
    # Supplier accidentally stamped their own challan instead of getting buyer's stamp
    res = analyze_challan_stamp(
        stamp_text="Sharma Tools - Dispatch Department",
        buyer_name="Mega Infra Projects Pvt Ltd",
        supplier_name="Sharma Tools",
    )
    assert res.is_stamped is True
    assert res.is_buyer_match is False
    assert res.is_supplier_self_stamp is True
    assert res.forensic_status == "possible_self_stamp"


def test_third_party_or_unmatched_stamp() -> None:
    res = analyze_challan_stamp(
        stamp_text="Gati Express Cargo Logistics",
        buyer_name="Mega Infra Projects Pvt Ltd",
        supplier_name="Sharma Tools",
    )
    assert res.is_stamped is True
    assert res.is_buyer_match is False
    assert res.is_supplier_self_stamp is False
    assert res.forensic_status == "third_party_or_unmatched"


def test_no_stamp_text() -> None:
    res = analyze_challan_stamp(
        stamp_text=None,
        buyer_name="Mega Infra Projects Pvt Ltd",
        supplier_name="Sharma Tools",
    )
    assert res.is_stamped is False
    assert res.forensic_status == "no_stamp"
