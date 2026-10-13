"""Browser journeys on the replay reader (docs/TESTING.md 5: E2E-1a, E2E-2, E2E-3a, E2E-6)."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import DEMO

pytestmark = pytest.mark.e2e


def create_case(page: Page, server: str) -> None:
    page.goto(server + "/")
    page.get_by_label("Case name").fill("Sample Fabricators v Demo Textiles")
    page.get_by_label("Supplier (you)").fill("Sample Fabricators Pvt Ltd")
    page.get_by_label("Buyer", exact=True).fill("Demo Textiles Ltd")
    page.get_by_role("button", name="New case").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Sample Fabricators v Demo Textiles")


def add_and_read(page: Page, kind: str, label: str) -> None:
    page.locator("#file").set_input_files(str(DEMO / f"{kind}.jpg"))
    page.locator("#kind").select_option(kind)
    page.get_by_role("button", name="Add this paper").click()
    expect(page.locator("#viewer-title")).to_have_text(label)
    page.get_by_role("button", name="Check this paper").click()
    expect(page.locator(".status-line")).to_have_text("Paper checked", timeout=20_000)
    # The finished status line redirects to the refreshed workbench; wait for that page.
    expect(page.locator(".claims-table")).to_be_visible()
    page.wait_for_load_state("networkidle")


def test_demo_journey_red_pen_and_confirm(page: Page, server: str) -> None:
    page.set_viewport_size({"width": 1440, "height": 1000})
    create_case(page, server)
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    add_and_read(page, "invoice", "Tax invoice")
    # E2E-2: the buyer GSTIN row was corrected by the re-read; the original stays, struck.
    row = page.locator("tr.row", has=page.get_by_role("rowheader", name="Buyer GSTIN"))
    expect(row.locator(".struck")).to_contain_text("27AAAPZ5678Z1ZM")
    expect(row.locator(".hand")).to_have_text("27AAAPZ5678Z1Z1")
    expect(row.locator(".check-cell")).to_contain_text("Passed")
    expect(row).to_contain_text("The GSTIN checksum now passes.")
    add_and_read(page, "challan", "Delivery challan")
    add_and_read(page, "po", "Purchase order")
    page.get_by_label("Yes, in writing").check()
    page.get_by_label("Agreed credit days").fill("30")
    page.get_by_label("Work out interest up to").fill("13/10/2026")
    page.get_by_role("button", name="Save terms").click()
    expect(page.locator("[data-owed]")).to_have_text("₹5,40,976.71")
    page.get_by_role("button", name="Confirm these values").click()
    expect(page.locator("svg.stamp")).to_be_visible()
    page.get_by_role("link", name="Open evidence file").click()
    expect(page.locator(".dossier")).to_contain_text("CHECKED")
    assert all(re.match(r"^http://127\.0\.0\.1:\d+/", url) for url in requests), requests


def test_failing_gstin_blocks_confirm_until_accepted(page: Page, server: str) -> None:
    create_case(page, server)
    add_and_read(page, "invoice", "Tax invoice")
    row = page.locator("tr.row", has=page.get_by_role("rowheader", name="Supplier GSTIN"))
    row.get_by_text("Edit").click()
    row.get_by_label("Value as printed on the paper").fill("09AAAPZ1234Z1ZM")
    row.get_by_role("button", name="Save value").click()
    row = page.locator("tr.row", has=page.get_by_role("rowheader", name="Supplier GSTIN"))
    expect(row.locator(".check-cell")).to_contain_text("Doesn't match")
    expect(page.get_by_role("button", name="Confirm these values")).to_be_disabled()
    row.get_by_text("Accept anyway").click()
    row.get_by_label(re.compile("Why are you accepting this")).fill("Checked the paper by hand")
    row.get_by_role("button", name="Accept with this reason").click()
    row = page.locator("tr.row", has=page.get_by_role("rowheader", name="Supplier GSTIN"))
    expect(row).to_contain_text("Accepted by you: Checked the paper by hand")


def test_reduced_motion_shows_the_correction_without_animation(page: Page, server: str) -> None:
    page.emulate_media(reduced_motion="reduce")
    create_case(page, server)
    add_and_read(page, "invoice", "Tax invoice")
    hand = page.locator("tr.row", has=page.get_by_role("rowheader", name="Buyer GSTIN")).locator(
        ".hand"
    )
    expect(hand).to_have_text("27AAAPZ5678Z1Z1")
    assert hand.evaluate("el => getComputedStyle(el).animationName") == "none"
