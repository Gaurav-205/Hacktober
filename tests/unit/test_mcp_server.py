"""Tests for the Munim MCP server."""

import json

from munim_mcp.server import (
    handle_calculate_msmed_interest,
    handle_request,
    handle_verify_gstin,
    handle_verify_invoice_math,
)


def test_mcp_initialize() -> None:
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }
    resp = handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == "munim-mcp"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_tools_list() -> None:
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = handle_request(req)
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "calculate_msmed_interest" in tool_names
    assert "verify_gstin" in tool_names
    assert "verify_invoice_math" in tool_names


def test_mcp_verify_gstin_valid() -> None:
    # 27AAPFU0939F1ZV is a valid GSTIN
    res = handle_verify_gstin({"gstin": "27AAPFU0939F1ZV"})
    data = json.loads(res["content"][0]["text"])
    assert data["ok"] is True
    assert data["state_code"] == "27"
    assert data["pan"] == "AAPFU0939F"
    assert data["errors"] == []


def test_mcp_verify_gstin_invalid_checksum() -> None:
    # Mutate last character
    res = handle_verify_gstin({"gstin": "27AAPFU0939F1ZA"})
    data = json.loads(res["content"][0]["text"])
    assert data["ok"] is False
    assert "GSTIN-CHECKSUM" in data["errors"]


def test_mcp_verify_invoice_math() -> None:
    # Taxable 1000.00 (100000 paise), CGST/SGST 90.00 each, Total 1180.00 (118000 paise)
    res = handle_verify_invoice_math(
        {
            "taxable_paise": 100000,
            "cgst_paise": 9000,
            "sgst_paise": 9000,
            "igst_paise": 0,
            "total_paise": 118000,
        }
    )
    data = json.loads(res["content"][0]["text"])
    assert data["ok"] is True
    assert data["difference_paise"] == 0

    # Discrepancy
    res_bad = handle_verify_invoice_math(
        {
            "taxable_paise": 100000,
            "cgst_paise": 9000,
            "sgst_paise": 9000,
            "igst_paise": 0,
            "total_paise": 120000,  # 20 rupees extra claimed
        }
    )
    data_bad = json.loads(res_bad["content"][0]["text"])
    assert data_bad["ok"] is False
    assert data_bad["difference_paise"] == -2000


def test_mcp_calculate_interest() -> None:
    res = handle_calculate_msmed_interest(
        {
            "principal_paise": 100_000_00,  # ₹1,00,000
            "acceptance_date": "2024-01-01",
            "agreement": "none",
            "as_on": "2024-04-01",
            "bank_rate_percent": "6.75",
        }
    )
    data = json.loads(res["content"][0]["text"])
    assert data["due_date"] == "2024-01-16"
    assert data["days_late"] > 70
    assert data["interest_paise"] > 0
    assert "₹" in data["interest_formatted"]
