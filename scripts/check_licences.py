"""Licence allow-list check (docs/ARCHITECTURE.md section 11, THIRD_PARTY.md "Rules").

Checks, in the current environment:
- L1 every installed distribution has an allowed licence (LGPL only for python-stdnum), or a
  documented exception in EXCEPTIONS;
- L2 every direct dependency declared in the workspace is mentioned in THIRD_PARTY.md;
- L3 every self-hosted font and vendored script has its licence file next to it.

Exit 0 when clean, 1 with problems, 2 when a manifest or THIRD_PARTY.md cannot be read, is
not UTF-8 or is not valid TOML.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_STATIC = Path("packages/munim_web/src/munim_web/static")

ALLOWED = frozenset(
    {
        "MIT",
        "MIT-CMU",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSD",
        "Apache-2.0",
        "ISC",
        "MPL-2.0",
        "PSF-2.0",
        "Python-2.0",
        "HPND",
        "OFL-1.1",
        "0BSD",
        "Unlicense",
        "CC0-1.0",
        "Zlib",
    }
)
LGPL_ALLOWED_FOR = frozenset({"python-stdnum"})

# Distributions whose licence is acceptable for a documented reason the allow-list cannot
# express. Each entry names the reason; docs/adr/0007 records the decision.
EXCEPTIONS: dict[str, str] = {
    "text-unidecode": (
        "dev-only, pulled in by pytest-playwright through python-slugify; dual-licensed "
        "Artistic License or GPL, used unmodified under the Artistic License and never "
        "shipped with the app (docs/adr/0007-dev-only-licence-exception.md)"
    ),
}

# Free-text licence fields and classifier names mapped to SPDX-like ids. Order matters: the
# first matching pattern wins, so specific names come before generic ones.
TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), spdx)
    for pattern, spdx in (
        (r"\blgpl|lesser general public", "LGPL-2.1-or-later"),
        (r"\bagpl|affero", "AGPL"),
        (r"\bgpl\b|gnu general public", "GPL"),
        (r"artistic", "Artistic"),
        (r"mit-cmu|cmu license", "MIT-CMU"),
        (r"\bmit\b|permission is hereby granted, free of charge", "MIT"),
        (r"bsd[- ]?2|2-clause|simplified bsd", "BSD-2-Clause"),
        (r"bsd[- ]?3|3-clause|new bsd|modified bsd", "BSD-3-Clause"),
        (r"0bsd|zero-clause", "0BSD"),
        (r"\bbsd\b", "BSD"),
        (r"apache", "Apache-2.0"),
        (r"mozilla public license 2|\bmpl[- ]?2", "MPL-2.0"),
        (r"\bisc\b", "ISC"),
        (r"python software foundation|\bpsfl?\b|psf-2", "PSF-2.0"),
        (r"\bhpnd\b|historical permission", "HPND"),
        (r"unlicense", "Unlicense"),
        (r"cc0", "CC0-1.0"),
        (r"zlib", "Zlib"),
        (r"open font license|\bofl\b", "OFL-1.1"),
    )
)
REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")  # PEP 508 distribution name


@dataclass(frozen=True)
class Distribution:
    name: str
    expression: str = ""
    license_text: str = ""
    classifiers: tuple[str, ...] = ()
    license_file_head: str = ""


def normalise_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def classify_text(text: str) -> set[str]:
    """Return every licence id a free-text field mentions."""
    found = {spdx for pattern, spdx in TEXT_PATTERNS if pattern.search(text)}
    if "LGPL-2.1-or-later" in found:
        found.discard("GPL")
    if "MIT-CMU" in found:
        found.discard("MIT")
    return found


def expression_allowed(expression: str, name: str) -> bool:
    """Evaluate an SPDX expression: OR passes if any branch passes, AND if all do."""
    allowed = ALLOWED | ({"LGPL-2.1-or-later", "LGPL-2.1+"} if name in LGPL_ALLOWED_FOR else set())
    for branch in re.split(r"\s+OR\s+", expression.strip("() ")):
        terms = [t for t in re.split(r"\s+AND\s+", branch.strip("() ")) if t]
        if terms and all(t.strip("() ") in allowed for t in terms):
            return True
    return False


def licence_ids(dist: Distribution) -> tuple[set[str], str]:
    """Return (licence ids, where they came from) for a distribution."""
    if dist.expression:
        return {dist.expression}, "License-Expression"
    for source, text in (
        ("classifiers", " ; ".join(dist.classifiers)),
        ("License", dist.license_text),
        ("licence file", dist.license_file_head),
    ):
        ids = classify_text(text) if text else set()
        if ids:
            return ids, source
    return set(), "none"


def check_distribution(dist: Distribution) -> str | None:
    """Return a problem line for a distribution, or None when its licence is acceptable."""
    name = normalise_name(dist.name)
    if name.startswith("munim-") or name == "munim-workspace":
        return None
    if name in EXCEPTIONS:
        return None
    ids, source = licence_ids(dist)
    if not ids:
        return f"L1: {name}: no licence found in its metadata or licence file"
    if source == "License-Expression":
        if expression_allowed(dist.expression, name):
            return None
        return f"L1: {name}: licence expression {dist.expression!r} is not on the allow-list"
    lgpl_ok = name in LGPL_ALLOWED_FOR
    acceptable = ALLOWED | ({"LGPL-2.1-or-later"} if lgpl_ok else set())
    # Dual-licensed packages list several ids; one acceptable licence is enough.
    if ids & acceptable:
        return None
    return f"L1: {name}: licence {sorted(ids)} (from {source}) is not on the allow-list"


def installed_distributions() -> list[Distribution]:
    dists: list[Distribution] = []
    for dist in metadata.distributions():
        meta = dist.metadata
        head = ""
        for file in dist.files or ():
            if re.search(r"(licen[cs]e|copying)", file.name, re.IGNORECASE):
                try:
                    head = Path(str(dist.locate_file(file))).read_text(errors="replace")[:400]
                except OSError:
                    continue
                break
        dists.append(
            Distribution(
                name=meta["Name"],
                expression=(meta.get("License-Expression") or "").strip(),
                license_text=(meta.get("License") or "").strip()[:400],
                classifiers=tuple(
                    c.split("::")[-1].strip()
                    for c in meta.get_all("Classifier") or []
                    if c.startswith("License ::")
                ),
                license_file_head=head,
            )
        )
    return dists


def requirement_name(requirement: str) -> str:
    match = REQUIREMENT_NAME.match(requirement.strip())
    return normalise_name(match.group(0)) if match else ""


class InputError(Exception):
    """A manifest or THIRD_PARTY.md cannot be read, decoded or parsed."""


def read_utf8(path: Path) -> str:
    """Return the file's text; raise InputError naming the file when it is unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise InputError(f"{path}: not valid UTF-8 (byte {exc.start}: {exc.reason})") from exc


