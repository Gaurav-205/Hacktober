"""Model Context Protocol (MCP) server for Munim.

Exposes Munim's deterministic GSTIN validation, invoice math, and MSMED Act
interest calculation tools to LLMs and AI coding assistants via standard JSON-RPC 2.0 stdio.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from typing import Any

from munim_core.clock import BankRate, ClockInput, compute
from munim_core.ids import check_gstin
from munim_core.money import format_inr

SERVER_NAME = "munim-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "calculate_msmed_interest",
        "description": (
            "Calculate statutory compound interest with monthly rests under Section 16 "
            "of the MSMED Act, 2006 (at 3x RBI Bank Rate)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "principal_paise": {
                    "type": "integer",
                    "description": (
                        "Principal amount in integer paise (e.g. ₹10,000.00 is 1000000 paise)."
                    ),
                },
                "acceptance_date": {
                    "type": "string",
                    "description": (
                        "Date of goods/service delivery or acceptance in 'YYYY-MM-DD' format."
                    ),
                },
                "agreement": {
                    "type": "string",
                    "enum": ["none", "written"],
                    "description": (
                        "Whether a written credit agreement exists ('none' defaults to 15 days, "
                        "'written' uses credit_days capped at 45)."
                    ),
                },
                "credit_days": {
                    "type": "integer",
                    "description": (
                        "Agreed credit days if agreement is 'written' (capped at 45 under law)."
                    ),
                },
                "as_on": {
                    "type": "string",
                    "description": (
                        "Evaluation date up to which interest is computed in 'YYYY-MM-DD' format."
                    ),
                },
                "bank_rate_percent": {
                    "type": "string",
                    "description": (
                        "RBI Bank Rate percentage (e.g. '6.75'). Interest rate is 3x this rate."
                    ),
                },
            },
            "required": ["principal_paise", "acceptance_date", "agreement", "as_on"],
        },
    },
    {
        "name": "verify_gstin",
        "description": (
            "Verify an Indian Goods and Services Tax Identification Number (GSTIN) "
            "against format, state code, and ISO/IEC 7064 mod-36 checksum."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "gstin": {
                    "type": "string",
                    "description": "The 15-character GSTIN string to check.",
                },
            },
            "required": ["gstin"],
        },
    },
    {
        "name": "verify_invoice_math",
        "description": (
            "Verify deterministic arithmetic on an Indian tax invoice "
            "(Taxable Value + CGST + SGST + IGST + Round Off = Total)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "taxable_paise": {
                    "type": "integer",
                    "description": "Taxable value in integer paise.",
                },
                "cgst_paise": {
                    "type": "integer",
                    "description": "Central GST in integer paise (0 if inter-state).",
                },
                "sgst_paise": {
                    "type": "integer",
                    "description": "State GST in integer paise (0 if inter-state).",
                },
                "igst_paise": {
                    "type": "integer",
                    "description": "Integrated GST in integer paise (0 if intra-state).",
                },
                "total_paise": {
                    "type": "integer",
                    "description": "Printed total invoice amount in integer paise.",
                },
                "round_off_paise": {
                    "type": "integer",
                    "description": "Optional round-off amount in integer paise (default 0).",
                },
            },
            "required": [
                "taxable_paise",
                "cgst_paise",
                "sgst_paise",
                "igst_paise",
                "total_paise",
            ],
        },
    },
]


def handle_calculate_msmed_interest(arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        principal = int(arguments["principal_paise"])
        acc_dt = date.fromisoformat(arguments["acceptance_date"])
        as_on_dt = date.fromisoformat(arguments["as_on"])
        agreement = arguments.get("agreement", "none")
        credit_days = int(arguments["credit_days"]) if "credit_days" in arguments else None

        rate_pct = Decimal(str(arguments.get("bank_rate_percent", "6.75")))
        rates = (BankRate(effective_from=date(2000, 1, 1), percent=rate_pct),)

        clock_in = ClockInput(
            acceptance_date=acc_dt,
            agreement=agreement,  # type: ignore[arg-type]
            credit_days=credit_days,
            principal_paise=principal,
            as_on=as_on_dt,
            rates=rates,
            payments=(),
        )

        res = compute(clock_in)
        out = {
            "due_date": res.due_date.isoformat(),
            "as_on": as_on_dt.isoformat(),
            "days_late": res.days_late,
            "principal_paise": principal,
            "principal_formatted": format_inr(principal),
            "interest_paise": res.interest_paise,
            "interest_formatted": format_inr(res.interest_paise),
            "total_paise": res.total_paise,
            "total_formatted": format_inr(res.total_paise),
            "cap_applied": res.cap_applied,
            "basis": res.basis_key,
            "number_of_monthly_rests": len(res.steps),
        }
        return {
            "content": [{"type": "text", "text": json.dumps(out, indent=2)}],
            "isError": False,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error computing interest: {e}"}],
            "isError": True,
        }


def handle_verify_gstin(arguments: dict[str, Any]) -> dict[str, Any]:
    gstin_raw = str(arguments.get("gstin", ""))
    res = check_gstin(gstin_raw)
    out = {
        "ok": res.ok,
        "normalised": res.normalised,
        "state_code": res.state_code,
        "pan": res.pan,
        "errors": list(res.errors),
        "normalisation_applied": res.normalisation_applied,
    }
    return {"content": [{"type": "text", "text": json.dumps(out, indent=2)}], "isError": False}


def handle_verify_invoice_math(arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        taxable = int(arguments.get("taxable_paise", 0))
        cgst = int(arguments.get("cgst_paise", 0))
        sgst = int(arguments.get("sgst_paise", 0))
        igst = int(arguments.get("igst_paise", 0))
        total = int(arguments.get("total_paise", 0))
        round_off = int(arguments.get("round_off_paise", 0))

        computed = taxable + cgst + sgst + igst + round_off
        diff = computed - total
        ok = diff == 0

        out = {
            "ok": ok,
            "computed_total_paise": computed,
            "printed_total_paise": total,
            "difference_paise": diff,
            "computed_total_formatted": format_inr(computed),
            "printed_total_formatted": format_inr(total),
        }
        return {
            "content": [{"type": "text", "text": json.dumps(out, indent=2)}],
            "isError": False,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error verifying invoice math: {e}"}],
            "isError": True,
        }


def handle_request(req: dict[str, Any]) -> dict[str, Any]:
    msg_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name == "calculate_msmed_interest":
            call_res = handle_calculate_msmed_interest(arguments)
        elif tool_name == "verify_gstin":
            call_res = handle_verify_gstin(arguments)
        elif tool_name == "verify_invoice_math":
            call_res = handle_verify_invoice_math(arguments)
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
            }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": call_res,
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def main() -> None:
    """Run MCP server in stdio mode."""
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            # Ignore client notifications without id
            if "id" not in req:
                continue
            resp = handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
