"""Tests for scripts/build_tokens.py (DESIGN.md front matter to tokens.css)."""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import REPO_ROOT, load_script, run_script

pytestmark = pytest.mark.unit

FRONT_MATTER = """\
---
name: Sample design (synthetic)
colors:
  paper: "#FFFFFF"   # comments are ignored
  ink: "#15171C"
typography:
  family-ui: "Mukta, 'Noto Sans Devanagari', sans-serif"
  family-hand: "Kalam, cursive"
  body: { family: ui, size: 16px, line: 26px, weight: 400 }
  amount: { family: ui, size: 40px, line: 44px, weight: 600, tracking: -0.01em, features: [tnum] }
rounded:
  field: 2px
  none: 0px
spacing: { base: 4px, scale: [4, 8, 12] }
motion:
  stamp:
    duration: 160ms
    easing: "cubic-bezier(.2,.9,.3,1.2)"
    from: "scale(1.18)"
    to: "scale(1)"
  strike: { duration: 220ms, easing: "ease-out" }
  reduced-motion: "all of the above become instant state changes"
---

# Body text is not read
"""

EXPECTED_BODY = """\
:root {
  /* Colours */
  --color-paper: #FFFFFF;
  --color-ink: #15171C;

  /* Typography */
  --font-ui: Mukta, 'Noto Sans Devanagari', sans-serif;
  --font-hand: Kalam, cursive;
  --type-body-size: 16px;
  --type-body-line: 26px;
  --type-body-weight: 400;
  --type-amount-size: 40px;
  --type-amount-line: 44px;
  --type-amount-weight: 600;
  --type-amount-tracking: -0.01em;

  /* Radii */
  --radius-field: 2px;
  --radius-none: 0px;

  /* Spacing (base 4px) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;

  /* Motion (reduced motion turns these into instant state changes) */
  --motion-stamp-duration: 160ms;
  --motion-stamp-easing: cubic-bezier(.2,.9,.3,1.2);
  --motion-stamp-from: scale(1.18);
  --motion-stamp-to: scale(1);
  --motion-strike-duration: 220ms;
  --motion-strike-easing: ease-out;
}
"""


def write_design(tmp_path: Path, text: str = FRONT_MATTER) -> Path:
    design = tmp_path / "DESIGN.md"
    design.write_text(text, encoding="utf-8")
    return design


def test_generates_every_token_family_in_front_matter_order(tmp_path: Path) -> None:
    design = write_design(tmp_path)
    out = tmp_path / "css" / "tokens.css"

    result = run_script("build_tokens", "--design", design, "--out", out)

    assert result.returncode == 0, result.stderr
    assert f"build_tokens: wrote {out}" in result.stdout
    header = load_script("build_tokens").HEADER
    assert "Do not edit by hand" in header
    assert out.read_text(encoding="utf-8") == header + EXPECTED_BODY


def test_output_is_deterministic(tmp_path: Path) -> None:
    design = write_design(tmp_path)
    first, second = tmp_path / "a.css", tmp_path / "b.css"

    assert run_script("build_tokens", "--design", design, "--out", first).returncode == 0
    assert run_script("build_tokens", "--design", design, "--out", second).returncode == 0

    assert first.read_bytes() == second.read_bytes()
    assert b"\r\n" not in first.read_bytes()
    module = load_script("build_tokens")
    data = module.read_front_matter(design)
    assert module.build_css(data) == module.build_css(data) == first.read_text(encoding="utf-8")


def test_check_passes_when_output_is_current(tmp_path: Path) -> None:
    design = write_design(tmp_path)
    out = tmp_path / "tokens.css"
    assert run_script("build_tokens", "--design", design, "--out", out).returncode == 0

    result = run_script("build_tokens", "--design", design, "--out", out, "--check")

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"build_tokens: {out} is up to date" in result.stdout


def test_check_fails_when_output_is_stale_and_does_not_rewrite_it(tmp_path: Path) -> None:
    design = write_design(tmp_path)
    out = tmp_path / "tokens.css"
    assert run_script("build_tokens", "--design", design, "--out", out).returncode == 0
    write_design(tmp_path, FRONT_MATTER.replace('ink: "#15171C"', 'ink: "#111111"'))
    before = out.read_bytes()

    result = run_script("build_tokens", "--design", design, "--out", out, "--check")

    assert result.returncode == 1
    assert f"{out}:1: tokens: is out of date with DESIGN.md" in result.stdout
    assert "uv run python scripts/build_tokens.py" in result.stdout
    assert out.read_bytes() == before


