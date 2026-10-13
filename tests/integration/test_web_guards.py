"""Security guards, uploads, acceptance and deletion (docs/TESTING.md 4 and 8, API.md, D8, D11)."""

from __future__ import annotations

import io
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from munim_web.main import create_app
from munim_web.settings import Settings
from tests.integration.test_web_flow import BASE, ROOT, Web, demo_case

pytestmark = pytest.mark.integration


@pytest.fixture
def web(tmp_path: Path) -> Iterator[Web]:
    app = create_app(
        Settings(data_dir=tmp_path, provider="replay", replay_dir=ROOT / "eval/fixtures/replay")
    )
    app.app.state.today = date(2026, 10, 13)
    with TestClient(app, base_url=BASE) as client:
        yield Web(client)


# ---------------------------------------------------------------- headers, host, CSRF
def test_every_response_carries_the_security_headers(web: Web) -> None:
    for path in ("/", "/static/css/app.css", "/does-not-exist"):
        headers = web.client.get(path).headers
        assert "default-src 'self'" in headers["content-security-policy"]
        assert "frame-ancestors 'none'" in headers["content-security-policy"]
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"
        assert headers["permissions-policy"].startswith("camera=()")
    assert web.client.get("/").headers["cache-control"] == "no-store"
    assert "no-store" not in web.client.get("/static/css/app.css").headers.get("cache-control", "")


def test_a_foreign_host_header_is_refused(web: Web) -> None:
    r = web.client.get("/", headers={"host": "attacker.example:8765"})
    assert r.status_code == 400
    assert web.client.get("/", headers={"host": "localhost:8765"}).status_code == 200


def test_post_without_or_with_a_wrong_csrf_token_is_refused(web: Web) -> None:
    web.token  # noqa: B018 - sets the cookie
    form = {"title": "x", "supplier_name": "s", "buyer_name": "b"}
    assert web.client.post("/cases", data=form, follow_redirects=False).status_code == 403
    assert (
        web.client.post(
            "/cases", data={**form, "csrf_token": "wrong"}, follow_redirects=False
        ).status_code
        == 403
    )
    assert (
        web.client.post(
            "/cases", data=form, headers={"X-CSRF-Token": web.token}, follow_redirects=False
        ).status_code
        == 303
    )
    assert web.app.state.db.cases()[0]["title"] == "x"


