"""Generate tokens.css from the YAML front matter of DESIGN.md.

DESIGN.md is the single source of truth for colours, type, radii, spacing and
motion. This script turns its front matter into CSS custom properties so that no
stylesheet ever carries a raw value. Run it after any change to DESIGN.md;
``--check`` fails when the committed tokens.css has drifted.

Exit codes: 0 written or up to date, 1 out of date (``--check``), 2 bad input.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DESIGN = REPO_ROOT / "DESIGN.md"
DEFAULT_OUT = REPO_ROOT / "packages/munim_web/src/munim_web/static/css/tokens.css"

HEADER = (
    "/* Generated from DESIGN.md by scripts/build_tokens.py. Do not edit by hand:\n"
    "   change the front matter of DESIGN.md, then run\n"
    "   `uv run python scripts/build_tokens.py`. */\n"
)

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
UNIT_RE = re.compile(r"^-?\d*\.?\d+([a-z%]*)$")
TYPE_FIELDS = ("size", "line", "weight", "tracking")
MOTION_FIELDS = ("duration", "easing", "from", "to")
FAMILY_KEYS = (("family-ui", "--font-ui"), ("family-hand", "--font-hand"))
FAMILY_NAMES = frozenset(key for key, _ in FAMILY_KEYS)


class DesignError(Exception):
    """DESIGN.md is missing, unreadable or does not have the expected shape."""


def read_front_matter(design: Path) -> dict[str, Any]:
    """Return the parsed YAML between the first two ``---`` lines of ``design``."""
    try:
        text = design.read_text(encoding="utf-8")
    except OSError as exc:
        raise DesignError(f"cannot read {design}: {exc.strerror or exc}") from exc
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
    return data


def _css_value(value: object, where: str) -> str:
    """Render a scalar as a CSS value, refusing anything that could break out of it."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise DesignError(f"{where}: expected a string or number, got {type(value).__name__}")
    text = str(value).strip()
    if not text or any(ch in text for ch in ";{}\n\\<>"):
        raise DesignError(f"{where}: value {text!r} is empty or contains a forbidden character")
    return text


def _name(name: object, where: str) -> str:
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise DesignError(f"{where}: token name {name!r} must be lowercase letters, digits, '-'")
    return name


def _section(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise DesignError(f"front matter: '{key}' must be a mapping")
    return value


def build_css(data: Mapping[str, Any]) -> str:
    """Build the full tokens.css text from parsed front matter (deterministic)."""
    out: list[str] = [HEADER, ":root {\n"]

    out.append("  /* Colours */\n")
    for raw_name, raw_hex in _section(data, "colors").items():
        name = _name(raw_name, "colors")
        if not isinstance(raw_hex, str) or not HEX_RE.match(raw_hex):
            raise DesignError(f"colors.{name}: {raw_hex!r} is not a hex colour")
        out.append(f"  --color-{name}: {raw_hex};\n")

    typography = _section(data, "typography")
    out.append("\n  /* Typography */\n")
    for key, prop in FAMILY_KEYS:
        if key not in typography:
            raise DesignError(f"typography.{key} is missing")
        out.append(f"  {prop}: {_css_value(typography[key], f'typography.{key}')};\n")
    for raw_style, spec in typography.items():
        if raw_style in FAMILY_NAMES:
            continue
        style = _name(raw_style, "typography")
        if not isinstance(spec, Mapping):
            raise DesignError(f"typography.{style} must be a mapping")
        for field in TYPE_FIELDS:
            if field in spec:
                value = _css_value(spec[field], f"typography.{style}.{field}")
                out.append(f"  --type-{style}-{field}: {value};\n")
            elif field != "tracking":
                raise DesignError(f"typography.{style}.{field} is missing")

    out.append("\n  /* Radii */\n")
    for raw_name, value in _section(data, "rounded").items():
        name = _name(raw_name, "rounded")
        out.append(f"  --radius-{name}: {_css_value(value, f'rounded.{name}')};\n")

    spacing = _section(data, "spacing")
    base = _css_value(spacing.get("base", "4px"), "spacing.base")
    unit_match = UNIT_RE.match(base)
    unit = unit_match.group(1) if unit_match and unit_match.group(1) else "px"
    scale = spacing.get("scale")
    if not isinstance(scale, list) or not scale:
        raise DesignError("spacing.scale must be a non-empty list")
    out.append(f"\n  /* Spacing (base {base}) */\n")
    for index, step in enumerate(scale, start=1):
        if isinstance(step, bool) or not isinstance(step, int | float):
            raise DesignError(f"spacing.scale[{index - 1}] must be a number")
        out.append(f"  --space-{index}: {step}{unit};\n")

    out.append("\n  /* Motion (reduced motion turns these into instant state changes) */\n")
    for raw_name, spec in _section(data, "motion").items():
        if not isinstance(spec, Mapping):
            continue  # descriptive entries such as reduced-motion carry no values
        name = _name(raw_name, "motion")
        for field in ("duration", "easing"):
            if field not in spec:
                raise DesignError(f"motion.{name}.{field} is missing")
        for field in MOTION_FIELDS:
            if field in spec:
                value = _css_value(spec[field], f"motion.{name}.{field}")
                out.append(f"  --motion-{name}-{field}: {value};\n")

    out.append("}\n")
    return "".join(out)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN, help="path to DESIGN.md")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="tokens.css to write")
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the existing output differs from what would be generated",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        css = build_css(read_front_matter(args.design))
    except DesignError as exc:
        print(f"build_tokens: error: {exc}", file=sys.stderr)
        return 2

    out: Path = args.out
    if args.check:
        try:
            current = out.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = None
        except OSError as exc:
            print(f"build_tokens: error: cannot read {out}: {exc}", file=sys.stderr)
            return 2
        if current != css:
            state = "is missing" if current is None else "is out of date with DESIGN.md"
            print(f"{out}:1: tokens: {state}; run `uv run python scripts/build_tokens.py`")
            return 1
        print(f"build_tokens: {out} is up to date")
        return 0

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(css, encoding="utf-8", newline="\n")
    except OSError as exc:
        print(f"build_tokens: error: cannot write {out}: {exc}", file=sys.stderr)
        return 2
    print(f"build_tokens: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
