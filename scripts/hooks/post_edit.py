#!/usr/bin/env python3
"""Claude Code PostToolUse hook for Edit, Write and MultiEdit: fast checks on the edited file.

Specification: docs/planning/CLAUDE_CODE_PROMPT.md, Appendix A.2. Standard library only.

The hook JSON arrives on stdin. The project directory is the CLAUDE_PROJECT_DIR environment
variable, else the "cwd" field of the input, else the current directory. The edited file is
tool_input.file_path, absolute or relative to the project directory. Files outside the
project, under .git/, .venv/ or node_modules/ (at any depth) or under data/ (at the root)
are ignored. Nothing runs until <project>/.venv exists.

Checks by path; each one is skipped silently when its script or tool does not exist yet:

  *.py                                  ruff format, then ruff check --fix (remaining errors)
  munim_web templates/, static/css/,    scripts/design_lint.py <file>
  static/js/ (not static/js/vendor/)
  munim_web i18n/*.json                 scripts/check_i18n.py
  DESIGN.md                             scripts/build_tokens.py, then scripts/check_contrast.py
  rules/*.yaml, docs/DOMAIN_RULES.md    pytest -q -k rule_sync (never the full suite)

Every command runs as "<uv> run --no-sync --quiet ..." in the project directory, so the hook
never installs or updates the environment, with a 45 s timeout. <uv> is the MUNIM_HOOK_UV
environment variable, default "uv" (tests point it elsewhere). ruff check also gets
"--output-format concise" so each remaining error fits on one line of the report.

Exit codes read: ruff check 1 means errors remain; the Munim check scripts 1 means findings;
pytest 1 means failures and 5 means nothing collected (a skip). Any other non-zero code, a
timeout or a command that cannot start is a tool problem: one line on stderr, not blocking.

Exit 2 when a check found problems, with a report of at most 40 lines on stderr (file, check,
first relevant lines, then "Fix this before continuing."). Otherwise exit 0 with no output
apart from tool-problem notes. Input that is not a JSON object: exit 0 with a one-line note.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

TIMEOUT_SECONDS = 45.0
MAX_REPORT_LINES = 40
MAX_LINE_CHARS = 240
UV_ENV_VAR = "MUNIM_HOOK_UV"
FOOTER = "Fix this before continuing."

WEB_PACKAGE = "packages/munim_web/src/munim_web/"
DESIGN_LINT_PREFIXES = (
    WEB_PACKAGE + "templates/",
    WEB_PACKAGE + "static/css/",
    WEB_PACKAGE + "static/js/",
)
VENDOR_PREFIX = WEB_PACKAGE + "static/js/vendor/"
I18N_DIR = WEB_PACKAGE + "i18n"
IGNORED_ANYWHERE = frozenset({".git", ".venv", "node_modules"})
IGNORED_AT_ROOT = frozenset({"data"})


@dataclass(frozen=True)
class Check:
    """One command run through uv, and how to read its exit code."""

    label: str
    args: tuple[str, ...]
    script: str | None = None  # project-relative script that must exist
    tool: str | None = None  # executable that must exist in the project's .venv
    finding_codes: frozenset[int] = frozenset({1})
    clean_codes: frozenset[int] = frozenset({0})
    summary_only: bool = False  # pytest: report the FAILED and ERROR summary lines


@dataclass(frozen=True)
class Completed:
    """What a command did: its exit code and output, or why it did not finish."""

    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    problem: str | None = None
    started: bool = True


def project_dir(payload: Mapping[str, object]) -> str:
    """Return the project directory: CLAUDE_PROJECT_DIR, else the input's cwd, else ours."""
    from_env = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if from_env:
        return from_env
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        return cwd
    return os.getcwd()


def edited_file(payload: Mapping[str, object]) -> tuple[str, str] | None:
    """Return (project root, path relative to it) for a file to check, or None to ignore it."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, Mapping):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    root = os.path.realpath(project_dir(payload))
    target = os.path.realpath(os.path.join(root, file_path))
    try:
        common = os.path.commonpath([root, target])
    except ValueError:  # different drives on Windows
        return None
    if common != root or target == root:
        return None
    relative = os.path.relpath(target, root)
    parts = relative.split(os.sep)
    if parts[0] in IGNORED_AT_ROOT or any(part in IGNORED_ANYWHERE for part in parts[:-1]):
        return None
    if not os.path.isfile(target):
        return None
    return root, relative


def checks_for(relative: str) -> list[Check]:
    """Return the checks for a project-relative path (native separators), in order."""
    posix = relative.replace(os.sep, "/")
    argument = os.path.join(os.curdir, relative) if relative.startswith("-") else relative
    if posix.endswith(".py"):
        return [
            Check(
                "ruff format",
                ("ruff", "format", argument),
                tool="ruff",
                finding_codes=frozenset(),
            ),
            Check(
                "ruff check",
                ("ruff", "check", "--fix", "--quiet", "--output-format", "concise", argument),
                tool="ruff",
            ),
        ]
    if posix.startswith(DESIGN_LINT_PREFIXES) and not posix.startswith(VENDOR_PREFIX):
        script = "scripts/design_lint.py"
        return [Check("design_lint", ("python", script, argument), script=script)]
    if posixpath.dirname(posix) == I18N_DIR and posix.endswith(".json"):
        script = "scripts/check_i18n.py"
        return [Check("check_i18n", ("python", script), script=script)]
    if posix == "DESIGN.md":
        return [
            Check(
                "build_tokens",
                ("python", "scripts/build_tokens.py"),
                script="scripts/build_tokens.py",
            ),
            Check(
                "check_contrast",
                ("python", "scripts/check_contrast.py"),
                script="scripts/check_contrast.py",
            ),
        ]
    if (posixpath.dirname(posix) == "rules" and posix.endswith(".yaml")) or (
        posix == "docs/DOMAIN_RULES.md"
    ):
        return [
            Check(
                "rule sync test",
                ("pytest", "-q", "-k", "rule_sync"),
                tool="pytest",
                clean_codes=frozenset({0, 5}),
                summary_only=True,
            )
        ]
    return []


def venv_has_tool(root: str, tool: str) -> bool:
    """Return True when the project's .venv provides the executable."""
    venv = os.path.join(root, ".venv")
    candidates = (
        os.path.join(venv, "bin", tool),
        os.path.join(venv, "Scripts", tool + ".exe"),
    )
    return any(os.path.isfile(candidate) for candidate in candidates)