def test_csrf_cookie_is_http_only_and_strict(web: Web) -> None:
    fresh = TestClient(web.client.app, base_url=BASE)
    cookie = fresh.get("/").headers["set-cookie"]
    assert cookie.startswith("munim_csrf_8765=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie


# ---------------------------------------------------------------- uploads
def upload(web: Web, case_id: str, name: str, data: bytes) -> str:
    r = web.post(
        f"/cases/{case_id}/papers", {"kind": "invoice"}, files={"file": (name, data, "image/jpeg")}
    )
    return str(r.headers.get("location", r.status_code))


def test_an_executable_named_jpg_is_refused(web: Web) -> None:
    case_id = web.new_case()
    assert upload(web, case_id, "invoice.jpg", b"MZ\x90\x00" + b"\x00" * 500).endswith(
        "error=paper.err.type"
    )
    assert web.app.state.db.papers(case_id) == []


def test_an_oversized_upload_is_refused_before_parsing(web: Web) -> None:
    case_id = web.new_case()
    big = b"\xff\xd8\xff" + b"\x00" * (15 * 1024 * 1024 + 100 * 1024)
    r = web.post(
        f"/cases/{case_id}/papers",
        {"kind": "invoice"},
        files={"file": ("big.jpg", big, "image/jpeg")},
    )
    assert r.status_code == 413
    assert web.app.state.db.papers(case_id) == []


def test_upload_stores_generated_names_and_strips_metadata(web: Web) -> None:
    case_id = web.new_case()
    image = Image.new("RGB", (400, 300), "white")
    exif = image.getexif()
    exif[0x010F] = "Synthetic Camera"
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    location = upload(web, case_id, "../../etc/passwd.jpg", out.getvalue())
    paper = web.app.state.db.paper(location.split("paper=")[1])
    assert paper["original_path"].endswith("original.jpg") and ".." not in paper["original_path"]
    derived = web.client.get(f"/papers/{paper['id']}/image")
    assert derived.headers["cache-control"] == "no-store"
    assert b"Synthetic Camera" not in derived.content


# ---------------------------------------------------------------- acceptance and confirm
def test_confirm_is_refused_until_a_failing_check_is_accepted_with_a_reason(web: Web) -> None:
    case_id, papers = demo_case(web)
    db = web.app.state.db
    claim = db.one(
        "SELECT * FROM claims WHERE paper_id = ? AND field = 'supplier_gstin'", (papers["invoice"],)
    )
    broken = claim["value_current"][:-1] + "M"
    web.post(f"/claims/{claim['id']}", {"value": broken, "version": str(claim["version"])})
    page = web.client.get(f"/cases/{case_id}?paper={papers['invoice']}").text
    assert "Doesn&#39;t match" in page or "Doesn't match" in page
    assert web.post(f"/cases/{case_id}/confirm").status_code == 409
    assert (
        web.post(f"/claims/{claim['id']}/accept", {"rule_id": "GSTIN-CHECKSUM", "reason": "no"})
        .headers["location"]
        .endswith("error=claims.accept.err#row-" + claim["id"])
    )
    for rule in ("GSTIN-CHECKSUM", "X-SUPPLIER-GSTIN"):
        web.post(
            f"/claims/{claim['id']}/accept",
            {"rule_id": rule, "reason": "Checked the paper by hand"},
        )
    assert web.post(f"/cases/{case_id}/confirm").status_code == 303
    page = web.client.get(f"/cases/{case_id}?paper={papers['invoice']}").text
    assert "Accepted by you: Checked the paper by hand" in page


def test_an_acceptance_lapses_when_its_value_changes(web: Web) -> None:
    case_id, papers = demo_case(web)
    db = web.app.state.db
    claim = db.one(
        "SELECT * FROM claims WHERE paper_id = ? AND field = 'supplier_gstin'", (papers["invoice"],)
    )
    web.post(
        f"/claims/{claim['id']}",
        {"value": claim["value_current"][:-1] + "M", "version": str(claim["version"])},
    )
    for rule in ("GSTIN-CHECKSUM", "X-SUPPLIER-GSTIN"):
        web.post(
            f"/claims/{claim['id']}/accept",
            {"rule_id": rule, "reason": "Checked the paper by hand"},
        )
    edited = db.one("SELECT * FROM claims WHERE id = ?", (claim["id"],))
    web.post(
        f"/claims/{claim['id']}",
        {"value": claim["value_current"][:-1] + "K", "version": str(edited["version"])},
    )
    assert web.post(f"/cases/{case_id}/confirm").status_code == 409


def test_a_stale_edit_is_refused(web: Web) -> None:
    case_id, papers = demo_case(web)
    claim = web.app.state.db.one(
        "SELECT * FROM claims WHERE paper_id = ? AND field = 'invoice_number'", (papers["invoice"],)
    )
    r = web.post(f"/claims/{claim['id']}", {"value": "X-1", "version": str(claim["version"] - 1)})
    assert "error=claims.stale" in r.headers["location"]
    assert (
        web.app.state.db.one("SELECT value_current FROM claims WHERE id = ?", (claim["id"],))[0]
        == claim["value_current"]
    )


# ---------------------------------------------------------------- delete
def test_deleting_a_case_removes_its_files_and_rows(web: Web, tmp_path: Path) -> None:
    case_id, _ = demo_case(web)
    assert any((tmp_path / "uploads" / case_id).rglob("*.jpg"))
    assert (
        web.post(f"/cases/{case_id}/delete").headers["location"] == f"/cases/{case_id}#delete"
    )  # not confirmed
    r = web.post(f"/cases/{case_id}/delete", {"sure": "yes"})
    assert r.headers["location"] == "/?deleted=1"
    assert not (tmp_path / "uploads" / case_id).exists()
    db = web.app.state.db
    for table in ("cases", "papers", "claims", "acceptances", "payments", "events"):
        assert db.one(f"SELECT COUNT(*) FROM {table}")[0] == 0, table  # noqa: S608
    assert db.all("PRAGMA foreign_key_check") == []
    raw = b"".join(p.read_bytes() for p in tmp_path.glob("munim.db*"))
    assert b"SF/2025-26/0412" not in raw and b"Demo Textiles" not in raw
    assert web.client.get(f"/cases/{case_id}").status_code == 404


# ---------------------------------------------------------------- JSON surface and Hindi
def test_json_api_verifies_a_gstin_and_runs_the_clock(web: Web) -> None:
    from tests.unit.verify_helpers import BUYER_GSTIN

    h = {"X-CSRF-Token": web.token}
    r = web.client.post("/api/v1/verify/gstin", json={"gstin": BUYER_GSTIN}, headers=h)
    assert r.json() == {"valid": True, "state_code": "27", "pan": "AAAPZ5678Z", "errors": []}
    body = {
        "acceptance_date": "2026-03-20",
        "agreement": "written",
        "credit_days": 30,
        "principal_paise": 50000000,
        "as_on": "2026-10-13",
        "rates": [{"effective_from": "2025-12-05", "percent": "5.50"}],
    }
    clock = web.client.post("/api/v1/clock", json=body, headers=h).json()
    assert (clock["due_date"], clock["days_late"], clock["interest_paise"]) == (
        "2026-04-19",
        177,
        4097671,
    )
    assert web.client.post("/api/v1/clock", json=body).status_code == 403


def test_hindi_pages_render_without_missing_keys(web: Web) -> None:
    case_id, papers = demo_case(web)
    web.client.cookies.set("munim_lang", "hi")
    for path in (
        "/",
        f"/cases/{case_id}",
        f"/cases/{case_id}/dossier",
        "/rules",
        "/settings",
        "/about",
        "/evaluation",
    ):
        r = web.client.get(path)
        assert r.status_code == 200, path
        assert 'lang="hi"' in r.text
        assert "⟦" not in r.text
    assert "इन मानों की पुष्टि करें" in web.client.get(f"/cases/{case_id}").text


# ---------------------------------------------------------------- case settings numbers
@pytest.mark.parametrize("printed", ["\u00b2", "3\u00b9"])
def test_credit_days_with_a_non_decimal_digit_is_refused_not_a_500(web: Web, printed: str) -> None:
    case_id, _ = demo_case(web)
    r = web.post(f"/cases/{case_id}/settings", {"credit_days": printed})
    assert r.status_code == 303
    assert "error=settings.case.err.days" in r.headers["location"]
    row = web.app.state.db.case(case_id)
    assert row is not None and row["credit_days"] is None


def test_notice_days_with_a_non_decimal_digit_is_ignored_not_a_500(web: Web) -> None:
    case_id, _ = demo_case(web)
    before = web.app.state.db.case(case_id)
    assert before is not None
    r = web.post(f"/cases/{case_id}/settings", {"notice_days": "\u00b2"})
    assert r.status_code == 303
    after = web.app.state.db.case(case_id)
    assert after is not None and after["notice_days"] == before["notice_days"]


def test_credit_days_in_devanagari_digits_are_stored_as_a_number(web: Web) -> None:
    case_id, _ = demo_case(web)
    r = web.post(f"/cases/{case_id}/settings", {"credit_days": "\u0969\u0966"})  # 30
    assert r.status_code == 303
    assert "error" not in r.headers["location"]
    row = web.app.state.db.case(case_id)
    assert row is not None and row["credit_days"] == 30
