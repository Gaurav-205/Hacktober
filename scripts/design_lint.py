"""Design lint: enforce DESIGN.md section 12 on templates, CSS, JS and i18n strings.

Rules (numbers as in DESIGN.md section 12; every message cites section 7):

1. Raw hex colours outside tokens.css (CSS declaration values; colour and style
   attributes in templates; 6- or 8-digit hex in JS string literals).
2. Shadows, blurs and gradients: box-shadow (except a focus ring marked
   ``/* focus-ring */`` on the same line, or ``none``), text-shadow,
   backdrop-filter, drop-shadow()/blur() filters, and every *-gradient().
3. border-radius above 6px, any percentage, and 9999px pills.
4. text-transform: uppercase outside a ``.stamp`` selector; letter-spacing above
   0.02em.
5. Emoji, arrows, the em dash and the middle dot used as a separator, in i18n
   values, template text and CSS strings.
6. Font families other than the declared ones.
7. Devanagari in a template line that has no ``lang="hi"``.
8. IntersectionObserver, scroll-driven animations, and @keyframes that animate
   opacity together with translate (fade-and-slide entrances).
9. Banned words in i18n values, template text and CSS strings.

With no arguments the default roots of the web package (templates, static/css,
static/js and i18n under ``--root``, the repository by default) are scanned, and a
missing default root is an error. With arguments, the given files and directories
are linted; files with other extensions and anything under ``static/js/vendor/``
are skipped. Paths print relative to ``--root`` when they are inside it.

Exit codes: 0 clean, 1 findings, 2 bad arguments, a missing scan root or
unreadable input.
"""

from __future__ import annotations

import argparse
import bisect
import html
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PACKAGE = Path("packages/munim_web/src/munim_web")
SCAN_DIRS = ("templates", "static/css", "static/js", "i18n")


def default_roots(repo_root: Path) -> tuple[Path, ...]:
    """The scan roots of the web package inside the repository at ``repo_root``."""
    return tuple(repo_root / WEB_PACKAGE / name for name in SCAN_DIRS)


WEB_ROOT = REPO_ROOT / WEB_PACKAGE
DEFAULT_ROOTS = default_roots(REPO_ROOT)
KINDS = {".html": "template", ".j2": "template", ".css": "css", ".js": "js", ".json": "json"}
VENDOR_PARTS = ("static", "js", "vendor")
TOKENS_FILE = "tokens.css"
SECTION = "DESIGN.md section 7"

MAX_RADIUS_PX = Fraction(6)
PILL_RADIUS_PX = Fraction(9999)
MAX_TRACKING_EM = Fraction(2, 100)
ROOT_PX = Fraction(16)

ALLOWED_FAMILIES = frozenset(
    {
        "mukta",
        "kalam",
        "ibm plex sans",
        "noto sans devanagari",
        "system-ui",
        "sans-serif",
        "cursive",
        "inherit",
        "var(--font-ui)",
        "var(--font-hand)",
    }
)
COLOUR_ATTRS = frozenset(
    {"fill", "stroke", "color", "stop-color", "bgcolor", "flood-color", "lighting-color"}
)
VISIBLE_ATTRS = frozenset(
    {
        "alt",
        "title",
        "placeholder",
        "label",
        "value",
        "content",
        "summary",
        "aria-label",
        "aria-description",
        "aria-roledescription",
        "aria-valuetext",
        "aria-placeholder",
    }
)

