"""Unit tests for the workbench view model, munim_web.services.views."""

from __future__ import annotations

import pytest

from munim_web.services.views import Row, counts

pytestmark = pytest.mark.unit


def row(status: str) -> Row:
    return Row(
        id="c1",
        field="buyer_gstin",
        index=None,
        label="Buyer GSTIN",
        value=None,
        value_read=None,
        source="model",
        status=status,
        messages=[],
        accept_rule=None,
        accepted=[],
        repair_reason=None,
        repair_outcome=None,
        repair_via=None,
        animate=False,
        version=1,
        box=None,
        blocking=False,
        rereadable=False,
    )


def test_counts_splits_passed_from_open() -> None:
    c = counts([row("passed"), row("passed"), row("failed"), row("review")])
    assert (c["passed"], c["open"], c["failed"], c["review"], c["total"]) == (2, 2, 1, 1, 4)


@pytest.mark.parametrize(
    ("statuses", "overall"),
    [
        (["passed", "passed"], "passed"),
        (["passed", "review"], "review"),
        (["review", "failed"], "failed"),
        (["passed", "failed", "review"], "failed"),
        (["skipped", "accepted"], "none"),
        ([], "none"),
    ],
)
def test_overall_is_the_worst_state(statuses: list[str], overall: str) -> None:
    assert counts([row(s) for s in statuses])["overall"] == overall
