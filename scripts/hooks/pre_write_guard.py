#!/usr/bin/env python3
"""Claude Code PreToolUse hook for Edit, Write and MultiEdit: block unsafe writes.

Specification: docs/planning/CLAUDE_CODE_PROMPT.md, Appendix A.1. Standard library only.

The hook JSON arrives on stdin. The project directory is the CLAUDE_PROJECT_DIR environment
variable, else the "cwd" field of the input, else the current directory. The path is
tool_input.file_path, absolute or relative to the project directory; symlinks and ".." are
resolved before any comparison. The new text is tool_input.content (Write),
tool_input.new_string (Edit) and the joined tool_input.edits[*].new_string (MultiEdit).

Rules, checked in this order; the first one that holds blocks the write:

  G1  the path resolves outside the project directory
  G2  the file name is .env, or .env.<anything> other than .env.example (in any directory)
  G3  the path is under data/, eval/real/ or .git/ at the project root
  G4  the new text contains a likely secret (SECRET_PATTERNS below)
  G5  the new text contains a 12-digit number that looks like an Aadhaar number: optionally
      grouped 4-4-4 with single spaces or hyphens, not part of a longer digit run, first
      digit 2 to 9, passing the Verhoeff checksum. Allowed when the path is under tests/ or
      eval/fixtures/ and the same line contains "synthetic" (any case)

Exit 0 allows the write and prints nothing. Exit 2 blocks it with one line on stderr:
"Blocked by pre_write_guard <rule id>: <reason>. Fix: <what to do>." The message never
repeats the matched text. Input that is not a JSON object is not a reason to block: the
hook exits 0 with a one-line note on stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Verhoeff checksum tables: multiplication in the dihedral group D5, the position
# permutation (row i is the base permutation applied i times) and the group inverse.
VERHOEFF_D: tuple[tuple[int, ...], ...] = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
VERHOEFF_P: tuple[tuple[int, ...], ...] = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
VERHOEFF_INV: tuple[int, ...] = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)

# G4: what each pattern looks like, for the message, and the pattern itself.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("a Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("a private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("a GitHub token", re.compile(r"gh[pousr]_[0-9A-Za-z]{36}")),
    ("a GitHub fine-grained token", re.compile(r"github_pat_[0-9A-Za-z_]{60,}")),
    ("an API secret key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
)

# G5: every start position of twelve digits (4-4-4, each gap an optional single space or
# hyphen) with no digit directly before or after. The lookahead finds overlapping
# candidates, so a failing candidate cannot hide a passing one. \d also matches other
# scripts' decimal digits (Devanagari, for example), which are checked the same way.
AADHAAR_CANDIDATE = re.compile(r"(?<!\d)(?=(\d{4}[ -]?\d{4}[ -]?\d{4})(?!\d))")
AADHAAR_SEPARATORS = frozenset(" -")
SYNTHETIC_MARKER = "synthetic"

# G3: protected locations relative to the project root, with the fix for each.
PROTECTED_PREFIXES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("data",),
        "runtime data belongs to the running app; put test data in a temporary directory "
        "and synthetic fixtures under eval/fixtures/",
    ),
    (
        ("eval", "real"),
        "real documents never enter the repository; use synthetic fixtures under eval/fixtures/",
    ),
    ((".git",), "change git state with git commands, not by writing files"),
)
# G5 exception: the synthetic marker is honoured only under these locations.
FIXTURE_PREFIXES: tuple[tuple[str, ...], ...] = (("tests",), ("eval", "fixtures"))

ENV_FILE = ".env"
ENV_EXAMPLE = ".env.example"


@dataclass(frozen=True)
class Block:
    """A reason to block the write."""

    rule: str
    reason: str
    fix: str

    def message(self) -> str:
        """Return the one-line message for stderr."""
        return f"Blocked by pre_write_guard {self.rule}: {self.reason}. Fix: {self.fix}."


def verhoeff_valid(digits: Sequence[int]) -> bool:
    """Return True when the digits, check digit last, pass the Verhoeff checksum."""
    check = 0
    for position, digit in enumerate(reversed(digits)):
        check = VERHOEFF_D[check][VERHOEFF_P[position % 8][digit]]
    return check == 0


def verhoeff_check_digit(digits: Sequence[int]) -> int:
    """Return the Verhoeff check digit to append to the digits."""
    check = 0
    for position, digit in enumerate(reversed(digits)):
        check = VERHOEFF_D[check][VERHOEFF_P[(position + 1) % 8][digit]]
    return VERHOEFF_INV[check]


def project_dir(payload: Mapping[str, object]) -> str:
    """Return the project directory: CLAUDE_PROJECT_DIR, else the input's cwd, else ours."""
    from_env = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if from_env:
        return from_env
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        return cwd
    return os.getcwd()


def relative_parts(root: str, target: str) -> tuple[str, ...] | None:
    """Return the parts of target relative to root, or None when target is outside root."""
    try:
        common = os.path.commonpath([root, target])
    except ValueError:  # different drives on Windows
        return None
    if common != root:
        return None
    relative = os.path.relpath(target, root)
    if relative == os.curdir:
        return ()
    return tuple(relative.split(os.sep))


