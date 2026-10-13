"""String-file checks for Munim's i18n (docs/CONTENT.md, DESIGN.md section 11).

en.json and hi.json are flat objects mapping dotted keys to strings. Checks:
  a  both files parse and are flat objects of non-empty strings
  b  identical key sets
  c  the same {placeholder} names in both languages for each key
  d  no development markers (the missing-key brackets)
  e  no Latin-script words in hi.json except proper nouns, acronyms and units
  f  every literal key used in templates as t("key") exists; a key ending in "." is a prefix
     completed at run time, and some key must start with it
  g  every literal key used in Python as message_key=, note_key=, basis_key=, *_key params or
     t("key") exists

Exit 0 when clean, 1 with findings, 2 when a file cannot be read or is not UTF-8.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "packages/munim_web/src/munim_web"
DEFAULT_DIR = WEB / "i18n"
DEFAULT_TEMPLATES = (WEB / "templates", WEB / "notices")
DEFAULT_CODE = (ROOT / "packages/munim_core/src", WEB)
MARKERS = ("⟦", "⟧")

# Latin words allowed inside Hindi strings: proper nouns, acronyms, file formats and units that
# Indian papers print in Latin script (docs/CONTENT.md notes, docs/PLAN_REVIEW.md).
HI_LATIN_ALLOWED = frozenset(
    {
        "GSTIN",
        "PAN",
        "IFSC",
        "Udyam",
        "UDYAM",
        "MSMED",
        "MSME",
        "MSEFC",
        "Gemma",
        "Ollama",
        "Gemini",
        "Google",
        "API",
        "RBI",
        "JPEG",
        "PNG",
        "WebP",
        "HEIC",
        "PDF",
        "MB",
        "CGST",
        "SGST",
        "IGST",
        "HSN",
        "SAC",
        "GST",
        "ZIP",
        "JSON",
        "URL",
        "HTML",
        "Munim",
        "CHECKED",
        "NBCC",
        "India",
        "Ltd",
        "Silpi",
        "Industries",
        "Mahakali",
        "Foods",
        "IST",
        "A4",
        "CSV",
        "kg",
        "g",
        "l",
        "ml",
        "nos",
        "x",
        "XX",
    }
)
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
BACKTICKS = re.compile(r"`[^`]*`")
TEMPLATE_KEY = re.compile(r"""\bt\(\s*(["'])([A-Za-z0-9_.-]+)\1""")
CODE_KEY = re.compile(
    r"""(?:\b(?:message_key|note_key|basis_key|[a-z_]+_key)["']?\s*[=:]\s*|\bt\(\s*)(["'])"""
    r"""([a-z][a-z0-9_]*(?:\.[A-Za-z0-9_-]+)+)\1"""
)


@dataclass
class Report:
    findings: list[str] = field(default_factory=list)

    def add(self, path: Path | str, line: int, check: str, message: str) -> None:
        self.findings.append(f"{path}:{line}: {check}: {message}")


class InputError(Exception):
    """A file exists but cannot be decoded, so nothing about it can be checked."""


def read_utf8(path: Path) -> str:
    """Return the file's text; raise InputError (naming the file) when it is not UTF-8."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path}: not valid UTF-8 (byte {exc.start}: {exc.reason})") from exc


def line_of(raw: str, key: str) -> int:
    index = raw.find(json.dumps(key, ensure_ascii=False))
    return raw.count("\n", 0, index) + 1 if index >= 0 else 0


def load(path: Path, report: Report) -> tuple[dict[str, str], str] | None:
    raw = read_utf8(path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        report.add(path, exc.lineno, "a", f"not valid JSON: {exc.msg}")
        return None
    if not isinstance(data, dict):
        report.add(path, 1, "a", "the file must be a flat JSON object")
        return None
    clean: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(value, str):
            report.add(path, line_of(raw, key), "a", f"{key}: value must be a string")
        elif not value.strip():
            report.add(path, line_of(raw, key), "a", f"{key}: value is empty")
        else:
            clean[key] = value
    return clean, raw


def latin_words(value: str) -> list[str]:
    """Return Latin words in a Hindi string that are not allowed."""
    text = PLACEHOLDER.sub(" ", value)
    text = BACKTICKS.sub(" ", text)
    for marker in ("Run:", "चलाएँ:"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return [w for w in LATIN_WORD.findall(text) if w not in HI_LATIN_ALLOWED]


def check_pair(
    en: Mapping[str, str], hi: Mapping[str, str], paths: tuple[Path, Path], raws: tuple[str, str]
) -> Report:
    report = Report()
    en_path, hi_path = paths
    for key in sorted(set(en) - set(hi)):
        report.add(hi_path, 0, "b", f"{key}: missing (present in en.json)")
    for key in sorted(set(hi) - set(en)):
        report.add(en_path, 0, "b", f"{key}: missing (present in hi.json)")
    for key in sorted(set(en) & set(hi)):
        en_names, hi_names = set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(hi[key]))
        if en_names != hi_names:
            report.add(
                hi_path,
                line_of(raws[1], key),
                "c",
                f"{key}: placeholders differ (en {sorted(en_names)}, hi {sorted(hi_names)})",
            )
    for path, raw, strings in ((en_path, raws[0], en), (hi_path, raws[1], hi)):
        for key, value in strings.items():
            if any(marker in value for marker in MARKERS):
                report.add(path, line_of(raw, key), "d", f"{key}: contains a missing-key marker")
    for key, value in hi.items():
        bad = latin_words(value)
        if bad:
            report.add(
                hi_path, line_of(raws[1], key), "e", f"{key}: Latin words {bad} in Hindi text"
            )
    return report


def used_keys(files: Iterable[Path], pattern: re.Pattern[str]) -> list[tuple[Path, int, str]]:
    found: list[tuple[Path, int, str]] = []
    for path in files:
        for number, line in enumerate(read_utf8(path).splitlines(), start=1):
            for match in pattern.finditer(line):
                found.append((path, number, match.group(2)))
    return found


def iter_files(roots: Iterable[Path], suffixes: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in sorted(root.rglob("*")) if p.suffix in suffixes and p.is_file())
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--templates", type=Path, action="append")
    parser.add_argument("--code", type=Path, action="append")
    args = parser.parse_args(argv)
    en_path, hi_path = args.dir / "en.json", args.dir / "hi.json"
    report = Report()
    if not en_path.exists() and not hi_path.exists():
        print("check_i18n: no i18n files yet")
        return 0
    for path in (en_path, hi_path):
        if not path.exists():
            report.add(path, 0, "a", "file is missing; en.json and hi.json must both exist")
    try:
        loaded = [load(p, report) for p in (en_path, hi_path) if p.exists()]
        if len(loaded) == 2 and loaded[0] and loaded[1]:
            (en, en_raw), (hi, hi_raw) = loaded[0], loaded[1]
            report.findings += check_pair(en, hi, (en_path, hi_path), (en_raw, hi_raw)).findings
            templates = iter_files(args.templates or DEFAULT_TEMPLATES, (".html", ".j2"))
            for path, line, key in used_keys(templates, TEMPLATE_KEY):
                if key.endswith("."):  # t("paper.kind." ~ kind): a prefix completed at run time
                    if not any(k.startswith(key) for k in en):
                        report.add(
                            path, line, "f", f"{key}: no key in en.json starts with this prefix"
                        )
                elif key not in en:
                    report.add(path, line, "f", f"{key}: used in a template but not in en.json")
            code = iter_files(args.code or DEFAULT_CODE, (".py",))
            for path, line, key in used_keys(code, CODE_KEY):
                if key not in en:
                    report.add(path, line, "g", f"{key}: used in code but not in en.json")
    except (OSError, InputError) as exc:
        print(f"check_i18n: {exc}", file=sys.stderr)
        return 2
    for finding in report.findings:
        print(finding)
    return 1 if report.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