def available(root: str, check: Check) -> bool:
    """Return True when the check's script and tool exist."""
    if check.script is not None and not os.path.isfile(os.path.join(root, check.script)):
        return False
    return check.tool is None or venv_has_tool(root, check.tool)


def _kill(process: subprocess.Popen[str]) -> None:
    """Kill a timed-out command and everything it started."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
    else:
        process.kill()


def run_command(argv: Sequence[str], cwd: str, timeout: float) -> Completed:
    """Run a command with captured output and a timeout; never raise."""
    try:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=os.name == "posix",
        )
    except OSError as error:
        reason = error.strerror or type(error).__name__
        return Completed(None, problem=f"could not start {argv[0]} ({reason})", started=False)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill(process)
        process.communicate()
        return Completed(None, problem=f"timed out after {timeout:g} s")
    return Completed(process.returncode, stdout=stdout, stderr=stderr)


def clip(line: str) -> str:
    """Shorten a long output line."""
    line = line.rstrip()
    if len(line) <= MAX_LINE_CHARS:
        return line
    return line[: MAX_LINE_CHARS - 3] + "..."


def relevant_lines(check: Check, done: Completed) -> list[str]:
    """Return the output lines worth showing for a check that found problems."""
    lines = [clip(line) for line in (done.stdout + "\n" + done.stderr).splitlines() if line.strip()]
    if check.summary_only:
        summary = [line for line in lines if line.startswith(("FAILED", "ERROR"))]
        lines = summary or lines[-10:]
    return lines or [f"(no output; exit code {done.returncode})"]


def first_line(done: Completed) -> str:
    """Return the first non-empty output line, for a one-line tool-problem note."""
    for line in (done.stderr + "\n" + done.stdout).splitlines():
        if line.strip():
            return ": " + clip(line.strip())
    return ""


def build_report(
    relative: str, findings: Sequence[tuple[str, Sequence[str]]], notes: Sequence[str]
) -> list[str]:
    """Return the blocking report: at most MAX_REPORT_LINES lines, footer last."""
    lines = [f"post_edit: checks found problems in {relative}", *notes]
    budget = MAX_REPORT_LINES - len(lines) - len(findings) - 1
    for index, (label, body) in enumerate(findings):
        share = max(budget // (len(findings) - index), 0)
        shown = list(body)
        if len(shown) > share:
            keep = max(share - 1, 0)
            shown = [*shown[:keep], f"... {len(body) - keep} more lines"] if share else []
        lines.append(f"[{label}]")
        lines.extend(f"  {line}" for line in shown)
        budget -= len(shown)
    if len(lines) >= MAX_REPORT_LINES:
        lines = lines[: MAX_REPORT_LINES - 1]
    lines.append(FOOTER)
    return lines


def run_checks(root: str, relative: str, uv: str) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """Run the checks for one file. Return (findings by check, tool-problem notes)."""
    findings: list[tuple[str, list[str]]] = []
    notes: list[str] = []
    for check in checks_for(relative):
        if not available(root, check):
            continue
        done = run_command((uv, "run", "--no-sync", "--quiet", *check.args), root, TIMEOUT_SECONDS)
        if done.problem is not None:
            notes.append(f"post_edit: {check.label} skipped for {relative}: {done.problem}.")
            if not done.started:
                break
            continue
        if done.returncode in check.clean_codes:
            continue
        if done.returncode in check.finding_codes:
            findings.append((check.label, relevant_lines(check, done)))
            continue
        notes.append(
            f"post_edit: {check.label} could not check {relative} "
            f"(exit {done.returncode}, a tool problem, not blocking){first_line(done)}"
        )
    return findings, notes


def main(argv: Sequence[str] | None = None) -> int:
    """Run the checks for the edited file. Return 2 when they found problems, else 0."""
    parser = argparse.ArgumentParser(
        description="Claude Code PostToolUse hook: runs fast checks on the file just edited. "
        "Reads the hook JSON on stdin.",
    )
    parser.parse_args(argv)
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except ValueError:
        print("post_edit: the hook input is not valid JSON; nothing checked.", file=sys.stderr)
        return 0
    if not isinstance(payload, dict):
        print("post_edit: the hook input is not a JSON object; nothing checked.", file=sys.stderr)
        return 0
    located = edited_file(payload)
    if located is None:
        return 0
    root, relative = located
    if not os.path.isdir(os.path.join(root, ".venv")):
        return 0
    uv = os.environ.get(UV_ENV_VAR) or "uv"
    findings, notes = run_checks(root, relative, uv)
    if findings:
        for line in build_report(relative, findings, notes):
            print(line, file=sys.stderr)
        return 2
    for note in notes:
        print(note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
