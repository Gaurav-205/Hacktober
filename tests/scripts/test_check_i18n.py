"""Tests for scripts/check_i18n.py (string-file parity and Hindi script checks)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_i18n.py"


def run(
    tmp_path: Path,
    en: dict[str, object] | None,
    hi: dict[str, object] | None,
    template: str = "",
    code: str = "",
) -> subprocess.CompletedProcess[str]:
    i18n = tmp_path / "i18n"
    i18n.mkdir(exist_ok=True)
    for name, data in (("en.json", en), ("hi.json", hi)):
        if data is not None:
            (i18n / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    templates = tmp_path / "templates"
    templates.mkdir(exist_ok=True)
    (templates / "page.html").write_text(template, "utf-8")
    code_dir = tmp_path / "code"
    code_dir.mkdir(exist_ok=True)
    (code_dir / "rules.py").write_text(code, "utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dir",
            str(i18n),
            "--templates",
            str(templates),
            "--code",
            str(code_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


GOOD_EN = {"nav.cases": "Cases", "rule.GSTIN-STATE": "The first two digits {code} are wrong."}
GOOD_HI = {"nav.cases": "मामले", "rule.GSTIN-STATE": "पहले दो अंक {code} गलत हैं।"}


def test_matching_files_pass(tmp_path: Path) -> None:
    result = run(tmp_path, GOOD_EN, GOOD_HI, template='{{ t("nav.cases") }}')
    assert result.returncode == 0, result.stdout
    assert result.stdout == ""


def test_no_files_yet_is_clean(tmp_path: Path) -> None:
    result = run(tmp_path, None, None)
    assert result.returncode == 0
    assert "no i18n files yet" in result.stdout


def test_one_file_missing_is_a_finding(tmp_path: Path) -> None:
    result = run(tmp_path, GOOD_EN, None)
    assert result.returncode == 1
    assert "hi.json:0: a: file is missing" in result.stdout


def test_key_missing_from_hindi_is_reported(tmp_path: Path) -> None:
    en = {**GOOD_EN, "nav.about": "About"}
    result = run(tmp_path, en, GOOD_HI)
    assert result.returncode == 1
    assert "b: nav.about: missing (present in en.json)" in result.stdout


def test_key_missing_from_english_is_reported(tmp_path: Path) -> None:
    hi = {**GOOD_HI, "nav.about": "परिचय"}
    result = run(tmp_path, GOOD_EN, hi)
    assert "b: nav.about: missing (present in hi.json)" in result.stdout


def test_placeholder_mismatch_is_reported(tmp_path: Path) -> None:
    hi = {**GOOD_HI, "rule.GSTIN-STATE": "पहले दो अंक {kod} गलत हैं।"}
    result = run(tmp_path, GOOD_EN, hi)
    assert result.returncode == 1
    assert "c: rule.GSTIN-STATE: placeholders differ" in result.stdout


def test_empty_and_non_string_values_are_reported(tmp_path: Path) -> None:
    result = run(tmp_path, {**GOOD_EN, "x.empty": " "}, {**GOOD_HI, "x.empty": 3})
    assert "a: x.empty: value is empty" in result.stdout
    assert "a: x.empty: value must be a string" in result.stdout


def test_invalid_json_is_reported_with_its_line(tmp_path: Path) -> None:
    i18n = tmp_path / "i18n"
    i18n.mkdir()
    (i18n / "en.json").write_text('{\n "a": "b",\n}', "utf-8")
    (i18n / "hi.json").write_text("{}", "utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(i18n)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "en.json:3: a: not valid JSON" in result.stdout


def test_missing_key_marker_is_reported(tmp_path: Path) -> None:
    result = run(tmp_path, {**GOOD_EN, "nav.cases": "⟦nav.cases⟧"}, GOOD_HI)
    assert "d: nav.cases: contains a missing-key marker" in result.stdout


def test_latin_words_in_hindi_are_reported(tmp_path: Path) -> None:
    hi = {**GOOD_HI, "nav.cases": "Cases मामले"}
    result = run(tmp_path, GOOD_EN, hi)
    assert result.returncode == 1
    assert "e: nav.cases: Latin words ['Cases']" in result.stdout


@pytest.mark.parametrize(
    "hindi",
    [
        "GSTIN का चेकसम सही है।",
        "JPEG, PNG, WebP या HEIC फ़ोटो, या PDF",
        "होस्टेड Gemma 4 (Gemini API)",
        "मॉडल {model} डाउनलोड नहीं है। चलाएँ: ollama pull {model}",
        "फ़ाइल `DOMAIN_RULES.md` देखें",
    ],
)
def test_allowed_latin_in_hindi_passes(tmp_path: Path, hindi: str) -> None:
    en_value = "Run: ollama pull {model}" if "{model}" in hindi else "English"
    result = run(tmp_path, {"k.v": en_value}, {"k.v": hindi})
    assert result.returncode == 0, result.stdout


def test_template_key_missing_from_english_is_reported(tmp_path: Path) -> None:
    result = run(tmp_path, GOOD_EN, GOOD_HI, template='<h1>{{ t("cases.title") }}</h1>')
    assert result.returncode == 1
    assert "page.html:1: f: cases.title: used in a template" in result.stdout


def test_code_message_key_missing_from_english_is_reported(tmp_path: Path) -> None:
    code = 'x = 1\nFinding(message_key="rule.INV-TOTAL")\nparams = {"expected_key": "term.igst"}\n'
    result = run(tmp_path, GOOD_EN, GOOD_HI, code=code)
    assert result.returncode == 1
    assert "rules.py:2: g: rule.INV-TOTAL: used in code" in result.stdout
    assert "rules.py:3: g: term.igst: used in code" in result.stdout


def test_dynamic_code_keys_are_not_guessed(tmp_path: Path) -> None:
    result = run(tmp_path, GOOD_EN, GOOD_HI, code='Finding(message_key=f"rule.{rule_id}")\n')
    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------- own errors: exit 2
def run_dir(i18n: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(i18n), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def assert_tool_error(result: subprocess.CompletedProcess[str], *fragments: str) -> None:
    """Exit 2 with one line on stderr naming the problem, and no findings on stdout."""
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert len(lines) == 1, result.stderr
    assert lines[0].startswith("check_i18n: ")
    for fragment in fragments:
        assert fragment in lines[0]


@pytest.mark.parametrize("name", ["en.json", "hi.json"])
def test_string_file_that_is_not_utf8_is_a_tool_error(tmp_path: Path, name: str) -> None:
    i18n = tmp_path / "i18n"
    i18n.mkdir()
    for good, data in (("en.json", GOOD_EN), ("hi.json", GOOD_HI)):
        (i18n / good).write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    (i18n / name).write_bytes(b"\xff")

    assert_tool_error(run_dir(i18n), name, "not valid UTF-8")


def test_template_that_is_not_utf8_is_a_tool_error(tmp_path: Path) -> None:
    i18n = tmp_path / "i18n"
    i18n.mkdir()
    (i18n / "en.json").write_text(json.dumps(GOOD_EN), "utf-8")
    (i18n / "hi.json").write_text(json.dumps(GOOD_HI, ensure_ascii=False), "utf-8")
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "page.html").write_bytes(b"\xff")

    result = run_dir(i18n, "--templates", str(templates), "--code", str(tmp_path / "none"))

    assert_tool_error(result, "page.html", "not valid UTF-8")


def test_string_file_that_cannot_be_read_is_a_tool_error(tmp_path: Path) -> None:
    i18n = tmp_path / "i18n"
    (i18n / "en.json").mkdir(parents=True)  # a directory where the file should be
    (i18n / "hi.json").write_text(json.dumps(GOOD_HI, ensure_ascii=False), "utf-8")

    assert_tool_error(run_dir(i18n), "en.json")


def test_template_key_prefix_passes_when_a_key_has_that_prefix(tmp_path: Path) -> None:
    template = '<p>{{ t("nav." ~ name) }}</p>'
    result = run(tmp_path, GOOD_EN, GOOD_HI, template=template)
    assert result.returncode == 0, result.stdout


def test_template_key_prefix_with_no_matching_key_is_reported(tmp_path: Path) -> None:
    template = '<p>{{ t("nothing.here." ~ name) }}</p>'
    result = run(tmp_path, GOOD_EN, GOOD_HI, template=template)
    assert result.returncode == 1
    assert (
        "page.html:1: f: nothing.here.: no key in en.json starts with this prefix" in result.stdout
    )
