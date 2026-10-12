"""Repository hygiene guard (docs/SECURITY_PRIVACY.md section 7, docs/TESTING.md section 9).

Blocks, for the given files (pre-commit passes staged files) or for every tracked file:
- R1 files larger than 2 MB;
- R2 images or PDFs outside eval/fixtures/ and docs/screens/;
- R3 strings shaped like a GSTIN outside eval/fixtures/, tests/ and docs/.

Exit 0 when clean, 1 with findings, 2 when git or a file cannot be read.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2 * 1024 * 1024
IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".gif", ".bmp", ".tif", ".tiff", ".pdf",
}
IMAGE_DIRS = ("eval/fixtures/", "docs/screens/")
GSTIN_DIRS = ("eval/fixtures/", "tests/", "docs/")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".html", ".j2", ".css", ".js",
    ".sql", ".cfg", ".ini", ".sh", "",
}


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def check_file(rel: str, root: Path) -> list[str]:
    path = root / rel
    if not path.is_file():
        return []
    rel = rel.replace("\\", "/")
    problems: list[str] = []
    size = path.stat().st_size
    if size > MAX_BYTES:
        problems.append(f"{rel}:0: R1: file is {size} bytes; the limit is {MAX_BYTES}")
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES and not rel.startswith(IMAGE_DIRS):
        problems.append(
            f"{rel}:0: R2: images and PDFs belong only in eval/fixtures/ or docs/screens/"
        )
    if suffix in TEXT_SUFFIXES and not rel.startswith(GSTIN_DIRS) and size <= MAX_BYTES:
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if GSTIN_RE.search(line):
                problems.append(
                    f"{rel}:{number}: R3: GSTIN-shaped string outside eval/fixtures/, tests/ "
                    "and docs/; use synthetic values in those folders only"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="files to check (default: all tracked files)")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        files = args.files or tracked_files(args.root)
        problems = [p for rel in files for p in check_file(rel, args.root)]
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"check_repo_files: {exc}", file=sys.stderr)
        return 2
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