# ------------------------------------------------------------------ patterns
HEX_RE = re.compile(
    r"(?<![\w&#])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![\w-])"
)
JS_HEX_RE = re.compile(r"(?<![\w&#])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6})(?![\w-])")
CSS_STRING = r'"(?:[^"\\\n]|\\.)*"?|\'(?:[^\'\\\n]|\\.)*\'?'
CSS_STRING_RE = re.compile(CSS_STRING, re.S)
CSS_COMMENT_OR_STRING_RE = re.compile(CSS_STRING + r"|/\*.*?(?:\*/|\Z)", re.S)
CSS_STRUCT_RE = re.compile(CSS_STRING + r"|[{};()]", re.S)
JS_TOKEN_RE = re.compile(
    CSS_STRING + r"|`(?:[^`\\]|\\.)*`?|/\*.*?(?:\*/|\Z)|//[^\n]*",
    re.S,
)
URL_RE = re.compile(r"url\([^)]*\)?", re.I)
PROP_RE = re.compile(r"-{0,2}[A-Za-z_][\w-]*")
CSS_ESCAPE_RE = re.compile(r"\\([0-9a-fA-F]{1,6})\s?|\\(.)", re.S)
FOCUS_MARKER_RE = re.compile(r"/\*\s*focus-ring\s*\*/")
GRADIENT_RE = re.compile(r"\b((?:repeating-)?(?:linear|radial|conic)-gradient)\s*\(", re.I)
FILTER_FN_RE = re.compile(r"\b(drop-shadow|blur)\s*\(", re.I)
RADIUS_PROP_RE = re.compile(r"(?:-webkit-|-moz-)?border(?:-[a-z]+)*-radius")
LENGTH_RE = re.compile(r"(?<![\w.#-])(-?(?:\d+\.?\d*|\.\d+))([a-zA-Z%]*)")
KEYFRAMES_RE = re.compile(r"@(?:-webkit-|-moz-)?keyframes\b", re.I)
TRANSLATE_RE = re.compile(r"\btranslate(?:3d|x|y|z)?\s*\(", re.I)
SCROLL_FN_RE = re.compile(r"(?<![\w-])(scroll|view)\s*\(", re.I)
SCROLL_PROPS = frozenset(
    {
        "animation-timeline",
        "animation-range",
        "animation-range-start",
        "animation-range-end",
        "scroll-timeline",
        "scroll-timeline-name",
        "scroll-timeline-axis",
        "view-timeline",
        "view-timeline-name",
        "view-timeline-axis",
        "view-timeline-inset",
    }
)
FONT_SIZE_LINE_RE = re.compile(r"(?:^|\s)\S+\s*/\s*(?:var\([^)]*\)|[^\s,]+)\s+")
FONT_SIZE_RE = re.compile(
    r"(?:^|\s)(?:\d*\.?\d+(?:px|rem|em|%|pt|ch|ex|vw|vh)|(?:xx?-|xxx-)?(?:small|large)|medium"
    r"|smaller|larger)\s+",
    re.I,
)
JS_STYLE_RE = re.compile(
    r"\b(box-?shadow|text-?shadow|backdrop-?filter|(?:repeating-)?(?:linear|radial|conic)"
    r"-gradient\s*\()",
    re.I,
)
INTERSECTION_RE = re.compile(r"\bIntersectionObserver\b")
STAMP_SELECTOR_RE = re.compile(r"\.stamp(?![\w-])")  # .stamp, not .stamped-row

TEMPLATE_COMMENT_RE = re.compile(r"\{#.*?#\}|<!--.*?-->", re.S)
JINJA_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
STYLE_BLOCK_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>|\Z)", re.S | re.I)
SCRIPT_BLOCK_RE = re.compile(r"(<script\b[^>]*>)(.*?)(</script\s*>|\Z)", re.S | re.I)
TAG_RE = re.compile(r"</?[A-Za-z!][^<>]*>")
ATTR_RE = re.compile(
    r"(?<![\w:.-])([A-Za-z_:][\w:.-]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'=<>`]+))"
)
ENTITY_RE = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
JSON_STRING_RE = re.compile(r'"(?:[^"\\\n]|\\.)*"')
JSON_KEY_TAIL_RE = re.compile(r"\s*:")

DEVANAGARI_RE = re.compile("[\u0900-\u097f\ua8e0-\ua8ff]")
LANG_HI_RE = re.compile(r"\blang\s*=\s*[\"']?hi\b", re.I)
SEPARATOR_DOT_RE = re.compile("(?<=\\s)[\u00b7\u2022\u2027\u22c5](?=\\s)")
BANNED_RE = re.compile(
    r"\b(ai[\s\-\u2010\u2011]*powered|magic(?:al|ally)?|seamless(?:ly)?|supercharg(?:e|es|ed|ing)"
    r"|unlock(?:s|ed|ing)?|revolutionary|lorem|verified)\b",
    re.I,
)

