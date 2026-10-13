"""Check the colour pairs declared in DESIGN.md against WCAG 2.x contrast.

Reads the colour tokens from the YAML front matter of DESIGN.md and the pairs
from the Notes column of the section 2 table ("Colour palette and roles"):

* ``<ratio>:1 on <token>`` and ``<ratio>:1 on its own wash``: this token as
  text (or edge) on that background, with a claimed ratio;
* ``Text on it is `ink` `` (optionally followed by ``(<ratio>:1)``) and
  ``Text on it must be `a`, `b` or `c` ``: those tokens as text on this one;
* ``White text on it`` (optionally followed by ``<ratio>:1``): ``sheet`` on it.

A pair fails when its computed ratio is below the threshold (3.0 for
``hairline-strong``, a UI edge; 4.5 for text) or when a claimed ratio in the
document differs from the computed one by more than 0.1.

Exit codes: 0 all pairs pass, 1 a pair or the table failed, 2 bad input (unreadable,
not UTF-8 or not in the expected shape).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DESIGN = REPO_ROOT / "DESIGN.md"

TEXT_THRESHOLD = 4.5
EDGE_THRESHOLD = 3.0
EDGE_TOKENS = frozenset({"hairline-strong"})
CLAIM_TOLERANCE = 0.1

SECTION_RE = re.compile(r"^##\s+2\.\s")
HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
COLOUR_NAME = r"`?([a-z][a-z0-9-]*)`?"
RATIO = r"(\d+(?:\.\d+)?):1"
RATIO_ON_RE = re.compile(RATIO + r" on (its own wash|" + COLOUR_NAME + r")")
TEXT_IS_RE = re.compile(r"Text on it is `([a-z][a-z0-9-]*)`(?:\s*\(" + RATIO + r"\))?")
TEXT_MUST_RE = re.compile(r"Text on it must be ((?:`[a-z][a-z0-9-]*`(?:\s*,\s*|\s+or\s+)?)+)")
WHITE_RE = re.compile(r"White text on it(?:\s+" + RATIO + r")?")
BACKTICK_TOKEN_RE = re.compile(r"`([a-z][a-z0-9-]*)`")


class DesignError(Exception):
    """DESIGN.md is missing, unreadable or does not have the expected shape."""


@dataclass
class Pair:
    fg: str
    bg: str
    line: int
    claimed: str | None = None

    @property
    def threshold(self) -> float:
        return EDGE_THRESHOLD if self.fg in EDGE_TOKENS else TEXT_THRESHOLD


@dataclass(frozen=True)
class Row:
    token: str
    hex: str
    notes: str
    line: int


def relative_luminance(hex_colour: str) -> float:
    """WCAG 2.x relative luminance of an sRGB colour given as #rgb or #rrggbb."""
    if not HEX_RE.match(hex_colour):
        raise ValueError(f"not an opaque hex colour: {hex_colour!r}")
    digits = hex_colour[1:]
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    channels = []
    for i in (0, 2, 4):
        c = int(digits[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """WCAG 2.x contrast ratio (L1 + 0.05) / (L2 + 0.05), lighter over darker."""
    a, b = relative_luminance(first), relative_luminance(second)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def read_design(design: Path) -> tuple[dict[str, Any], list[str]]:
    """Return (front matter, all lines) of DESIGN.md."""
    try:
        text = design.read_text(encoding="utf-8")
    except OSError as exc:
        raise DesignError(f"cannot read {design}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise DesignError(
            f"cannot read {design}: not valid UTF-8 (byte {exc.start}: {exc.reason})"
        ) from exc
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise DesignError(f"{design}: the first line must be '---' (YAML front matter)")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise DesignError(f"{design}: front matter has no closing '---' line") from None
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise DesignError(f"{design}: front matter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DesignError(f"{design}: front matter must be a mapping")
    return data, lines


def read_colours(front_matter: dict[str, Any]) -> dict[str, str]:
    colours = front_matter.get("colors")
    if not isinstance(colours, dict) or not colours:
        raise DesignError("front matter: 'colors' must be a non-empty mapping")
    result: dict[str, str] = {}
    for name, value in colours.items():
        if not isinstance(value, str) or not HEX_RE.match(value):
            raise DesignError(f"colors.{name}: {value!r} is not an opaque hex colour")
        result[str(name)] = value
    return result


def read_table(lines: list[str]) -> list[Row]:
    """Parse the section 2 markdown table: Token | Hex | Role | Notes."""
    start = next((i for i, line in enumerate(lines) if SECTION_RE.match(line)), None)
    if start is None:
        raise DesignError("section '## 2.' (colour palette and roles) not found")
    rows: list[Row] = []
    in_table = False
    for index in range(start + 1, len(lines)):
        line = lines[index].strip()
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            if in_table:
                break
            continue
        in_table = True
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4:
            raise DesignError(f"DESIGN.md:{index + 1}: table row has fewer than 4 columns")
        token, hex_value = cells[0].strip("`"), cells[1].strip("`")
        if token.lower() == "token" or set(token) <= {"-", ":", " "}:
            continue  # header or separator row
        rows.append(Row(token=token, hex=hex_value, notes=cells[3], line=index + 1))
    if not rows:
        raise DesignError("section 2 has no colour table")
    return rows


def own_wash(token: str, colours: dict[str, str]) -> str | None:
    """The wash of a status colour: tick -> tick-wash, red-pen -> red-wash."""
    for candidate in (f"{token}-wash", f"{token.split('-')[0]}-wash"):
        if candidate in colours:
            return candidate
    return None


def pairs_from_notes(row: Row, colours: dict[str, str]) -> tuple[list[Pair], list[str]]:
    """Derive (pairs, problems) from one row's Notes cell."""
    pairs: list[Pair] = []
    problems: list[str] = []
    for match in RATIO_ON_RE.finditer(row.notes):
        claimed, target = match.group(1), match.group(2)
        if target == "its own wash":
            bg = own_wash(row.token, colours)
            if bg is None:
                problems.append(f"'{row.token}' has no '-wash' token for 'on its own wash'")
                continue
        else:
            bg = match.group(3)
        pairs.append(Pair(fg=row.token, bg=bg, line=row.line, claimed=claimed))
    for match in TEXT_IS_RE.finditer(row.notes):
        pairs.append(Pair(fg=match.group(1), bg=row.token, line=row.line, claimed=match.group(2)))
    for match in TEXT_MUST_RE.finditer(row.notes):
        for fg in BACKTICK_TOKEN_RE.findall(match.group(1)):
            pairs.append(Pair(fg=fg, bg=row.token, line=row.line))
    for match in WHITE_RE.finditer(row.notes):
        pairs.append(Pair(fg="sheet", bg=row.token, line=row.line, claimed=match.group(1)))
    return pairs, problems


def collect_pairs(
    rows: list[Row], colours: dict[str, str], source: str = "DESIGN.md"
) -> tuple[list[Pair], list[str]]:
    """All pairs in table order, de-duplicated (a claimed ratio wins), plus table problems."""
    seen: dict[tuple[str, str], Pair] = {}
    problems: list[str] = []
    for row in rows:
        where = f"{source}:{row.line}: contrast:"
        if row.token not in colours:
            problems.append(f"{where} table token '{row.token}' is not in the front matter colors")
            continue
        if row.hex.upper() != colours[row.token].upper():
            problems.append(
                f"{where} table hex {row.hex} for '{row.token}' "
                f"differs from the front matter ({colours[row.token]})"
            )
        row_pairs, row_problems = pairs_from_notes(row, colours)
        problems.extend(f"{where} {problem}" for problem in row_problems)
        for pair in row_pairs:
            unknown = [name for name in (pair.fg, pair.bg) if name not in colours]
            if unknown:
                problems.extend(f"{where} unknown token '{name}'" for name in unknown)
                continue
            key = (pair.fg, pair.bg)
            if key not in seen or (seen[key].claimed is None and pair.claimed is not None):
                seen[key] = pair
    return list(seen.values()), problems


def check_pair(pair: Pair, colours: dict[str, str], source: str = "DESIGN.md") -> tuple[str, bool]:
    """Return (report line, passed) for one pair."""
    ratio = contrast_ratio(colours[pair.fg], colours[pair.bg])
    reasons: list[str] = []
    if ratio < pair.threshold:
        reasons.append(f"below the {pair.threshold:.1f}:1 minimum")
    if pair.claimed is not None and abs(ratio - float(pair.claimed)) > CLAIM_TOLERANCE:
        reasons.append(f"claimed ratio is wrong ({source} says {pair.claimed}:1)")
    claimed = pair.claimed if pair.claimed is not None else "none"
    status = "ok" if not reasons else f"FAIL: {'; '.join(reasons)} ({source}:{pair.line})"
    head = f"{pair.fg} on {pair.bg}: {ratio:.2f}"
    return f"{head} (threshold {pair.threshold:.1f}, claimed {claimed}) {status}", not reasons


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN, help="path to DESIGN.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        front_matter, lines = read_design(args.design)
        colours = read_colours(front_matter)
        rows = read_table(lines)
    except DesignError as exc:
        print(f"check_contrast: error: {exc}", file=sys.stderr)
        return 2

    source = args.design.name
    pairs, problems = collect_pairs(rows, colours, source)
    failed = len(problems)
    for problem in problems:
        print(problem)
    for pair in pairs:
        report, passed = check_pair(pair, colours, source)
        print(report)
        failed += 0 if passed else 1
    if not pairs:
        print(f"{source}:1: contrast: no colour pairs found in the section 2 notes")
        failed += 1
    print(f"check_contrast: {len(pairs)} pairs checked, {failed} problems")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
