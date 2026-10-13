"""Screenshots of Munim's main pages at 360, 768 and 1440 px in English and Hindi (make screens).

Starts its own server on a free loopback port with a temporary data folder and the replay
reader, builds the confirmed demo case from the synthetic fixtures, and writes PNGs to
docs/screens/. Exit 0 written, 2 when the server or browser fails.
"""

from __future__ import annotations

import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from munim_web.main import create_app  # noqa: E402
from munim_web.settings import Settings  # noqa: E402

OUT = ROOT / "docs" / "screens"
DEMO = ROOT / "eval" / "fixtures" / "demo"
WIDTHS = (360, 768, 1440)
KINDS = (("invoice", "Tax invoice"), ("challan", "Delivery challan"), ("po", "Purchase order"))


def start(data: Path) -> tuple[str, uvicorn.Server]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = int(s.getsockname()[1])
    settings = Settings(
        data_dir=data, port=port, provider="replay", replay_dir=ROOT / "eval/fixtures/replay"
    )
    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/healthz").status_code == 200:
                return url, server
        except httpx.HTTPError:
            time.sleep(0.05)
    raise RuntimeError("server did not start")


def demo_case(page: Page, url: str) -> str:
    page.goto(url + "/")
    page.locator("#title").fill("Sample Fabricators v Demo Textiles")
    page.locator("#supplier_name").fill("Sample Fabricators Pvt Ltd")
    page.locator("#buyer_name").fill("Demo Textiles Ltd")
    page.locator("form[action='/cases'] button").click()
    page.wait_for_url("**/cases/*")
    for kind, label in KINDS:
        page.locator("#file").set_input_files(str(DEMO / f"{kind}.jpg"))
        page.locator("#kind").select_option(kind)
        page.locator(".dropzone button").click()
        expect(page.locator("#viewer-title")).to_have_text(label)
        page.locator("form[action$='/read'] button").click()
        expect(page.locator(".status-line")).to_have_text("Paper checked", timeout=20_000)
    page.locator("input[name=agreement][value=written]").check()
    page.locator("#credit_days").fill("30")
    page.locator("#as_on_date").fill("13/10/2026")
    page.locator("#terms button[type=submit]").click()
    page.locator("[data-owed]").wait_for()
    page.locator("form[action$='/confirm'] button").click()
    page.locator("svg.stamp").wait_for()
    return page.url.split("/cases/")[1].split("?")[0]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as data:
        try:
            url, server = start(Path(data))
        except RuntimeError as exc:
            print(f"screens: {exc}", file=sys.stderr)
            return 2
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            case_id = demo_case(page, url)
            pages = {
                "cases": "/",
                "workbench": f"/cases/{case_id}",
                "evidence": f"/cases/{case_id}/dossier",
            }
            count = 0
            for lang in ("en", "hi"):
                page.context.add_cookies([{"name": "munim_lang", "value": lang, "url": url}])
                for width in WIDTHS:
                    page.set_viewport_size({"width": width, "height": 900})
                    for name, path in pages.items():
                        page.goto(url + path)
                        page.evaluate("document.fonts.ready")
                        page.screenshot(path=str(OUT / f"{name}-{width}-{lang}.png"))
                        count += 1
            browser.close()
        server.should_exit = True
    print(f"screens: {count} screenshots in {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