def declared_dependencies(root: Path) -> set[str]:
    """Return the direct dependencies declared in the workspace manifests."""
    names: set[str] = set()
    manifests = [root / "pyproject.toml", *sorted(root.glob("packages/*/pyproject.toml"))]
    for manifest in manifests:
        try:
            data = tomllib.loads(read_utf8(manifest))
        except tomllib.TOMLDecodeError as exc:
            raise InputError(f"{manifest}: not valid TOML ({exc})") from exc
        project = data.get("project", {})
        requirements: list[str] = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            requirements.extend(extra)
        for group in data.get("dependency-groups", {}).values():
            requirements.extend(r for r in group if isinstance(r, str))
        names.update(requirement_name(r) for r in requirements)
    return {n for n in names if n and not n.startswith("munim-")}


def missing_from_third_party(names: Iterable[str], third_party: str) -> list[str]:
    """Return the names with no whole-token mention (so pypdf is not found in pypdfium2)."""
    text = normalise_name(third_party)
    return sorted(
        n
        for n in names
        if not re.search(rf"(?<![a-z0-9]){re.escape(normalise_name(n))}(?![a-z0-9])", text)
    )


def check_assets(root: Path) -> list[str]:
    problems: list[str] = []
    fonts = root / WEB_STATIC / "fonts"
    if any(fonts.glob("*.woff2")) and not any((fonts / "LICENSES").glob("*.txt")):
        problems.append(f"L3: {fonts.relative_to(root)}: fonts without LICENSES/*.txt")
    for script in sorted((root / WEB_STATIC / "js" / "vendor").glob("*.js")):
        stem = script.name.split(".")[0]
        if not list(script.parent.glob(f"{stem}*LICENSE*")):
            problems.append(f"L3: {script.relative_to(root)}: no licence file next to it")
    return problems


def run(root: Path, third_party: Path, dists: Sequence[Distribution], verbose: bool) -> list[str]:
    problems = [p for d in dists if (p := check_distribution(d))]
    if verbose:
        for dist in sorted(dists, key=lambda d: normalise_name(d.name)):
            ids, source = licence_ids(dist)
            print(f"{normalise_name(dist.name):32} {', '.join(sorted(ids)) or '-':28} {source}")
    third_party_text = read_utf8(third_party)
    problems += [
        f"L2: {name}: declared dependency has no row in {third_party.name}"
        for name in missing_from_third_party(declared_dependencies(root), third_party_text)
    ]
    problems += check_assets(root)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--third-party", type=Path, default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="list every licence")
    args = parser.parse_args(argv)
    third_party = args.third_party or args.root / "THIRD_PARTY.md"
    try:
        dists = installed_distributions()
        problems = run(args.root, third_party, dists, args.verbose)
    except (OSError, InputError) as exc:
        print(f"check_licences: {exc}", file=sys.stderr)
        return 2
    for problem in problems:
        print(problem)
    print(f"check_licences: {len(dists)} distributions, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
