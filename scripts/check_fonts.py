"""Check the self-hosted web fonts: files, licences, glyph coverage and OpenType features.

DESIGN.md section 3 sets Mukta for the interface and Kalam for corrections, both
self-hosted as WOFF2 subsets so the app works offline. With fontTools this script
confirms, in the fonts directory (``--fonts-dir``):

* files: Mukta 400, 500 and 600 and Kalam 400, each in the latin, latin-ext and
  devanagari subsets, named ``<family>-<subset>-<weight>-normal.woff2``;
* licences: ``LICENSES/Mukta-OFL.txt`` and ``LICENSES/Kalam-OFL.txt`` contain the
  SIL Open Font License text;
* coverage: for each family and weight, the union of the subsets' character maps
  covers a Devanagari sample of Munim's own words and a Latin sample with the
  rupee sign and the figures;
* features: Mukta's latin subset has ``tnum`` (tabular figures) in GSUB or GPOS and
  lining figures, either from an ``lnum`` feature or by default, which is accepted
  when the font has no ``onum`` feature (docs/PLAN_REVIEW.md D16).

Each check prints one line, ``<check>: ok: <detail>`` or ``<check>: FAIL: <detail>``,
then ``check_fonts: N checks, M problems`` (M is the number of failing checks).

Exit codes: 0 all checks pass, 1 a check failed, 2 the fonts directory is missing or
a font or licence file cannot be read.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FONTS_DIR = REPO_ROOT / "packages/munim_web/src/munim_web/static/fonts"

FAMILIES: dict[str, tuple[int, ...]] = {"Mukta": (400, 500, 600), "Kalam": (400,)}
SUBSETS = ("latin", "latin-ext", "devanagari")
LICENCE_DIR = "LICENSES"
LICENCE_MARK = "SIL OPEN FONT LICENSE"
SAMPLES = {
    # Munim, amount owed, evidence file, checked (the nukta letter is checked as
    # base letter plus U+093C, which is how NFC text and the shaper see it).
    "devanagari": "मुनीम बकाया रकम सबूत की फ़ाइल जाँचा गया",
    "latin": "Munim ₹0123456789,.-/",
}
FEATURE_FAMILY = "Mukta"
FEATURE_SUBSET = "latin"
LAYOUT_TABLES = ("GSUB", "GPOS")


class FontError(Exception):
    """A font or licence file exists but cannot be read."""


@dataclass(frozen=True)
class FontInfo:
    """What the checks need from one font file."""

    codepoints: frozenset[int]
    features: dict[str, frozenset[str]]  # layout table tag -> feature tags

    def tables_with(self, feature: str) -> list[str]:
        return [table for table in LAYOUT_TABLES if feature in self.features.get(table, ())]


@dataclass(frozen=True)
class Result:
    name: str
    passed: bool
    detail: str

    def format(self) -> str:
        return f"{self.name}: {'ok' if self.passed else 'FAIL'}: {self.detail}"


def font_file(family: str, subset: str, weight: int) -> str:
    return f"{family.lower()}-{subset}-{weight}-normal.woff2"


def required_chars(sample: str) -> list[str]:
    """The distinct non-space characters of ``sample`` in NFC, in order."""
    chars: list[str] = []
    for char in unicodedata.normalize("NFC", sample):
        if not char.isspace() and char not in chars:
            chars.append(char)
    return chars


def _feature_tags(font: TTFont, table_tag: str) -> frozenset[str]:
    if table_tag not in font:
        return frozenset()
    feature_list = getattr(font[table_tag].table, "FeatureList", None)
    records = getattr(feature_list, "FeatureRecord", None) or []
    return frozenset(str(record.FeatureTag) for record in records)


def read_font(path: Path) -> FontInfo:
    """Read the character map and layout feature tags of one font file."""
    try:
        with TTFont(path) as font:
            cmap = font.getBestCmap() or {}
            features = {tag: _feature_tags(font, tag) for tag in LAYOUT_TABLES}
    except Exception as exc:  # fontTools raises many exception types for damaged files
        raise FontError(f"cannot read {path}: {exc}") from exc
    return FontInfo(frozenset(int(code) for code in cmap), features)


class FontDir:
    """The fonts directory; each font file is read at most once."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.errors: list[str] = []
        self._fonts: dict[str, FontInfo | None] = {}

    def exists(self, name: str) -> bool:
        return (self.directory / name).is_file()

    def font(self, name: str) -> FontInfo | None:
        """The parsed font, or None when it is missing or unreadable (recorded in errors)."""
        if name not in self._fonts:
            info: FontInfo | None = None
            if self.exists(name):
                try:
                    info = read_font(self.directory / name)
                except FontError as exc:
                    self.errors.append(str(exc))
            self._fonts[name] = info
        return self._fonts[name]