EMOJI_RANGES = (
    (0x1F000, 0x1F2FF),  # mahjong, cards, enclosed supplements, regional indicators
    (0x1F300, 0x1FAFF),  # pictographs, emoticons, transport, supplemental symbols
    (0x2600, 0x27BF),  # miscellaneous symbols and dingbats (includes U+2728 sparkles)
    (0x231A, 0x231B),
    (0x2328, 0x2328),
    (0x23CF, 0x23CF),
    (0x23E9, 0x23F3),
    (0x23F8, 0x23FA),
    (0x3030, 0x3030),
    (0x303D, 0x303D),
    (0x3297, 0x3297),
    (0x3299, 0x3299),
    (0xFE0F, 0xFE0F),  # emoji presentation selector
    (0x20E3, 0x20E3),  # combining enclosing keycap
    (0xE0020, 0xE007F),  # emoji tag sequences
)
ARROW_RANGES = (
    (0x2190, 0x21FF),
    (0x27F0, 0x27FF),
    (0x2900, 0x297F),
    (0x2B00, 0x2BFF),
)


# ------------------------------------------------------------------ findings
@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    rule: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: rule {self.rule} ({SECTION}): {self.message}"


@dataclass
class Source:
    """One file's text plus the findings raised against it."""

    path: str
    text: str
    findings: list[Finding] = field(default_factory=list)
    _starts: list[int] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._starts = [0] + [m.end() for m in re.finditer("\n", self.text)]

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self._starts, offset)

    def raw_line(self, number: int) -> str:
        start = self._starts[number - 1]
        end = self.text.find("\n", start)
        return self.text[start:] if end < 0 else self.text[start:end]

    def add(self, offset: int, rule: int, message: str) -> None:
        self.findings.append(Finding(self.path, self.line_of(offset), rule, message))


@dataclass(frozen=True)
class Decl:
    """A CSS declaration with offsets into the file it came from."""

    prop: str
    value: str
    start: int
    value_start: int
    end: int
    scopes: tuple[tuple[str, int], ...]


# ------------------------------------------------------------------ text helpers
def spaces(text: str) -> str:
    """Same length as ``text``, every character but newlines turned into a space."""
    return re.sub(r"[^\n]", " ", text)


def blank(text: str, pattern: re.Pattern[str]) -> str:
    return pattern.sub(lambda m: spaces(m.group()), text)


def strip_css_comments(text: str) -> str:
    return CSS_COMMENT_OR_STRING_RE.sub(
        lambda m: spaces(m.group()) if m.group().startswith("/*") else m.group(), text
    )


def blank_strings_and_urls(value: str) -> str:
    value = CSS_STRING_RE.sub(lambda m: spaces(m.group()), value)
    return URL_RE.sub(lambda m: spaces(m.group()), value)


def decode_css_string(token: str) -> str:
    body = token[1:-1] if len(token) >= 2 and token[-1] == token[0] else token[1:]

    def unescape(match: re.Match[str]) -> str:
        if match.group(1):
            code = int(match.group(1), 16)
            return chr(code) if 0 < code <= 0x10FFFF else ""
        return match.group(2) if match.group(2) != "\n" else ""

    return CSS_ESCAPE_RE.sub(unescape, body)


def to_fraction(number: str) -> Fraction | None:
    try:
        return Fraction(Decimal(number))
    except (InvalidOperation, ValueError):
        return None


