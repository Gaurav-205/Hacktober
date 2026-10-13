"""The evaluation harness, the committed fixtures and the report schema (AI_SPEC 8, D10)."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from munim_ai.evaluation import caught, iou, run_evaluation, same_value
from munim_ai.providers.replay import ReplayProvider
from munim_core.verify.models import FieldRef, Finding, Severity, Status

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "eval" / "fixtures"
AS_ON = date(2026, 10, 13)


def load_script(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- metric functions
@pytest.mark.parametrize(
    ("field", "read", "truth", "same"),
    [
        ("invoice_total", "500000", "5,00,000.00", True),
        ("invoice_total", "5,00,000.10", "5,00,000.00", False),
        ("round_off", "(0.22)", "-0.22", True),
        ("invoice_date", "21-03-2026", "21/03/2026", True),
        ("invoice_date", "03/12/2026", "12/03/2026", False),
        ("buyer_gstin", "27 aaapz 5678 z1z1", "27AAAPZ5678Z1Z1", True),
        ("buyer_name", "demo  textiles LTD", "Demo Textiles Ltd", True),
        ("buyer_name", None, "Demo Textiles Ltd", False),
    ],
)
def test_same_value_normalises_by_field_type(
    field: str, read: str | None, truth: str, same: bool
) -> None:
    assert same_value(field, read, truth) is same


def test_iou() -> None:
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert iou([0, 0, 10, 10], [0, 5, 10, 15]) == pytest.approx(50 / 150)
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
    assert iou(None, [0, 0, 1, 1]) == 0.0


def finding(status: Status, *refs: FieldRef) -> Finding:
    return Finding("X", status, Severity.BLOCKING, "rule.X", {}, refs, "1")


def test_wrong_field_is_caught_only_by_a_failed_or_flagged_rule_naming_it() -> None:
    ref = FieldRef("invoice", "invoice_total")
    other = FieldRef("invoice", "taxable_total")
    assert caught([finding(Status.FAILED, ref)], ref) == ["X"]
    assert caught([finding(Status.NEEDS_REVIEW, other, ref)], ref) == ["X"]
    assert caught([finding(Status.PASSED, ref), finding(Status.SKIPPED, ref)], ref) == []
    assert caught([finding(Status.FAILED, other)], ref) == []


# ---------------------------------------------------------------- committed fixtures
def test_every_file_in_the_manifest_exists_with_its_hash() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    assert manifest["synthetic"] is True
    for entry in manifest["files"]:
        data = (FIXTURES / entry["path"]).read_bytes()
        assert len(data) == entry["size"], entry["path"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]


def test_fixture_set_has_the_promised_shape() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    plain = [p for p in manifest["papers"] if not p["injected"]]
    kinds = {k: sum(p["kind"] == k for p in plain) for k in ("invoice", "challan", "po")}
    assert kinds == {"invoice": 12, "challan": 10, "po": 8}
    assert sum(p["injected"] for p in manifest["papers"]) == 5
    images = [f for f in manifest["files"] if f["path"].endswith(".jpg")]
    assert sum(f["size"] for f in images) < 6_000_000
    assert all(f["size"] < 2_000_000 for f in manifest["files"])


def test_generator_is_deterministic(tmp_path: Path) -> None:
    gen = load_script(ROOT / "scripts" / "gen_fixtures.py")
    assert gen.main(["--out", str(tmp_path / "a")]) == 0
    assert gen.main(["--out", str(tmp_path / "a")]) == 1  # refuses to overwrite
    assert gen.main(["--out", str(tmp_path / "b"), "--force"]) == 0
    a = json.loads((tmp_path / "a" / "manifest.json").read_text())
    b = json.loads((tmp_path / "b" / "manifest.json").read_text())
    assert a["files"] == b["files"]


# ---------------------------------------------------------------- the harness over the demo
async def test_demo_misread_is_wrong_caught_and_repaired_by_the_model() -> None:
    report = await run_evaluation(
        ReplayProvider(FIXTURES / "replay"), FIXTURES, as_on=AS_ON, case_ids={"demo"}
    )
    assert report["provider"] == "replay" and report["recorded_from"] == "synthetic"
    assert report["n_papers"] == 3
    assert report["missing_recordings"] == []
    examples = {(f["paper"], f["field"]): f for f in report["failure_examples"]}
    gstin = examples[("demo-invoice", "buyer_gstin")]
    assert gstin["caught"] is True
    assert "GSTIN-CHECKSUM" in gstin["rules"]
    assert gstin["crop"].startswith("data:image/jpeg;base64,")
    assert report["metrics"]["wrong_and_passed"]["count"] == 0
    assert report["metrics"]["repair"]["model_misreads"] == {"corrected": 1}
    assert report[
        "summary"
    ] == "In 1 of {} fields the value was wrong; the checks caught 1 of those 1.".format(
        report["n_fields"]
    )


async def test_injected_gstin_faults_are_reported_honestly() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    injected = {c["id"] for c in manifest["cases"] if c["injected"]}
    report = await run_evaluation(
        ReplayProvider(FIXTURES / "replay"), FIXTURES, as_on=AS_ON, case_ids=injected
    )
    # The look-alike fault is fixed by the map; the other is printed, so a re-read is unchanged.
    assert report["metrics"]["repair"]["injected_gstin"] == {"corrected": 1, "unchanged": 1}


# ---------------------------------------------------------------- report validation
def test_committed_replay_report_is_valid_and_an_edited_one_is_not() -> None:
    validate = load_script(ROOT / "eval" / "validate_report.py")
    report = json.loads((ROOT / "eval" / "reports" / "replay.json").read_text())
    assert validate.problems(report) == []
    broken = copy.deepcopy(report)
    broken["recorded_from"] = "guess"
    del broken["metrics"]["wrong_and_passed"]
    found = validate.problems(broken)
    assert any(p.startswith("recorded_from:") for p in found)
    assert any("wrong_and_passed" in p for p in found)
    stale = copy.deepcopy(report)
    stale["prompt_versions"]["invoice"] = "0"
    assert validate.problems(stale) == [
        "prompt_versions: differ from the prompt files; re-run the evaluation"
    ]


def test_run_eval_writes_replay_json_not_latest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_eval = load_script(ROOT / "eval" / "run_eval.py")
    monkeypatch.setenv("MUNIM_PROVIDER", "replay")
    monkeypatch.setattr(run_eval, "REPORTS", tmp_path)
    assert run_eval.main(["--case", "demo", "--date", "2026-10-13"]) == 0
    assert (tmp_path / "replay.json").is_file()
    assert not (tmp_path / "latest.json").exists()
