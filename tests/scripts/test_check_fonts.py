"""Tests for scripts/check_fonts.py (font files, licences, coverage, tnum and lining).

The fonts here are tiny synthetic WOFF2 files built with fontTools' FontBuilder:
empty glyphs, a character map and, where a test needs it, GSUB or GPOS features.
They are written to ``tmp_path`` only and never committed.
"""

from __future__ import annotations

import shutil
import unicodedata
from collections.abc import Iterable
from pathlib import Path

import pytest
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from .conftest import load_script, run_script

pytestmark = pytest.mark.unit

DEVANAGARI = unicodedata.normalize("NFC", "मुनीम बकाया रकम सबूत की फ़ाइल जाँचा गया")
LATIN = "Munim 0123456789,.-/"
RUPEE = "₹"
OFL_TEXT = (
    "Synthetic test licence file.\n"
    "This Font Software is licensed under the SIL Open Font License, Version 1.1.\n"
)

TNUM = "feature tnum { sub uni0030 by uni0030.alt; } tnum;"
TNUM_GPOS = "feature tnum { pos uni0030 <0 0 100 0>; } tnum;"
ONUM = "feature onum { sub uni0030 by uni0030.alt; } onum;"
LNUM = "feature lnum { sub uni0030.alt by uni0030; } lnum;"

# Like Fontsource: Latin letters and figures in "latin", the rupee sign only in
# "latin-ext", Devanagari in "devanagari". Coverage is the union of the three.
SUBSET_CHARS = {"latin": LATIN, "latin-ext": RUPEE, "devanagari": DEVANAGARI}
FAMILIES = {"mukta": (400, 500, 600), "kalam": (400,)}