def test_check_fails_when_output_was_edited_by_hand(tmp_path: Path) -> None:
    design = write_design(tmp_path)
    out = tmp_path / "tokens.css"
    assert run_script("build_tokens", "--design", design, "--out", out).returncode == 0
    out.write_text(out.read_text(encoding="utf-8") + "/* hand edit */\n", encoding="utf-8")

    result = run_script("build_tokens", "--design", design, "--out", out, "--check")

    assert result.returncode == 1
    assert "is out of date with DESIGN.md" in result.stdout


def test_check_fails_when_output_is_missing(tmp_path: Path) -> None:
    design = write_design(tmp_path)
    out = tmp_path / "tokens.css"

    result = run_script("build_tokens", "--design", design, "--out", out, "--check")

    assert result.returncode == 1
    assert f"{out}:1: tokens: is missing" in result.stdout
    assert not out.exists()


BAD_FRONT_MATTER = [
    pytest.param(
        "colors:\n  ink: '#000000'\n", "the first line must be '---'", id="no-front-matter"
    ),
    pytest.param("---\ncolors:\n  ink: '#000000'\n", "no closing '---' line", id="unclosed"),
    pytest.param("---\ncolors: [unclosed\n---\n", "not valid YAML", id="invalid-yaml"),
    pytest.param("---\n- a\n- b\n---\n", "front matter must be a mapping", id="list"),
    pytest.param(
        FRONT_MATTER.replace('"#15171C"', '"blue"'), "colors.ink: 'blue' is not a hex", id="named"
    ),
    pytest.param(
        FRONT_MATTER.replace("  ink:", "  Ink:"), "token name 'Ink' must be lowercase", id="case"
    ),
    pytest.param(
        FRONT_MATTER.replace("Kalam, cursive", "Kalam; color: red"),
        "typography.family-hand: value",
        id="semicolon-injection",
    ),
    pytest.param(
        FRONT_MATTER.replace("ease-out", "ease-out} body {"),
        "motion.strike.easing: value",
        id="brace-injection",
    ),
    pytest.param(
        FRONT_MATTER.replace('  family-hand: "Kalam, cursive"\n', ""),
        "typography.family-hand is missing",
        id="no-hand-family",
    ),
    pytest.param(
        FRONT_MATTER.replace("size: 16px, ", ""), "typography.body.size is missing", id="no-size"
    ),
    pytest.param(
        FRONT_MATTER.replace("scale: [4, 8, 12]", "scale: []"),
        "spacing.scale must be a non-empty list",
        id="empty-scale",
    ),
    pytest.param(
        FRONT_MATTER.replace("scale: [4, 8, 12]", "scale: [4, wide]"),
        "spacing.scale[1] must be a number",
        id="word-in-scale",
    ),
    pytest.param(
        FRONT_MATTER.replace(', easing: "ease-out"', ""),
        "motion.strike.easing is missing",
        id="no-easing",
    ),
    pytest.param(
        FRONT_MATTER.replace("rounded:\n  field: 2px\n  none: 0px\n", "rounded: 2px\n"),
        "'rounded' must be a mapping",
        id="rounded-scalar",
    ),
]


@pytest.mark.parametrize(("text", "message"), BAD_FRONT_MATTER)
def test_bad_front_matter_is_an_error_and_writes_nothing(
    tmp_path: Path, text: str, message: str
) -> None:
    design = write_design(tmp_path, text)
    out = tmp_path / "tokens.css"

    result = run_script("build_tokens", "--design", design, "--out", out)

    assert result.returncode == 2
    assert "build_tokens: error:" in result.stderr
    assert message in result.stderr
    assert not out.exists()


def test_missing_design_file_is_an_error(tmp_path: Path) -> None:
    result = run_script("build_tokens", "--design", tmp_path / "nope.md", "--check")

    assert result.returncode == 2
    assert "build_tokens: error: cannot read" in result.stderr
    assert "nope.md" in result.stderr


def test_committed_tokens_css_is_up_to_date_with_design_md() -> None:
    result = run_script("build_tokens", "--check")

    assert result.returncode == 0, result.stdout + result.stderr
    tokens = REPO_ROOT / "packages/munim_web/src/munim_web/static/css/tokens.css"
    assert f"build_tokens: {tokens} is up to date" in result.stdout