def in_ranges(code: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(low <= code <= high for low, high in ranges)


def char_problem(char: str) -> str | None:
    code = ord(char)
    if char == "\u2014":
        return "em dash (U+2014) is not allowed; use a comma, a colon or a full stop"
    if in_ranges(code, ARROW_RANGES):
        return f"arrow or arrow-like symbol {char} (U+{code:04X}) is not allowed; say it in words"
    if in_ranges(code, EMOJI_RANGES):
        return f"emoji or pictograph U+{code:04X} is not allowed"
    return None


def text_problems(text: str) -> Iterator[tuple[int, int, str]]:
    """Rule 5 (characters) problems in user-facing text, as (index, rule, message)."""
    for index, char in enumerate(text):
        problem = char_problem(char)
        if problem:
            yield index, 5, problem
    for match in SEPARATOR_DOT_RE.finditer(text):
        yield (
            match.start(),
            5,
            f"'{match.group()}' (U+{ord(match.group()):04X}) used as a separator; "
            "use a comma or separate lines",
        )


def word_problems(text: str) -> Iterator[tuple[int, int, str]]:
    """Rule 9 (banned words) problems, as (index, rule, message)."""
    for match in BANNED_RE.finditer(text):
        word = match.group(1)
        hint = "; Munim says Passed, never Verified" if word.lower() == "verified" else ""
        yield match.start(), 9, f'banned word "{word}"{hint}'


# ------------------------------------------------------------------ CSS
def parse_css(text: str, base: int = 0, inline: bool = False) -> list[Decl]:
    """Split comment-free CSS into declarations, tracking the enclosing selectors.

    ``inline`` treats ``text`` as the body of a style attribute (no braces).
    """
    decls: list[Decl] = []
    stack: list[tuple[str, int]] = []
    seg_start = 0
    depth = 0

    def add(start: int, end: int) -> None:
        segment = text[start:end]
        stripped = segment.strip()
        if not stripped or stripped.startswith("@"):
            return
        colon = segment.find(":")
        if colon < 0:
            return
        prop = segment[:colon].strip()
        if not PROP_RE.fullmatch(prop):
            return
        lead = len(segment) - len(segment.lstrip())
        decls.append(
            Decl(
                prop=prop.lower(),
                value=segment[colon + 1 :],
                start=base + start + lead,
                value_start=base + start + colon + 1,
                end=base + end,
                scopes=tuple(stack),
            )
        )

    for match in CSS_STRUCT_RE.finditer(text):
        piece = match.group()
        if piece[0] in "\"'":
            continue
        if piece == "(":
            depth += 1
            continue
        if piece == ")":
            depth = max(0, depth - 1)
            continue
        if piece == ";" and depth:
            continue  # e.g. url(data:image/svg+xml;utf8,...)
        if piece == "{":
            prelude = text[seg_start : match.start()]
            lead = len(prelude) - len(prelude.lstrip())
            stack.append((" ".join(prelude.split()), base + seg_start + lead))
        else:
            add(seg_start, match.start())
            if piece == "}" and stack:
                stack.pop()
        if piece in "{}":
            depth = 0
        seg_start = match.end()
    if inline:
        add(seg_start, len(text))
    return decls


def plain_value(value: str) -> str:
    return value.strip().lower().removesuffix("!important").strip()


def radius_problems(value: str) -> Iterator[tuple[int, str]]:
    for match in LENGTH_RE.finditer(value):
        number = to_fraction(match.group(1))
        unit = match.group(2).lower()
        if number is None or number == 0 or not unit:
            continue
        shown = match.group()
        if unit == "%":
            yield match.start(), f"border-radius {shown} is a percentage; no circles or pills"
            continue
        if unit == "px":
            px = number
        elif unit in ("rem", "em"):
            px = number * ROOT_PX
        else:
            yield match.start(), f"border-radius {shown} uses '{unit}'; use px, at most 6px"
            continue
        if px >= PILL_RADIUS_PX:
            yield match.start(), f"border-radius {shown} makes a pill; at most 6px"
        elif px > MAX_RADIUS_PX:
            yield match.start(), f"border-radius {shown} is above 6px"


def tracking_problem(value: str, unitless_is_px: bool = False) -> str | None:
    text = plain_value(value)
    if text in ("normal", "inherit", "0") or "var(" in text or "calc(" in text:
        return None
    match = re.fullmatch(r"(-?(?:\d+\.?\d*|\.\d+))([a-z%]*)", text)
    if not match:
        return None
    number = to_fraction(match.group(1))
    unit = match.group(2) or ("px" if unitless_is_px else "")
    if number is None or number <= 0:
        return None
    if unit == "px":
        em = number / ROOT_PX
    elif unit in ("em", "rem"):
        em = number
    else:
        return f"letter-spacing {text} uses '{unit or 'no unit'}'; use em, at most 0.02em"
    if em > MAX_TRACKING_EM:
        return f"letter-spacing {text} is above 0.02em"
    return None


def split_top_level(value: str) -> Iterator[tuple[int, str]]:
    """Split on commas outside parentheses and quotes, yielding (index, part)."""
    depth = 0
    quote = ""
    start = 0
    for index, char in enumerate(value):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            yield start, value[start:index]
            start = index + 1
    yield start, value[start:]


def normalise_family(name: str) -> str:
    name = name.strip().removesuffix("!important").strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in "\"'":
        name = name[1:-1]
    name = " ".join(name.split()).lower()
    if name.startswith("var("):
        name = name.replace(" ", "")
    return name


def family_problems(value: str) -> Iterator[tuple[int, str]]:
    for index, part in split_top_level(value):
        family = normalise_family(part)
        if family and family not in ALLOWED_FAMILIES:
            lead = len(part) - len(part.lstrip())
            yield (
                index + lead,
                f"font family {part.strip()} is not declared; use var(--font-ui) or "
                "var(--font-hand)",
            )


def font_shorthand_families(value: str) -> tuple[int, str] | None:
    """Return (index, family list) of a ``font`` shorthand value, if it can be found."""
    text = value.rstrip()
    if plain_value(text) in ("inherit", "initial", "unset", "revert") or plain_value(
        text
    ).startswith("var("):
        return None
    match = FONT_SIZE_LINE_RE.search(text) or FONT_SIZE_RE.search(text)
    if not match:
        return None
    return match.end(), text[match.end() :]


def check_decls(src: Source, decls: list[Decl], allow_hex: bool = False) -> None:
    """Apply the CSS rules (1, 2, 3, 4, 5, 6, 8, 9) to parsed declarations."""
    keyframes: dict[int, tuple[str, set[str]]] = {}
    for decl in decls:
        prop = decl.prop
        clean = blank_strings_and_urls(decl.value)
        lowered = plain_value(clean)

        if not allow_hex:
            for match in HEX_RE.finditer(clean):
                src.add(
                    decl.value_start + match.start(),
                    1,
                    f"raw hex colour {match.group()}; use a colour token through var(--color-...)",
                )

        if prop in ("box-shadow", "-webkit-box-shadow", "-moz-box-shadow") and lowered != "none":
            lines = range(src.line_of(decl.start), src.line_of(decl.end) + 1)
            if not any(FOCUS_MARKER_RE.search(src.raw_line(n)) for n in lines):
                src.add(
                    decl.start,
                    2,
                    "box-shadow is not allowed; only a focus ring marked /* focus-ring */ "
                    "on the same line",
                )
        if prop == "text-shadow" and lowered != "none":
            src.add(decl.start, 2, "text-shadow is not allowed")
        if prop in ("backdrop-filter", "-webkit-backdrop-filter") and lowered != "none":
            src.add(decl.start, 2, "backdrop-filter is not allowed (no blur or glass)")
        if prop in ("filter", "-webkit-filter"):
            for match in FILTER_FN_RE.finditer(clean):
                src.add(decl.value_start + match.start(), 2, f"{match.group(1)}() is not allowed")
        for match in GRADIENT_RE.finditer(clean):
            src.add(decl.value_start + match.start(), 2, f"{match.group(1)}() is not allowed")

        if RADIUS_PROP_RE.fullmatch(prop):
            for index, message in radius_problems(clean):
                src.add(decl.value_start + index, 3, message)

        if (
            prop == "text-transform"
            and "uppercase" in lowered
            and not any(STAMP_SELECTOR_RE.search(prelude) for prelude, _ in decl.scopes)
        ):
            src.add(decl.start, 4, "text-transform: uppercase is allowed only inside .stamp")
        if prop == "letter-spacing":
            problem = tracking_problem(clean)
            if problem:
                src.add(decl.start, 4, problem)

        for match in CSS_STRING_RE.finditer(decl.value):
            decoded = decode_css_string(match.group())
            for _, rule, message in (*text_problems(decoded), *word_problems(decoded)):
                src.add(decl.value_start + match.start(), rule, message)

        families: tuple[int, str] | None = None
        if prop == "font-family":
            families = (0, decl.value)
        elif prop == "font":
            families = font_shorthand_families(decl.value)
        if families is not None:
            offset, family_list = families
            for index, message in family_problems(family_list):
                src.add(decl.value_start + offset + index, 6, message)

        if prop in SCROLL_PROPS:
            src.add(decl.start, 8, f"{prop} (scroll-driven animation) is not allowed")
        for match in SCROLL_FN_RE.finditer(clean):
            src.add(
                decl.value_start + match.start(),
                8,
                f"{match.group(1)}() timeline (scroll-driven animation) is not allowed",
            )
        for prelude, offset in decl.scopes:
            if KEYFRAMES_RE.match(prelude):
                features = keyframes.setdefault(offset, (prelude, set()))[1]
                if prop == "opacity":
                    features.add("opacity")
                if prop == "translate" or (
                    prop in ("transform", "-webkit-transform") and TRANSLATE_RE.search(clean)
                ):
                    features.add("translate")

    for offset, (prelude, features) in keyframes.items():
        if {"opacity", "translate"} <= features:
            src.add(
                offset,
                8,
                f"'{prelude}' animates opacity together with translate (a fade-and-slide "
                "entrance); use an instant state change",
            )


def lint_css(src: Source, is_tokens: bool) -> None:
    check_decls(src, parse_css(strip_css_comments(src.text)), allow_hex=is_tokens)


# ------------------------------------------------------------------ JS
def lint_js(src: Source, text: str, base: int = 0) -> None:
    strings: list[tuple[int, int]] = []

    def keep_strings(match: re.Match[str]) -> str:
        piece = match.group()
        if piece.startswith(("//", "/*")):
            return spaces(piece)
        strings.append((match.start(), match.end()))
        return piece

    code = JS_TOKEN_RE.sub(keep_strings, text)
    for start, end in strings:
        for match in JS_HEX_RE.finditer(text, start, end):
            src.add(
                base + match.start(),
                1,
                f"raw hex colour {match.group()}; read colours from CSS custom properties",
            )
    for match in JS_STYLE_RE.finditer(code):
        name = match.group(1)
        if name.lower().replace("-", "") == "boxshadow":
            line = src.line_of(base + match.start())
            if FOCUS_MARKER_RE.search(src.raw_line(line)):
                continue
        src.add(base + match.start(), 2, f"{name.rstrip('( ')} is not allowed")
    for match in INTERSECTION_RE.finditer(code):
        src.add(
            base + match.start(),
            8,
            "IntersectionObserver (scroll-triggered effects) is not allowed",
        )


# ------------------------------------------------------------------ templates
def attr_value(match: re.Match[str]) -> tuple[str, int]:
    for group in (2, 3, 4):
        if match.group(group) is not None:
            return match.group(group), match.start(group)
    return "", match.end()


def visible_text(text: str) -> str:
    """Template text a reader can see: text nodes and user-facing attribute values."""
    text = blank(text, JINJA_RE)
    text = STYLE_BLOCK_RE.sub(lambda m: spaces(m.group()), text)
    text = SCRIPT_BLOCK_RE.sub(lambda m: spaces(m.group()), text)

    def keep_visible_attrs(match: re.Match[str]) -> str:
        tag = match.group()
        chars = list(spaces(tag))
        for attr in ATTR_RE.finditer(tag):
            if attr.group(1).lower() in VISIBLE_ATTRS:
                value, start = attr_value(attr)
                chars[start : start + len(value)] = value
        return "".join(chars)

    return TAG_RE.sub(keep_visible_attrs, text)


def lint_template(src: Source) -> None:
    text = blank(src.text, TEMPLATE_COMMENT_RE)

    for match in STYLE_BLOCK_RE.finditer(text):
        css = strip_css_comments(blank(match.group(2), JINJA_RE))
        check_decls(src, parse_css(css, base=match.start(2)))
    for match in SCRIPT_BLOCK_RE.finditer(text):
        lint_js(src, match.group(2), base=match.start(2))

    markup = STYLE_BLOCK_RE.sub(lambda m: m.group(1) + spaces(m.group(2)) + m.group(3), text)
    markup = SCRIPT_BLOCK_RE.sub(lambda m: m.group(1) + spaces(m.group(2)) + m.group(3), markup)
    for match in ATTR_RE.finditer(markup):
        name = match.group(1).lower()
        value, start = attr_value(match)
        if name == "style":
            css = strip_css_comments(blank(value, JINJA_RE))
            check_decls(src, parse_css(css, base=start, inline=True))
        elif name in COLOUR_ATTRS:
            for hex_match in HEX_RE.finditer(blank_strings_and_urls(value)):
                src.add(
                    start + hex_match.start(),
                    1,
                    f"raw hex colour {hex_match.group()} in {name}=; use currentColor or a "
                    "token through var(--color-...)",
                )
        elif name == "font-family":
            for index, message in family_problems(value):
                src.add(start + index, 6, message)
        elif name == "letter-spacing":
            problem = tracking_problem(value, unitless_is_px=True)
            if problem:
                src.add(start, 4, problem)

    for index, rule, message in text_problems(text):
        src.add(index, rule, message)
    for match in ENTITY_RE.finditer(text):
        decoded = html.unescape(match.group())
        if len(decoded) != 1:
            continue
        problem = char_problem(decoded)
        if problem:
            src.add(match.start(), 5, f"{problem} (written as {match.group()})")
        elif decoded == "\u00b7" and text[match.start() - 1 : match.start()].isspace():
            src.add(match.start(), 5, f"middle dot {match.group()} used as a separator")

    offset = 0
    for line in text.split("\n"):
        if DEVANAGARI_RE.search(line) and not LANG_HI_RE.search(line):
            src.add(
                offset,
                7,
                'Devanagari text on a line without lang="hi"; take Hindi from i18n or mark '
                'the element lang="hi"',
            )
        offset += len(line) + 1

    for index, rule, message in word_problems(visible_text(text)):
        src.add(index, rule, message)


# ------------------------------------------------------------------ i18n JSON
def lint_json(src: Source) -> None:
    for match in JSON_STRING_RE.finditer(src.text):
        if JSON_KEY_TAIL_RE.match(src.text, match.end()):
            continue  # a key, not shown to the user
        try:
            value = json.loads(match.group())
        except ValueError:
            value = match.group()[1:-1]
        if not isinstance(value, str):
            continue
        for _, rule, message in (*text_problems(value), *word_problems(value)):
            src.add(match.start(), rule, message)


# ------------------------------------------------------------------ driver
def lint_text(path: str, text: str, kind: str, is_tokens: bool = False) -> list[Finding]:
    """Lint ``text`` as a file of ``kind`` (template, css, js, json)."""
    src = Source(path, text)
    if kind == "template":
        lint_template(src)
    elif kind == "css":
        lint_css(src, is_tokens)
    elif kind == "js":
        lint_js(src, text)
    elif kind == "json":
        lint_json(src)
    else:
        raise ValueError(f"unknown kind {kind!r}")
    return sorted(set(src.findings))


def in_vendor(path: Path) -> bool:
    parts = path.resolve().parts
    width = len(VENDOR_PARTS)
    return any(parts[i : i + width] == VENDOR_PARTS for i in range(len(parts) - width + 1))


def wanted(path: Path) -> bool:
    return path.suffix.lower() in KINDS and not in_vendor(path)


def iter_files(roots: list[Path]) -> Iterator[Path]:
    for root in roots:
        if root.is_dir():
            yield from (p for p in sorted(root.rglob("*")) if p.is_file() and wanted(p))
        elif root.is_file() and wanted(root):
            yield root


def display(path: Path, repo_root: Path = REPO_ROOT) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="files or directories to lint (default: the web package templates, css, js, i18n)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repository root: the default scan roots are taken under it and paths are "
        "shown relative to it (default: this repository)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths: list[Path] = args.paths
    repo_root: Path = args.root
    missing = [p for p in paths if not p.exists()]
    if missing:
        for path in missing:
            print(f"design_lint: error: no such file or directory: {path}", file=sys.stderr)
        return 2
    roots = paths or list(default_roots(repo_root))
    missing_roots = [root for root in roots if not paths and not root.is_dir()]
    if missing_roots:
        for root in missing_roots:
            print(
                f"design_lint: error: scan root is missing: {display(root, repo_root)}",
                file=sys.stderr,
            )
        return 2

    findings: list[Finding] = []
    errors = 0
    checked = 0
    for path in iter_files(roots):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"design_lint: error: cannot read {path}: {exc}", file=sys.stderr)
            errors += 1
            continue
        checked += 1
        kind = KINDS[path.suffix.lower()]
        findings.extend(lint_text(display(path, repo_root), text, kind, path.name == TOKENS_FILE))

    for finding in findings:
        print(finding.format())
    print(f"design_lint: {checked} files checked, {len(findings)} problems", file=sys.stderr)
    if errors:
        return 2
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