def build_font(path: Path, chars: Iterable[str], features: str = "") -> None:
    """Write a WOFF2 font mapping ``chars`` (spaces ignored) to empty glyphs."""
    codes = sorted({ord(char) for char in chars if not char.isspace()} | {0x30})
    names = {code: f"uni{code:04X}" for code in codes}
    order = [".notdef", *names.values(), "uni0030.alt"]
    builder = FontBuilder(unitsPerEm=1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(names)
    builder.setupGlyf({name: TTGlyphPen(None).glyph() for name in order})
    builder.setupHorizontalMetrics(dict.fromkeys(order, (500, 0)))
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Synthetic Test", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    if features:
        addOpenTypeFeaturesFromString(builder.font, features)
    builder.font.flavor = "woff2"
    builder.save(str(path))


def name(family: str, subset: str, weight: int) -> str:
    return f"{family}-{subset}-{weight}-normal.woff2"


@pytest.fixture(scope="module")
def good_fonts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A complete, passing fonts directory, built once per module."""
    directory = tmp_path_factory.mktemp("fonts")
    for family, weights in FAMILIES.items():
        for weight in weights:
            for subset, chars in SUBSET_CHARS.items():
                features = TNUM if (family, subset) == ("mukta", "latin") else ""
                build_font(directory / name(family, subset, weight), chars, features)
    (directory / "LICENSES").mkdir()
    for licence in ("Mukta-OFL.txt", "Kalam-OFL.txt"):
        (directory / "LICENSES" / licence).write_text(OFL_TEXT, encoding="utf-8")
    return directory


@pytest.fixture
def fonts(good_fonts: Path, tmp_path: Path) -> Path:
    """A private copy of the passing fonts directory that a test may break."""
    return Path(shutil.copytree(good_fonts, tmp_path / "fonts"))


def check(directory: Path) -> tuple[int, list[str], str]:
    result = run_script("check_fonts", "--fonts-dir", directory)
    return result.returncode, result.stdout.splitlines(), result.stderr


# ------------------------------------------------------------------ passing
def test_complete_fonts_pass_every_check(fonts: Path) -> None:
    code, lines, err = check(fonts)

    assert code == 0, lines
    assert err == ""
    assert lines[-1] == "check_fonts: 18 checks, 0 problems"
    assert "files Mukta: ok: 9 of 9 present" in lines
    assert "files Kalam: ok: 3 of 3 present" in lines
    assert "licence Mukta: ok: LICENSES/Mukta-OFL.txt contains the SIL Open Font License text" in (
        lines
    )
    for label in ("devanagari Mukta 400", "devanagari Mukta 600", "devanagari Kalam 400"):
        assert f"{label}: ok: all 20 sample characters covered across 3 subsets" in lines
    # The rupee sign is only in latin-ext: coverage is the union of the subsets.
    assert "latin Mukta 500: ok: all 20 sample characters covered across 3 subsets" in lines
    assert "tnum Mukta latin 400: ok: tnum feature in GSUB" in lines
    assert (
        "lining Mukta latin 600: ok: no lnum and no onum feature: figures are lining by default"
    ) in lines
    assert all(": ok: " in line for line in lines[:-1])


# ------------------------------------------------------------------ files and licences
def test_missing_font_file_fails(fonts: Path) -> None:
    (fonts / name("mukta", "latin-ext", 500)).unlink()

    code, lines, _ = check(fonts)

    assert code == 1
    assert "files Mukta: FAIL: missing mukta-latin-ext-500-normal.woff2" in lines
    assert "latin Mukta 500: FAIL: 1 of 20 sample characters missing: U+20B9" in lines
    assert "latin Mukta 400: ok: all 20 sample characters covered across 3 subsets" in lines
    assert lines[-1] == "check_fonts: 18 checks, 2 problems"


def test_missing_latin_file_fails_the_feature_checks(fonts: Path) -> None:
    (fonts / name("mukta", "latin", 400)).unlink()

    code, lines, _ = check(fonts)

    assert code == 1
    assert "tnum Mukta latin 400: FAIL: mukta-latin-400-normal.woff2 is missing or unreadable" in (
        lines
    )
    assert (
        "lining Mukta latin 400: FAIL: mukta-latin-400-normal.woff2 is missing or unreadable"
        in (lines)
    )


def test_missing_licence_fails(fonts: Path) -> None:
    (fonts / "LICENSES" / "Kalam-OFL.txt").unlink()

    code, lines, _ = check(fonts)

    assert code == 1
    assert "licence Kalam: FAIL: LICENSES/Kalam-OFL.txt is missing" in lines
    assert lines[-1] == "check_fonts: 18 checks, 1 problems"


def test_licence_without_ofl_text_fails(fonts: Path) -> None:
    (fonts / "LICENSES" / "Mukta-OFL.txt").write_text("All rights reserved.\n", encoding="utf-8")

    code, lines, _ = check(fonts)

    assert code == 1
    assert (
        "licence Mukta: FAIL: LICENSES/Mukta-OFL.txt does not contain the SIL Open Font License "
        "text"
    ) in lines


def test_licence_text_match_ignores_case(fonts: Path) -> None:
    (fonts / "LICENSES" / "Mukta-OFL.txt").write_text(
        "SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007\n", encoding="utf-8"
    )

    code, lines, _ = check(fonts)

    assert code == 0, lines
    assert "licence Mukta: ok: LICENSES/Mukta-OFL.txt contains the SIL Open Font License text" in (
        lines
    )


# ------------------------------------------------------------------ coverage
def test_devanagari_gap_in_one_weight_fails_only_that_weight(fonts: Path) -> None:
    build_font(fonts / name("mukta", "devanagari", 600), DEVANAGARI.replace("म", ""))

    code, lines, _ = check(fonts)

    assert code == 1
    assert "devanagari Mukta 600: FAIL: 1 of 20 sample characters missing: U+092E" in lines
    assert "devanagari Mukta 500: ok: all 20 sample characters covered across 3 subsets" in lines


def test_nukta_letter_needs_the_combining_nukta(fonts: Path) -> None:
    build_font(fonts / name("kalam", "devanagari", 400), DEVANAGARI.replace("़", ""))

    code, lines, _ = check(fonts)

    assert code == 1
    assert "devanagari Kalam 400: FAIL: 1 of 20 sample characters missing: U+093C" in lines


def test_latin_gap_fails(fonts: Path) -> None:
    build_font(fonts / name("kalam", "latin", 400), LATIN.replace("5", ""))

    code, lines, _ = check(fonts)

    assert code == 1
    assert "latin Kalam 400: FAIL: 1 of 20 sample characters missing: U+0035" in lines


def test_required_chars_normalise_and_drop_spaces_and_repeats() -> None:
    module = load_script("check_fonts")

    assert module.required_chars("फ़ फ़क") == ["फ", "़", "क"]
    assert module.required_chars("Munim ₹1,1") == ["M", "u", "n", "i", "m", "₹", "1", ","]


# ------------------------------------------------------------------ OpenType features
def test_missing_tnum_fails(fonts: Path) -> None:
    build_font(fonts / name("mukta", "latin", 400), LATIN)

    code, lines, _ = check(fonts)

    assert code == 1
    assert (
        "tnum Mukta latin 400: FAIL: no tnum feature in GSUB or GPOS; amounts need tabular figures"
    ) in lines
    assert "tnum Mukta latin 500: ok: tnum feature in GSUB" in lines
    assert lines[-1] == "check_fonts: 18 checks, 1 problems"


def test_tnum_in_gpos_passes(fonts: Path) -> None:
    build_font(fonts / name("mukta", "latin", 500), LATIN, TNUM_GPOS)

    code, lines, _ = check(fonts)

    assert code == 0, lines
    assert "tnum Mukta latin 500: ok: tnum feature in GPOS" in lines


def test_onum_without_lnum_fails_lining(fonts: Path) -> None:
    build_font(fonts / name("mukta", "latin", 600), LATIN, f"{TNUM}\n{ONUM}")

    code, lines, _ = check(fonts)

    assert code == 1
    assert (
        "lining Mukta latin 600: FAIL: onum feature in GSUB and no lnum feature; "
        "figures may be old-style by default"
    ) in lines
    assert "tnum Mukta latin 600: ok: tnum feature in GSUB" in lines


def test_lnum_feature_passes_lining_even_with_onum(fonts: Path) -> None:
    build_font(fonts / name("mukta", "latin", 600), LATIN, f"{TNUM}\n{ONUM}\n{LNUM}")

    code, lines, _ = check(fonts)

    assert code == 0, lines
    assert "lining Mukta latin 600: ok: lnum feature in GSUB" in lines


# ------------------------------------------------------------------ own errors
def test_unreadable_font_is_an_error(fonts: Path) -> None:
    (fonts / name("mukta", "latin", 400)).write_bytes(b"not a font, synthetic test bytes")

    code, lines, err = check(fonts)

    assert code == 2
    assert "check_fonts: error: cannot read" in err
    assert "mukta-latin-400-normal.woff2" in err
    assert lines[-1].startswith("check_fonts: 18 checks,")


def test_missing_fonts_directory_is_an_error(tmp_path: Path) -> None:
    code, lines, err = check(tmp_path / "nope")

    assert code == 2
    assert lines == []
    assert f"check_fonts: error: fonts directory not found: {tmp_path / 'nope'}" in err


# ------------------------------------------------------------------ the real fonts
def test_committed_fonts_pass() -> None:
    result = run_script("check_fonts")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines[-1] == "check_fonts: 18 checks, 0 problems"
    # docs/PLAN_REVIEW.md D16: Mukta has tnum, and lining figures by default.
    assert "tnum Mukta latin 400: ok: tnum feature in GSUB" in lines
    assert (
        "lining Mukta latin 400: ok: no lnum and no onum feature: figures are lining by default"
    ) in lines
    assert "devanagari Mukta 400: ok: all 20 sample characters covered across 3 subsets" in lines