def check_files(fonts: FontDir, family: str, weights: tuple[int, ...]) -> Result:
    names = [font_file(family, subset, weight) for weight in weights for subset in SUBSETS]
    missing = [name for name in names if not fonts.exists(name)]
    if missing:
        return Result(f"files {family}", False, f"missing {', '.join(missing)}")
    return Result(f"files {family}", True, f"{len(names)} of {len(names)} present")


def check_licence(fonts: FontDir, family: str) -> Result:
    rel = f"{LICENCE_DIR}/{family}-OFL.txt"
    name = f"licence {family}"
    path = fonts.directory / rel
    if not path.is_file():
        return Result(name, False, f"{rel} is missing")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        fonts.errors.append(f"cannot read {path}: {exc.strerror or exc}")
        return Result(name, False, f"{rel} cannot be read")
    if LICENCE_MARK.lower() not in text.lower():
        return Result(name, False, f"{rel} does not contain the SIL Open Font License text")
    return Result(name, True, f"{rel} contains the SIL Open Font License text")


def check_coverage(fonts: FontDir, family: str, weight: int, script: str) -> Result:
    name = f"{script} {family} {weight}"
    infos = [fonts.font(font_file(family, subset, weight)) for subset in SUBSETS]
    covered: set[int] = set()
    for info in infos:
        if info is not None:
            covered |= info.codepoints
    chars = required_chars(SAMPLES[script])
    if not any(info is not None for info in infos):
        return Result(name, False, "no readable font file for this weight")
    missing = [char for char in chars if ord(char) not in covered]
    if missing:
        codes = ", ".join(f"U+{ord(char):04X}" for char in missing)
        return Result(
            name, False, f"{len(missing)} of {len(chars)} sample characters missing: {codes}"
        )
    return Result(
        name, True, f"all {len(chars)} sample characters covered across {len(SUBSETS)} subsets"
    )


def check_tabular(fonts: FontDir, weight: int) -> Result:
    file = font_file(FEATURE_FAMILY, FEATURE_SUBSET, weight)
    name = f"tnum {FEATURE_FAMILY} {FEATURE_SUBSET} {weight}"
    info = fonts.font(file)
    if info is None:
        return Result(name, False, f"{file} is missing or unreadable")
    tables = info.tables_with("tnum")
    if not tables:
        return Result(name, False, "no tnum feature in GSUB or GPOS; amounts need tabular figures")
    return Result(name, True, f"tnum feature in {' and '.join(tables)}")


def check_lining(fonts: FontDir, weight: int) -> Result:
    file = font_file(FEATURE_FAMILY, FEATURE_SUBSET, weight)
    name = f"lining {FEATURE_FAMILY} {FEATURE_SUBSET} {weight}"
    info = fonts.font(file)
    if info is None:
        return Result(name, False, f"{file} is missing or unreadable")
    lnum = info.tables_with("lnum")
    if lnum:
        return Result(name, True, f"lnum feature in {' and '.join(lnum)}")
    onum = info.tables_with("onum")
    if onum:
        return Result(
            name,
            False,
            f"onum feature in {' and '.join(onum)} and no lnum feature; "
            "figures may be old-style by default",
        )
    return Result(name, True, "no lnum and no onum feature: figures are lining by default")


def run_checks(fonts: FontDir) -> list[Result]:
    """Every check, in print order: files, licences, coverage, then features."""
    results = [check_files(fonts, family, weights) for family, weights in FAMILIES.items()]
    results += [check_licence(fonts, family) for family in FAMILIES]
    results += [
        check_coverage(fonts, family, weight, script)
        for script in SAMPLES
        for family, weights in FAMILIES.items()
        for weight in weights
    ]
    feature_weights = FAMILIES[FEATURE_FAMILY]
    results += [check_tabular(fonts, weight) for weight in feature_weights]
    results += [check_lining(fonts, weight) for weight in feature_weights]
    return results


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fonts-dir",
        type=Path,
        default=DEFAULT_FONTS_DIR,
        help="directory with the WOFF2 files and LICENSES/ (default: the web package fonts)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    directory: Path = args.fonts_dir
    if not directory.is_dir():
        print(f"check_fonts: error: fonts directory not found: {directory}", file=sys.stderr)
        return 2

    fonts = FontDir(directory)
    results = run_checks(fonts)
    for result in results:
        print(result.format())
    problems = sum(not result.passed for result in results)
    print(f"check_fonts: {len(results)} checks, {problems} problems")
    for error in fonts.errors:
        print(f"check_fonts: error: {error}", file=sys.stderr)
    if fonts.errors:
        return 2
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
