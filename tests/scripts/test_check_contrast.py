"""Tests for scripts/check_contrast.py (WCAG ratios of the DESIGN.md colour pairs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import load_script, run_script

pytestmark = pytest.mark.unit

# A synthetic DESIGN.md in the same shape as the real one. Line numbers matter:
# the bond row is line 16, the ink row line 18, the tick-wash row line 21.
DESIGN = """\
---
colors:
  bond: "#F3F4F6"
  sheet: "#FFFFFF"
  ink: "#15171C"
  muted: "#5C6272"
  hairline-strong: "#80879A"
  tick: "#1E7A4F"
  tick-wash: "#E3F2EA"
---

## 2. Colour palette and roles (synthetic sample)

| Token | Hex | Role | Notes |
| --- | --- | --- | --- |
| `bond` | `#F3F4F6` | Page | Text on it must be `ink` or `muted`. |
| `sheet` | `#FFFFFF` | Panels | Controls sit on it. |
| `ink` | `#15171C` | Text | 16.3:1 on bond |
| `hairline-strong` | `#80879A` | Edges | 3.59:1 on sheet (an edge, 3:1 minimum) |
| `tick` | `#1E7A4F` | Passed | 4.6:1 on its own wash |
| `tick-wash` | `#E3F2EA` | Passed row | Text on it is `ink` |

