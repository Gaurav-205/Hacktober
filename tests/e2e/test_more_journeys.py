"""Keyboard, mobile, deletion and reader failure (docs/TESTING.md 5: E2E-5, E2E-7, E2E-8, E2E-9)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import DEMO
from tests.e2e.test_journeys import add_and_read, create_case

pytestmark = pytest.mark.e2e


def test_keyboard_only_edit_and_cancel(page: Page, server: str) -> None:
    create_case(page, server)
    add_and_read(page, "invoice", "Tax invoice")
    page.goto(page.url)  # a settled workbench: this test is about the table, not the read
    first = page.locator("tr.row").first
    first.focus()
    page.keyboard.press("ArrowDown")
    second = page.locator("tr.row").nth(1)
    expect(second).to_be_focused()
    page.keyboard.press("Enter")
    value = second.locator("input[name=value]")
    expect(value).to_be_focused()
    page.keyboard.press("Escape")
    expect(second.locator("details.edit")).not_to_have_attribute("open", "")
    expect(second).to_be_focused()
    # The focus ring is visible on a focused control.
    button = page.get_by_role("button", name="Read this paper again")
    button.focus()
    assert button.evaluate("el => getComputedStyle(el).outlineStyle") == "solid"


def test_phone_width_has_no_sideways_scroll_and_44px_targets(page: Page, server: str) -> None:
    page.set_viewport_size({"width": 360, "height": 780})
    create_case(page, server)
    add_and_read(page, "invoice", "Tax invoice")
    width = page.evaluate("document.documentElement.scrollWidth")
    assert width <= 360, width
    for name in ("Read this paper again", "Add this paper", "Confirm these values"):
        box = page.get_by_role("button", name=name).bounding_box()
        assert box is not None and box["height"] >= 44, (name, box)
    expect(page.locator(".claims-table thead")).to_be_hidden()


def test_deleting_a_case_needs_confirmation_and_removes_it(page: Page, server: str) -> None:
    create_case(page, server)
    case_url = page.url
    page.get_by_role("button", name="Delete case").click()
    expect(page).to_have_url(case_url)  # the checkbox is required first
    page.get_by_label("I understand this can't be undone").check()
    page.get_by_role("button", name="Delete case").click()
    expect(page.get_by_text("The case and its files were deleted.")).to_be_visible()
    expect(page.get_by_text("No cases yet.")).to_be_visible()
    assert page.request.get(case_url).status == 404


def test_reader_down_shows_the_fix_and_hand_entry_works(
    page: Page, server_without_ollama: str
) -> None:
    create_case(page, server_without_ollama)
    page.locator("#file").set_input_files(str(DEMO / "invoice.jpg"))
    page.get_by_role("button", name="Add this paper").click()
    page.get_by_role("button", name="Check this paper").click()
    status = page.locator(".status-line")
    expect(status).to_contain_text("can't reach Ollama", timeout=20_000)
    expect(page.get_by_role("heading", name="Values on this paper")).to_be_visible()
    row = page.locator("tr.row", has=page.get_by_role("rowheader", name="Invoice total"))
    row.get_by_text("Edit").click()
    row.get_by_label("Value as printed on the paper").fill("5,00,000.00")
    row.get_by_role("button", name="Save value").click()
    row = page.locator("tr.row", has=page.get_by_role("rowheader", name="Invoice total"))
    expect(row.locator(".hand")).to_have_text("5,00,000.00")
    expect(row).to_contain_text("Edited by you")