def under(parts: Sequence[str], prefix: Sequence[str]) -> bool:
    """Return True when the path parts start with the prefix (compared case-insensitively)."""
    if len(parts) < len(prefix):
        return False
    return all(
        part.casefold() == wanted.casefold() for part, wanted in zip(parts, prefix, strict=False)
    )


def is_env_file(name: str) -> bool:
    """Return True for .env and .env.<anything> except .env.example."""
    folded = name.casefold()
    if folded == ENV_FILE:
        return True
    return folded.startswith(ENV_FILE + ".") and folded != ENV_EXAMPLE


def check_path(file_path: str, root: str) -> tuple[Block | None, tuple[str, ...] | None]:
    """Apply G1 to G3. Return the block, if any, and the resolved project-relative parts."""
    target = os.path.realpath(os.path.join(root, file_path))
    parts = relative_parts(root, target)
    if parts is None:
        return (
            Block(
                "G1",
                "the path resolves outside the project directory",
                "write inside the repository; put scratch files under .scratch/ in the "
                "repository, which git ignores",
            ),
            None,
        )
    names = {os.path.basename(os.path.normpath(file_path)), os.path.basename(target)}
    if any(is_env_file(name) for name in names):
        return (
            Block(
                "G2",
                "the file is a .env file, which holds real secrets",
                "do not write .env files; document settings in .env.example and leave real "
                "values to the human",
            ),
            parts,
        )
    for prefix, fix in PROTECTED_PREFIXES:
        if under(parts, prefix):
            location = "/".join(prefix) + "/"
            return Block("G3", f"the path is under {location}, which is protected", fix), parts
    return None, parts


def new_texts(tool_input: Mapping[str, object]) -> list[str]:
    """Return the new text of a Write, Edit or MultiEdit call."""
    texts: list[str] = []
    for key in ("content", "new_string"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            texts.append(value)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        pieces = [
            edit["new_string"]
            for edit in edits
            if isinstance(edit, Mapping) and isinstance(edit.get("new_string"), str)
        ]
        joined = "\n".join(pieces)
        if joined:
            texts.append(joined)
    return texts


def line_number(text: str, index: int) -> int:
    """Return the 1-based line number of a character index."""
    return text.count("\n", 0, index) + 1


def line_at(text: str, index: int) -> str:
    """Return the whole line that contains a character index."""
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return text[start:] if end == -1 else text[start:end]


def find_secret(text: str) -> tuple[str, int] | None:
    """Return the kind of secret found and its line number, or None."""
    for kind, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return kind, line_number(text, match.start())
    return None


def find_aadhaar(text: str, synthetic_allowed: bool) -> int | None:
    """Return the line number of the first Aadhaar-like number, or None.

    When synthetic_allowed is True, a number on a line that contains "synthetic" (any case)
    is not reported.
    """
    for match in AADHAAR_CANDIDATE.finditer(text):
        candidate = match.group(1)
        digits = [unicodedata.decimal(char) for char in candidate if char not in AADHAAR_SEPARATORS]
        if digits[0] < 2 or not verhoeff_valid(digits):
            continue
        start = match.start(1)
        if synthetic_allowed and SYNTHETIC_MARKER in line_at(text, start).casefold():
            continue
        return line_number(text, start)
    return None


def evaluate(payload: Mapping[str, object]) -> Block | None:
    """Return the first rule that blocks this tool call, or None."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        return None
    root = os.path.realpath(project_dir(payload))
    parts: tuple[str, ...] | None = None
    file_path = tool_input.get("file_path")
    if isinstance(file_path, str) and file_path:
        block, parts = check_path(file_path, root)
        if block is not None:
            return block
    texts = new_texts(tool_input)
    for text in texts:
        secret = find_secret(text)
        if secret is not None:
            kind, line = secret
            return Block(
                "G4",
                f"the new text contains what looks like {kind} (line {line} of the new text)",
                "remove it; read secrets from the environment or the git-ignored .env file, "
                "and use a placeholder such as <GEMINI_API_KEY> in examples",
            )
    synthetic_allowed = parts is not None and any(
        under(parts, prefix) for prefix in FIXTURE_PREFIXES
    )
    for text in texts:
        aadhaar_line = find_aadhaar(text, synthetic_allowed)
        if aadhaar_line is not None:
            return Block(
                "G5",
                "the new text contains a 12-digit number that passes the Aadhaar checksum "
                f"(line {aadhaar_line} of the new text)",
                "remove it; a synthetic test number belongs under tests/ or eval/fixtures/ "
                "on a line that contains the word synthetic",
            )
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Run the guard on the hook JSON from stdin. Return 0 to allow, 2 to block."""
    parser = argparse.ArgumentParser(
        description="Claude Code PreToolUse guard: blocks writes that leak secrets or "
        "personal data, or touch protected paths. Reads the hook JSON on stdin.",
    )
    parser.parse_args(argv)
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except ValueError:
        print(
            "pre_write_guard: the hook input is not valid JSON; nothing checked.", file=sys.stderr
        )
        return 0
    if not isinstance(payload, dict):
        print(
            "pre_write_guard: the hook input is not a JSON object; nothing checked.",
            file=sys.stderr,
        )
        return 0
    block = evaluate(payload)
    if block is None:
        return 0
    print(block.message(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
