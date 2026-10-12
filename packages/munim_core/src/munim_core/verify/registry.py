"""run_all: every rule family over a case, in a stable order."""

from __future__ import annotations

from datetime import date

from munim_core.verify import cross, dates, identifiers, invoice, values
from munim_core.verify.models import CaseState, Finding


def run_all(state: CaseState, today: date) -> list[Finding]:
    """Run every rule on the case as it stands. Pure: the same state gives the same findings."""
    return [
        *values.check(state),
        *identifiers.check(state),
        *invoice.check(state, today),
        *dates.check(state),
        *cross.check(state),
    ]
