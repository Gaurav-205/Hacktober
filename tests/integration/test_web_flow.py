"""The demo journey through the web app on the replay reader (docs/DEMO_SCRIPT.md, E2E-1a/E2E-2).

Runs in-process with Starlette's test client and a temporary data folder. The papers are the
committed synthetic demo fixtures, so the replay recordings match their bytes.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from munim_web.main import create_app
from munim_web.settings import Settings

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "eval" / "fixtures" / "demo"
BASE = "http://127.0.0.1:8765"


class Web:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.app = client.app.app  # type: ignore[attr-defined]

    @property
    def token(self) -> str:
        if not self.client.cookies.get("munim_csrf_8765"):
            self.client.get("/")
        return str(self.client.cookies.get("munim_csrf_8765"))

    def post(self, url: str, data: dict[str, str] | None = None, **kw: object):  # type: ignore[no-untyped-def]
        return self.client.post(
            url, data={**(data or {}), "csrf_token": self.token}, follow_redirects=False, **kw
        )

    def new_case(self) -> str:
        r = self.post(
            "/cases",
            {
                "title": "Sample Fabricators v Demo Textiles",
                "supplier_name": "Sample Fabricators Pvt Ltd",
                "buyer_name": "Demo Textiles Ltd",
            },
        )
        assert r.status_code == 303
        return str(r.headers["location"]).rsplit("/", 1)[1]

    def upload(self, case_id: str, kind: str) -> str:
        data = (DEMO / f"{kind}.jpg").read_bytes()
        r = self.post(
            f"/cases/{case_id}/papers",
            {"kind": kind},
            files={"file": (f"{kind}.jpg", data, "image/jpeg")},
        )
        assert r.status_code == 303, r.text
        location = str(r.headers["location"])
        assert "error=" not in location, location
        return location.split("paper=")[1]

    def read(self, paper_id: str) -> None:
        r = self.post(f"/papers/{paper_id}/read")
        assert r.status_code == 303
        # The app runs on the test client's own event loop; wait for its background reads there.
        self.client.portal.call(self.app.state.papers.wait_idle)  # type: ignore[union-attr]


@pytest.fixture
def web(tmp_path: Path) -> Iterator[Web]:
    app = create_app(
        Settings(data_dir=tmp_path, provider="replay", replay_dir=ROOT / "eval/fixtures/replay")
    )
    app.app.state.today = date(2026, 10, 13)
    with TestClient(app, base_url=BASE) as client:
        yield Web(client)


def demo_case(web: Web) -> tuple[str, dict[str, str]]:
    case_id = web.new_case()
    papers = {kind: web.upload(case_id, kind) for kind in ("invoice", "challan", "po")}
    for paper_id in papers.values():
        web.read(paper_id)
    return case_id, papers


def test_demo_invoice_buyer_gstin_is_corrected_by_the_red_pen(web: Web) -> None:
    case_id, papers = demo_case(web)
    db = web.app.state.db
    claim = db.one(
        "SELECT * FROM claims WHERE paper_id = ? AND field = 'buyer_gstin'", (papers["invoice"],)
    )
    assert claim["value_read"].endswith("M")  # the recorded misread
    assert claim["value_current"] == claim["value_read"][:-1] + "1"
    assert (claim["source"], claim["repair_via"], claim["repair_outcome"]) == (
        "repair",
        "model",
        "corrected",
    )
    page = web.client.get(f"/cases/{case_id}?paper={papers['invoice']}").text
    row = page.split(f'id="row-{claim["id"]}"')[1].split("</tr>")[0]
    tag = re.search(rf'<tr id="row-{claim["id"]}"[^>]*>', page)
    assert tag is not None and "redpen-animate" in tag.group(0)
    assert claim["value_read"] in row  # the original stays visible, struck
    assert "struck" in row and 'class="hand"' in row
    assert "Re-read from the marked box. The GSTIN checksum now passes." in row
    again = web.client.get(f"/cases/{case_id}?paper={papers['invoice']}").text
    assert "redpen-animate" not in again  # the sequence plays once


def test_demo_journey_confirms_and_shows_the_amount_owed(web: Web) -> None:
    case_id, _ = demo_case(web)
    page = web.client.get(f"/cases/{case_id}").text
    assert "To work out the interest, add" in page
    r = web.post(
        f"/cases/{case_id}/settings",
        {"agreement": "written", "credit_days": "30", "as_on_date": "13/10/2026"},
    )
    assert r.status_code == 303
    page = web.client.get(f"/cases/{case_id}").text
    assert "₹40,976.71" in page and "₹5,40,976.71" in page
    assert "Provisional until you confirm the values." in page
    assert "19 Apr 2026" in page and ">177<" in page
    open_checks = re.search(r"(\d+) checks still need you", page)
    assert open_checks is None, open_checks
    r = web.post(f"/cases/{case_id}/confirm")
    assert r.status_code == 303
    page = web.client.get(r.headers["location"]).text
    assert "stamp-land" in page and "CHECKED" in page
    assert "Provisional" not in page
    dossier = web.client.get(f"/cases/{case_id}/dossier").text
    assert "₹5,40,976.71" in dossier and "CHECKED" in dossier
    notice = web.client.get(f"/cases/{case_id}/notice?lang=en").text
    assert "Payment therefore fell due on 19 Apr 2026." in notice
    assert "making ₹5,40,976.71 due" in notice


def test_workbench_hero_names_the_worst_row_state(web: Web) -> None:
    case_id, _ = demo_case(web)
    page = web.client.get(f"/cases/{case_id}").text
    hero = re.search(r'class="verdict-hero verdict-hero-(\w+)"', page)
    assert hero is not None, "the workbench has no verdict hero"
    statuses = set(re.findall(r'class="row row-(\w+)', page))
    worst = next((s for s in ("failed", "review", "passed") if s in statuses), "none")
    assert hero.group(1) == worst


def test_editing_a_value_undoes_the_confirmation(web: Web) -> None:
    case_id, papers = demo_case(web)
    web.post(
        f"/cases/{case_id}/settings",
        {"agreement": "written", "credit_days": "30", "as_on_date": "13/10/2026"},
    )
    assert web.post(f"/cases/{case_id}/confirm").status_code == 303
    db = web.app.state.db
    claim = db.one(
        "SELECT * FROM claims WHERE paper_id = ? AND field = 'invoice_number'", (papers["invoice"],)
    )
    r = web.post(
        f"/claims/{claim['id']}", {"value": "SF/2025-26/0413", "version": str(claim["version"])}
    )
    assert r.status_code == 303
    assert db.case(case_id)["confirmed_at"] is None
    edited = db.one("SELECT * FROM claims WHERE id = ?", (claim["id"],))
    assert (edited["value_read"], edited["value_current"], edited["source"]) == (
        "SF/2025-26/0412",
        "SF/2025-26/0413",
        "user",
    )
