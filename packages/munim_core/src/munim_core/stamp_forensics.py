"""Challan stamp forensic verification (pure core).

Analyzes the stamp impression text on delivery challans to verify:
1. Genuine buyer acknowledgement (store stamp / receiving officer).
2. Self-stamp detection (when suppliers mistakenly stamp their own dispatch copy).
3. Transporter / logistics intermediary stamps vs end-buyer acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz

from munim_core.verify.cross import NAME_THRESHOLD, normalise_name

__all__ = [
    "ForensicStatus",
    "StampForensicsResult",
    "analyze_challan_stamp",
]

ForensicStatus = Literal[
    "verified_buyer",
    "possible_self_stamp",
    "third_party_or_unmatched",
    "no_stamp",
]


@dataclass(frozen=True, slots=True)
class StampForensicsResult:
    """Forensic assessment of delivery challan acknowledgement stamp."""

    is_stamped: bool
    is_buyer_match: bool
    is_supplier_self_stamp: bool
    forensic_status: ForensicStatus
    buyer_similarity: int
    supplier_similarity: int
    notes: str


def analyze_challan_stamp(
    stamp_text: str | None,
    buyer_name: str | None,
    supplier_name: str | None,
) -> StampForensicsResult:
    """Analyze stamp text against buyer and supplier entities."""
    if not stamp_text or not stamp_text.strip():
        return StampForensicsResult(
            is_stamped=False,
            is_buyer_match=False,
            is_supplier_self_stamp=False,
            forensic_status="no_stamp",
            buyer_similarity=0,
            supplier_similarity=0,
            notes="No stamp impression text detected on challan",
        )

    norm_stamp = normalise_name(stamp_text)
    norm_buyer = normalise_name(buyer_name or "")
    norm_supplier = normalise_name(supplier_name or "")

    buyer_score = round(fuzz.token_set_ratio(norm_stamp, norm_buyer)) if norm_buyer else 0
    supplier_score = round(fuzz.token_set_ratio(norm_stamp, norm_supplier)) if norm_supplier else 0

    is_buyer = buyer_score >= NAME_THRESHOLD
    is_supplier = supplier_score >= NAME_THRESHOLD and supplier_score > buyer_score

    if is_buyer:
        status: ForensicStatus = "verified_buyer"
        notes = f"Stamp text matches buyer name ({buyer_score}% match)"
    elif is_supplier:
        status = "possible_self_stamp"
        notes = "Warning: Stamp appears to belong to supplier rather than buyer receiving entity"
    else:
        status = "third_party_or_unmatched"
        notes = "Stamp impression present but does not match buyer name"

    return StampForensicsResult(
        is_stamped=True,
        is_buyer_match=is_buyer,
        is_supplier_self_stamp=is_supplier,
        forensic_status=status,
        buyer_similarity=buyer_score,
        supplier_similarity=supplier_score,
        notes=notes,
    )
