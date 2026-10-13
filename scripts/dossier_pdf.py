"""Print a case's evidence file to an A4 PDF with Chromium (make dossier-pdf CASE=<id>).

Needs a running Munim (make run). Writes data/exports/<case>.pdf, or the path given with --out.
Exit 0 written, 1 the case was not found, 2 the server could not be reached.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


def render(url: str, out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            response = page.goto(url, wait_until="networkidle")
        except PlaywrightError as exc:
            print(
                f"dossier_pdf: cannot reach {url}: {exc.message.splitlines()[0]}", file=sys.stderr
            )
            return 2
        if response is None or response.status != 200:
            print(
                f"dossier_pdf: {url} answered {response.status if response else 'nothing'}",
                file=sys.stderr,
            )
            return 1
        page.emulate_media(media="print")
        page.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True)
        browser.close()
    print(f"dossier_pdf: wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case")
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    out = args.out or Path("data") / "exports" / f"{args.case}.pdf"
    return render(f"{args.base}/cases/{args.case}/dossier", out)


if __name__ == "__main__":
    raise SystemExit(main())
