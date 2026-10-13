"""Printed evidence file (E2E-10, Chromium only) and axe checks (docs/TESTING.md 5 and 6)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page, expect
from pypdf import PdfReader

from tests.e2e.test_journeys import add_and_read, create_case

ROOT = Path(__file__).resolve().parents[2]


def confirmed_case(page: Page, server: str) -> str:
    create_case(page, server)
    for kind, label in (
        ("invoice", "Tax invoice"),
        ("challan", "Delivery challan"),
        ("po", "Purchase order"),
    ):
        add_and_read(page, kind, label)
    page.get_by_label("Yes, in writing").check()
    page.get_by_label("Agreed credit days").fill("30")
    page.get_by_label("Work out interest up to").fill("13/10/2026")
    page.get_by_role("button", name="Save terms").click()
    page.get_by_role("button", name="Confirm these values").click()
    expect(page.locator("svg.stamp")).to_be_visible()
    return page.url.split("/cases/")[1].split("?")[0]


@pytest.mark.e2e
def test_printed_evidence_file_is_a4_with_the_stamp_and_amount(
    page: Page, server: str, browser_name: str
) -> None:
    if browser_name != "chromium":
        pytest.skip("Playwright prints PDFs only in Chromium; see docs/TESTING.md E2E-10")
    case_id = confirmed_case(page, server)
    page.goto(f"{server}/cases/{case_id}/dossier")
    page.emulate_media(media="print")
    reader = PdfReader(io.BytesIO(page.pdf(format="A4", prefer_css_page_size=True)))
    assert len(reader.pages) >= 4
    width, height = (float(v) for v in reader.pages[0].mediabox.upper_right)
    assert (round(width), round(height)) == (595, 842)  # A4 in points
    text = "\n".join(p.extract_text() for p in reader.pages)
    assert "Sample Fabricators v Demo Textiles" in text
    assert "CHECKED" in text
    assert "5,40,976.71" in text


@pytest.mark.a11y
@pytest.mark.parametrize("lang", ["en", "hi"])
def test_pages_have_no_serious_accessibility_violations(page: Page, server: str, lang: str) -> None:
    case_id = confirmed_case(page, server)
    page.context.add_cookies([{"name": "munim_lang", "value": lang, "url": server}])
    axe = Axe()
    for path in (
        "/",
        f"/cases/{case_id}",
        f"/cases/{case_id}/dossier",
        f"/cases/{case_id}/working",
        "/rules",
        "/settings",
        "/evaluation",
        "/about",
    ):
        page.goto(server + path)
        results = axe.run(page)
        serious = [
            v for v in results.response["violations"] if v["impact"] in ("serious", "critical")
        ]
        assert serious == [], (
            path,
            [(v["id"], [n["target"] for n in v["nodes"]][:3]) for v in serious],
        )
