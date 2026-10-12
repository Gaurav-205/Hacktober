"""The rule catalogue: every rule id, its version and its default severity.

docs/DOMAIN_RULES.md is the human-readable specification and rules/rules.yaml carries the
sources and statuses shown on the Rules page. A test keeps the three in step (rule_sync).
"""

from __future__ import annotations

from dataclasses import dataclass

from munim_core.verify.models import Severity

__all__ = ["RULES", "RuleSpec", "rule"]


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    version: str
    family: str  # identifiers | invoice | dates | cross | clock | notice | security
    severity: Severity  # the usual severity; some rules raise it for particular fields
    runs_in_verify: bool = True


_SPECS = (
    RuleSpec("GSTIN-FORMAT", "1.0", "identifiers", Severity.BLOCKING),
    RuleSpec("GSTIN-STATE", "1.0", "identifiers", Severity.BLOCKING),
    RuleSpec("GSTIN-CHECKSUM", "1.0", "identifiers", Severity.BLOCKING),
    RuleSpec("GSTIN-LOOKALIKE", "1.0", "identifiers", Severity.BLOCKING),
    RuleSpec("GSTIN-PAN", "1.0", "identifiers", Severity.BLOCKING),
    RuleSpec("PAN-FORMAT", "1.0", "identifiers", Severity.WARNING),
    RuleSpec("AADHAAR-MASK", "1.0", "security", Severity.WARNING, runs_in_verify=False),
    RuleSpec("UDYAM-FORMAT", "1.0", "identifiers", Severity.WARNING),
    RuleSpec("IFSC-KNOWN", "1.0", "identifiers", Severity.WARNING, runs_in_verify=False),
    RuleSpec("VALUE-FORMAT", "1.0", "invoice", Severity.BLOCKING),
    RuleSpec("INV-LINE-AMOUNT", "1.0", "invoice", Severity.BLOCKING),
    RuleSpec("INV-TAXABLE-SUM", "1.0", "invoice", Severity.BLOCKING),
    RuleSpec("INV-TAX-SPLIT", "1.0", "invoice", Severity.BLOCKING),
    RuleSpec("INV-TAX-RATE", "1.0", "invoice", Severity.WARNING),
    RuleSpec("INV-TOTAL", "1.0", "invoice", Severity.BLOCKING),
    RuleSpec("INV-NUMBER-FORMAT", "1.0", "invoice", Severity.WARNING),
    RuleSpec("INV-DATE-SANE", "1.0", "invoice", Severity.BLOCKING),
    RuleSpec("DATE-AMBIGUOUS", "1.0", "dates", Severity.WARNING),
    RuleSpec("X-SUPPLIER-GSTIN", "1.0", "cross", Severity.BLOCKING),
    RuleSpec("X-BUYER-GSTIN", "1.0", "cross", Severity.BLOCKING),
    RuleSpec("X-NAME-SIMILAR", "1.0", "cross", Severity.WARNING),
    RuleSpec("X-INVOICE-REF", "1.0", "cross", Severity.BLOCKING),
    RuleSpec("X-PO-REF", "1.0", "cross", Severity.WARNING),
    RuleSpec("X-QTY", "1.0", "cross", Severity.BLOCKING),
    RuleSpec("X-DATE-ORDER", "1.0", "cross", Severity.WARNING),
    RuleSpec("X-RECEIVER-ACK", "1.0", "cross", Severity.WARNING),
    RuleSpec("CLOCK-ACCEPT", "1.0", "clock", Severity.BLOCKING, runs_in_verify=False),
    RuleSpec("CLOCK-DUE", "1.0", "clock", Severity.BLOCKING, runs_in_verify=False),
    RuleSpec("CLOCK-INTEREST", "1.0", "clock", Severity.BLOCKING, runs_in_verify=False),
    RuleSpec("SEC-18-REFERENCE", "1.0", "notice", Severity.WARNING, runs_in_verify=False),
)

RULES: dict[str, RuleSpec] = {spec.rule_id: spec for spec in _SPECS}


def rule(rule_id: str) -> RuleSpec:
    """Return the catalogue entry for a rule id (KeyError for an unknown id)."""
    return RULES[rule_id]
