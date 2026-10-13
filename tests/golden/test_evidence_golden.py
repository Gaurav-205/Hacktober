"""Golden files for the demo case's notices and evidence-file content (TASKS T4.6).

The demo papers are read on the replay reader, the terms from docs/DEMO_SCRIPT.md are entered
and the values confirmed; the English and Hindi notices and a summary of the evidence file are
compared with tests/golden/. Re-bless with `make bless` only after reading the diff.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from munim_web.main import create_app
from munim_web.services.case_service import load_case
from munim_web.settings import Settings
from tests.integration.test_web_flow import BASE, ROOT, Web, demo_case

pytestmark = pytest.mark.golden

HERE = Path(__file__).parent
TODAY = date(2026, 10, 13)


@pytest.fixture(scope="module")
def confirmed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Web, str]]:
    app = create_app(
        Settings(
            data_dir=tmp_path_factory.mktemp("golden"),
            provider="replay",
            replay_dir=ROOT / "eval/fixtures/replay",
        )
    )
    app.app.state.today = TODAY
    with TestClient(app, base_url=BASE) as client:
        web = Web(client)
        case_id, _ = demo_case(web)
        web.post(
            f"/cases/{case_id}/settings",
            {"agreement": "written", "credit_days": "30", "as_on_date": "13/10/2026"},
        )
        assert web.post(f"/cases/{case_id}/confirm").status_code == 303
        yield web, case_id


def check(name: str, actual: str) -> None:
    path = HERE / name
    if os.environ.get("MUNIM_BLESS") == "1":
        path.write_text(actual, encoding="utf-8")
    assert path.is_file(), f"{name} is missing; run make bless after reviewing the output"
    assert actual == path.read_text(encoding="utf-8")


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_notice_matches_the_golden_text(confirmed: tuple[Web, str], lang: str) -> None:
    web, case_id = confirmed
    r = web.client.get(f"/cases/{case_id}/notice?lang={lang}")
    assert r.status_code == 200
    check(f"notice.{lang}.txt", r.text)


def test_evidence_file_content_matches_the_golden_summary(confirmed: tuple[Web, str]) -> None:
    web, case_id = confirmed
    snap = load_case(web.app.state.db, case_id, TODAY)
    assert snap is not None
    model = snap.dossier()
    result = model.clock.result if model.clock else None
    assert result is not None
    summary = {
        "confirmed": model.confirmed,
        "stamp_visible": model.stamp_visible,
        "unresolved": [f.rule_id for f in model.unresolved],
        "assumptions": list(model.assumptions),
        "clock": {
            "due_date": result.due_date.isoformat(),
            "days_late": result.days_late,
            "interest_paise": result.interest_paise,
            "total_paise": result.total_paise,
            "rates_unconfirmed": model.clock.rates_unconfirmed if model.clock else None,
        },
        "rows": sorted(
            f"{r.ref.paper_kind}.{r.ref.field}{'' if r.ref.index is None else f'[{r.ref.index}]'}"
            f" = {r.value!r} ({r.source}, {r.status.value if r.status else 'no check'})"
            for r in model.rows
            if r.value is not None
        ),
    }
    check("evidence_summary.json", json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