## 3. Typography
"""


def write_design(tmp_path: Path, text: str = DESIGN) -> Path:
    design = tmp_path / "DESIGN.md"
    design.write_text(text, encoding="utf-8")
    return design


def check(tmp_path: Path, text: str = DESIGN) -> tuple[int, list[str]]:
    result = run_script("check_contrast", "--design", write_design(tmp_path, text))
    return result.returncode, result.stdout.splitlines()


# ------------------------------------------------------------------ the real DESIGN.md
def test_real_design_md_has_the_known_ratios_and_passes() -> None:
    result = run_script("check_contrast")

    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout
    assert "ink on bond: 16.29 (threshold 4.5, claimed 16.3) ok" in out
    assert "hairline-strong on sheet: 3.59 (threshold 3.0, claimed 3.59) ok" in out
    assert "tick on tick-wash: 4.59 (threshold 4.5, claimed 4.6) ok" in out
    assert "FAIL" not in out
    assert out.rstrip().endswith("problems")
    assert ", 0 problems" in out.splitlines()[-1]


# ------------------------------------------------------------------ synthetic files
def test_synthetic_design_passes_and_reads_every_note_form(tmp_path: Path) -> None:
    code, lines = check(tmp_path)

    assert code == 0, lines
    assert lines[-1] == "check_contrast: 5 pairs checked, 0 problems"
    # "Text on it must be" (bond row) and "16.3:1 on bond" (ink row) name the same
    # pair; it is checked once, keeps its first position and takes the claimed ratio.
    assert lines[:-1] == [
        "ink on bond: 16.29 (threshold 4.5, claimed 16.3) ok",
        "muted on bond: 5.54 (threshold 4.5, claimed none) ok",
        "hairline-strong on sheet: 3.59 (threshold 3.0, claimed 3.59) ok",
        "tick on tick-wash: 4.59 (threshold 4.5, claimed 4.6) ok",
        "ink on tick-wash: 15.50 (threshold 4.5, claimed none) ok",
    ]


def test_text_pair_below_four_and_a_half_fails(tmp_path: Path) -> None:
    text = DESIGN.replace('  muted: "#5C6272"', '  muted: "#AAAAAA"').replace(
        "`muted` | `#5C6272`", "`muted` | `#AAAAAA`"
    )

    code, lines = check(tmp_path, text)

    assert code == 1
    assert (
        "muted on bond: 2.11 (threshold 4.5, claimed none) "
        "FAIL: below the 4.5:1 minimum (DESIGN.md:16)"
    ) in lines
    assert lines[-1] == "check_contrast: 5 pairs checked, 1 problems"


def test_edge_token_uses_the_three_to_one_threshold(tmp_path: Path) -> None:
    lighter = DESIGN.replace("#80879A", "#A0A6B4").replace("3.59:1 on sheet", "2.5:1 on sheet")

    code, lines = check(tmp_path, lighter)

    assert code == 1
    failing = [line for line in lines if line.startswith("hairline-strong on sheet:")]
    assert len(failing) == 1
    assert (
        "(threshold 3.0, claimed 2.5) FAIL: below the 3.0:1 minimum (DESIGN.md:19)" in (failing[0])
    )


def test_claimed_ratio_more_than_a_tenth_off_fails(tmp_path: Path) -> None:
    code, lines = check(tmp_path, DESIGN.replace("16.3:1 on bond", "15.0:1 on bond"))

    assert code == 1
    assert (
        "ink on bond: 16.29 (threshold 4.5, claimed 15.0) "
        "FAIL: claimed ratio is wrong (DESIGN.md says 15.0:1) (DESIGN.md:18)"
    ) in lines


@pytest.mark.parametrize(("claimed", "code"), [("16.2", 0), ("16.39", 0), ("16.4", 1)])
def test_claim_tolerance_is_one_tenth(tmp_path: Path, claimed: str, code: int) -> None:
    returncode, lines = check(tmp_path, DESIGN.replace("16.3:1 on bond", f"{claimed}:1 on bond"))

    assert returncode == code, lines
    line = next(line for line in lines if f"claimed {claimed})" in line)
    assert line.startswith("ink on bond: 16.29")
    assert ("FAIL" in line) is bool(code)


def test_table_hex_that_differs_from_front_matter_fails(tmp_path: Path) -> None:
    code, lines = check(tmp_path, DESIGN.replace("`ink` | `#15171C`", "`ink` | `#000000`"))

    assert code == 1
    assert (
        "DESIGN.md:18: contrast: table hex #000000 for 'ink' differs from the front matter "
        "(#15171C)"
    ) in lines


def test_unknown_token_in_notes_fails(tmp_path: Path) -> None:
    code, lines = check(tmp_path, DESIGN.replace("Text on it is `ink`", "Text on it is `ghost`"))

    assert code == 1
    assert "DESIGN.md:21: contrast: unknown token 'ghost'" in lines


def test_table_token_missing_from_front_matter_fails(tmp_path: Path) -> None:
    text = DESIGN.replace(
        "| Controls sit on it. |", "| Controls sit on it. |\n| `ghost` | `#000000` | x | |"
    )

    code, lines = check(tmp_path, text)

    assert code == 1
    assert "DESIGN.md:18: contrast: table token 'ghost' is not in the front matter colors" in lines


def test_own_wash_without_a_wash_token_fails(tmp_path: Path) -> None:
    code, lines = check(tmp_path, DESIGN.replace("16.3:1 on bond", "16.3:1 on its own wash"))

    assert code == 1
    assert "DESIGN.md:18: contrast: 'ink' has no '-wash' token for 'on its own wash'" in lines


def test_notes_without_any_pair_fail(tmp_path: Path) -> None:
    table_start = DESIGN.index("| `bond`")
    table_end = DESIGN.index("\n## 3.")
    text = DESIGN[:table_start] + "| `sheet` | `#FFFFFF` | Panels | none |\n" + DESIGN[table_end:]

    code, lines = check(tmp_path, text)

    assert code == 1
    assert "DESIGN.md:1: contrast: no colour pairs found in the section 2 notes" in lines
    assert lines[-1] == "check_contrast: 0 pairs checked, 1 problems"


BAD_INPUT = [
    pytest.param(None, "cannot read", id="missing-file"),
    pytest.param("no front matter\n", "the first line must be '---'", id="no-front-matter"),
    pytest.param("---\ncolors: {}\n", "no closing '---' line", id="unclosed"),
    pytest.param("---\ncolors: [\n---\n", "not valid YAML", id="invalid-yaml"),
    pytest.param(
        DESIGN.replace("colors:", "palette:"),
        "'colors' must be a non-empty mapping",
        id="no-colors",
    ),
    pytest.param(
        DESIGN.replace('"#FFFFFF"', '"#FFFFFF80"'), "is not an opaque hex colour", id="alpha"
    ),
    pytest.param(DESIGN.replace("## 2.", "## Two."), "section '## 2.'", id="no-section-2"),
    pytest.param(
        DESIGN[: DESIGN.index("| Token")] + "No table here.\n", "no colour table", id="no-table"
    ),
    pytest.param(
        DESIGN.replace("| Controls sit on it. |", "|"), "fewer than 4 columns", id="short-row"
    ),
]


@pytest.mark.parametrize(("text", "message"), BAD_INPUT)
def test_unreadable_or_malformed_input_is_an_error(
    tmp_path: Path, text: str | None, message: str
) -> None:
    design = tmp_path / "DESIGN.md" if text is None else write_design(tmp_path, text)

    result = run_script("check_contrast", "--design", design)

    assert result.returncode == 2
    assert result.stderr.startswith("check_contrast: error:")
    assert message in result.stderr


def test_directory_instead_of_a_file_is_an_error(tmp_path: Path) -> None:
    result = run_script("check_contrast", "--design", tmp_path)

    assert result.returncode == 2
    assert "check_contrast: error: cannot read" in result.stderr


# ------------------------------------------------------------------ the formula
def test_contrast_ratio_matches_wcag_reference_values() -> None:
    module = load_script("check_contrast")

    assert module.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert module.contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0)
    assert module.contrast_ratio("#777777", "#777777") == pytest.approx(1.0)
    assert module.contrast_ratio("#fff", "#FFFFFF") == pytest.approx(1.0)
    # WCAG's own example threshold colour: #767676 on white is 4.54:1.
    assert round(module.contrast_ratio("#767676", "#FFFFFF"), 2) == 4.54


def test_relative_luminance_rejects_non_hex() -> None:
    module = load_script("check_contrast")

    with pytest.raises(ValueError, match="not an opaque hex colour"):
        module.relative_luminance("#12345678")
    with pytest.raises(ValueError, match="not an opaque hex colour"):
        module.relative_luminance("red")
