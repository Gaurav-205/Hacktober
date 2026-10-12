"""Tests for scripts/hooks/post_edit.py (docs/planning/CLAUDE_CODE_PROMPT.md, A.2).

Two kinds of temporary project are used, both under tmp_path:

- Real tools. The project's .venv is a symlink to this repository's .venv, and its
  pyproject.toml holds only [tool.ruff] (no [project] table, so uv treats the directory as a
  plain environment and never syncs or rebuilds the linked .venv). The hook runs the real ruff
  through the real uv. Munim's own check scripts are stubs written here, so these tests do
  not depend on scripts/design_lint.py or scripts/check_i18n.py, which are built separately.
- Fake uv. MUNIM_HOOK_UV points at a small script that records each command line and fails
  on request, so the tests can assert the exact commands and the exit-code handling.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import LoadHook, RunHook

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = "packages/munim_web/src/munim_web"
FOOTER = "Fix this before continuing."
UV_COMMAND = ["run", "--no-sync", "--quiet"]

DESIGN_LINT_STUB = """\
import sys
from pathlib import Path

path = sys.argv[1]
for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
    if "box-shadow" in line:
        print(f"{path}:{number}: STUB-SHADOW: shadows are not allowed")
        raise SystemExit(1)
raise SystemExit(0)
"""

CHECK_I18N_STUB = """\
import json
from pathlib import Path

folder = Path("packages/munim_web/src/munim_web/i18n")
english = json.loads((folder / "en.json").read_text(encoding="utf-8"))
hindi = json.loads((folder / "hi.json").read_text(encoding="utf-8"))
missing = sorted(set(english) ^ set(hindi))
for key in missing:
    print(f"{folder}/hi.json:1: STUB-I18N: key {key} is missing in one language")
raise SystemExit(1 if missing else 0)
"""

FAKE_UV_BODY = """\
import json
import os
import sys

arguments = sys.argv[1:]
with open(os.environ["FAKE_UV_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"args": arguments, "cwd": os.getcwd()}) + "\\n")
if os.environ.get("FAKE_UV_TRIGGER") in arguments:
    sys.stdout.write(os.environ.get("FAKE_UV_OUTPUT", ""))
    raise SystemExit(int(os.environ.get("FAKE_UV_EXIT", "1")))
"""


def put(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_payload(path: Path | str) -> dict[str, object]:
    return {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": ""}}


def assert_silent_pass(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout == ""


def report_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    """Assert a blocking report within the limits and return its lines."""
    assert result.returncode == 2, result.stderr
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert 3 <= len(lines) <= 40
    assert lines[-1] == FOOTER
    return lines


# ---------------------------------------------------------------- real tools
@pytest.fixture
def uv_executable() -> str:
    found = os.environ.get("UV") or shutil.which("uv")
    if found is None:
        pytest.fail("uv is not on PATH; the post-edit hook runs every tool through uv")
    return found


@pytest.fixture
def real_project(tmp_path: Path) -> Path:
    if not (REPO_ROOT / ".venv" / "bin" / "ruff").is_file():
        pytest.fail("the repository .venv has no ruff; run make install first")
    root = tmp_path / "project"
    root.mkdir()
    (root / ".venv").symlink_to(REPO_ROOT / ".venv", target_is_directory=True)
    put(
        root,
        "pyproject.toml",
        '[tool.ruff]\nline-length = 100\n\n[tool.ruff.lint]\nselect = ["E", "F"]\n',
    )
    put(root, "scripts/design_lint.py", DESIGN_LINT_STUB)
    put(root, "scripts/check_i18n.py", CHECK_I18N_STUB)
    return root


@pytest.fixture
def run_real(run_hook: RunHook, real_project: Path, uv_executable: str) -> RunHook:
    def _run(path: Path | str) -> subprocess.CompletedProcess[str]:
        return run_hook(
            "post_edit",
            write_payload(path),
            project=real_project,
            cwd=real_project,
            env={"MUNIM_HOOK_UV": uv_executable},
        )

    return _run


def test_clean_python_file_passes_silently(run_real: RunHook, real_project: Path) -> None:
    source = 'def greet(name: str) -> str:\n    return "hello " + name\n'
    path = put(real_project, "app/clean.py", source)
    assert_silent_pass(run_real(path))
    assert path.read_text(encoding="utf-8") == source


def test_unformatted_python_is_formatted_silently(run_real: RunHook, real_project: Path) -> None:
    path = put(real_project, "app/spacing.py", "value=[1,2 ,3]\n")
    assert_silent_pass(run_real(path))
    assert path.read_text(encoding="utf-8") == "value = [1, 2, 3]\n"


def test_unused_import_is_removed_silently(run_real: RunHook, real_project: Path) -> None:
    path = put(real_project, "app/unused.py", "import os\n\nVALUE = 1\n")
    assert_silent_pass(run_real(path))
    content = path.read_text(encoding="utf-8")
    assert "import os" not in content
    assert "VALUE = 1" in content


def test_undefined_name_blocks_with_f821(run_real: RunHook, real_project: Path) -> None:
    path = put(real_project, "app/bad.py", "print(undefined_name_for_hook_check)\n")
    lines = report_lines(run_real(path))
    assert lines[0] == f"post_edit: checks found problems in {os.path.join('app', 'bad.py')}"
    assert "[ruff check]" in lines
    f821 = [line for line in lines if "F821" in line]
    assert len(f821) == 1
    assert "bad.py:1:7: F821 Undefined name `undefined_name_for_hook_check`" in f821[0]


def test_relative_file_path_is_resolved_against_project(
    run_real: RunHook, real_project: Path
) -> None:
    put(real_project, "app/bad.py", "print(undefined_name_for_hook_check)\n")
    lines = report_lines(run_real("app/bad.py"))
    assert any("F821" in line for line in lines)


def test_report_is_capped_at_40_lines(run_real: RunHook, real_project: Path) -> None:
    source = "".join(f"print(undefined_{index})\n" for index in range(100))
    path = put(real_project, "app/many.py", source)
    lines = report_lines(run_real(path))
    assert len(lines) == 40
    assert "  " + "app/many.py:1:7: F821 Undefined name `undefined_0`" in lines
    assert any(line.strip().startswith("...") and "more lines" in line for line in lines)


def test_template_with_box_shadow_blocks(run_real: RunHook, real_project: Path) -> None:
    template = '<div class="card">\n<style>.card { box-shadow: 0 1px 2px; }</style>\n</div>\n'
    path = put(real_project, f"{WEB}/templates/page.html", template)
    lines = report_lines(run_real(path))
    assert "[design_lint]" in lines
    assert f"  {WEB}/templates/page.html:2: STUB-SHADOW: shadows are not allowed" in lines


def test_clean_template_passes_silently(run_real: RunHook, real_project: Path) -> None:
    path = put(real_project, f"{WEB}/templates/page.html", '<div class="card">ok</div>\n')
    assert_silent_pass(run_real(path))


def test_static_css_is_design_linted(run_real: RunHook, real_project: Path) -> None:
    path = put(real_project, f"{WEB}/static/css/app.css", ".card {\n  box-shadow: none;\n}\n")
    lines = report_lines(run_real(path))
    assert f"  {WEB}/static/css/app.css:2: STUB-SHADOW: shadows are not allowed" in lines


def test_vendored_js_is_not_design_linted(run_real: RunHook, real_project: Path) -> None:
    path = put(real_project, f"{WEB}/static/js/vendor/htmx.min.js", "a.style='box-shadow:0'\n")
    assert_silent_pass(run_real(path))


def test_i18n_file_missing_a_key_blocks(run_real: RunHook, real_project: Path) -> None:
    put(real_project, f"{WEB}/i18n/en.json", '{"nav.home": "Home", "nav.help": "Help"}\n')
    path = put(real_project, f"{WEB}/i18n/hi.json", '{"nav.home": "होम"}\n')
    lines = report_lines(run_real(path))
    assert "[check_i18n]" in lines
    assert any("STUB-I18N: key nav.help is missing" in line for line in lines)


def test_complete_i18n_files_pass_silently(run_real: RunHook, real_project: Path) -> None:
    put(real_project, f"{WEB}/i18n/en.json", '{"nav.home": "Home"}\n')
    path = put(real_project, f"{WEB}/i18n/hi.json", '{"nav.home": "होम"}\n')
    assert_silent_pass(run_real(path))


def test_missing_check_script_is_skipped_silently(run_real: RunHook, real_project: Path) -> None:
    (real_project / "scripts" / "design_lint.py").unlink()
    path = put(real_project, f"{WEB}/templates/page.html", "<style>a { box-shadow: 0 }</style>\n")
    assert_silent_pass(run_real(path))


def test_path_outside_project_is_ignored(run_real: RunHook, tmp_path: Path) -> None:
    path = put(tmp_path, "outside.py", "print(undefined_name_for_hook_check)\n")
    assert_silent_pass(run_real(path))


@pytest.mark.parametrize(
    "relative",
    [
        "data/bad.py",
        "node_modules/pkg/bad.py",
        ".git/hooks/bad.py",
        "packages/x/node_modules/bad.py",
    ],
)
def test_ignored_directories_are_not_checked(
    run_real: RunHook, real_project: Path, relative: str
) -> None:
    path = put(real_project, relative, "x=1\nprint(undefined_name_for_hook_check)\n")
    assert_silent_pass(run_real(path))
    assert path.read_text(encoding="utf-8").startswith("x=1\n")  # not even formatted


def test_missing_venv_exits_silently_without_running_anything(
    run_real: RunHook, real_project: Path
) -> None:
    (real_project / ".venv").unlink()
    path = put(real_project, "app/bad.py", "x=1\nprint(undefined_name_for_hook_check)\n")
    assert_silent_pass(run_real(path))
    assert path.read_text(encoding="utf-8").startswith("x=1\n")  # not formatted


def test_missing_uv_is_a_one_line_note_and_not_blocking(
    run_hook: RunHook, real_project: Path, tmp_path: Path
) -> None:
    path = put(real_project, "app/bad.py", "print(undefined_name_for_hook_check)\n")
    result = run_hook(
        "post_edit",
        write_payload(path),
        project=real_project,
        cwd=real_project,
        env={"MUNIM_HOOK_UV": str(tmp_path / "no-such-uv")},
    )
    assert result.returncode == 0
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("post_edit: ruff format skipped for")
    assert "could not start" in lines[0]


@pytest.mark.parametrize("raw", ["{not json", "", "[1, 2]"])
def test_malformed_input_exits_0_with_a_note(
    run_hook: RunHook, real_project: Path, raw: str
) -> None:
    result = run_hook("post_edit", raw, project=real_project, cwd=real_project)
    assert result.returncode == 0
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("post_edit: the hook input is not")


# ---------------------------------------------------------------- fake uv
class FakeUv:
    """A project whose uv is a recording stub, and a way to run the hook in it."""

    def __init__(self, tmp_path: Path, run_hook: RunHook) -> None:
        self.root = tmp_path / "project"
        self.log = tmp_path / "uv-calls.jsonl"
        self.executable = tmp_path / "fake-uv"
        self._run_hook = run_hook
        for tool in ("ruff", "pytest"):
            put(self.root, f".venv/bin/{tool}", "")
        for script in ("design_lint", "check_i18n", "build_tokens", "check_contrast"):
            put(self.root, f"scripts/{script}.py", "")
        self.executable.write_text(f"#!{sys.executable}\n{FAKE_UV_BODY}", encoding="utf-8")
        self.executable.chmod(0o755)

    def run(
        self,
        relative: str,
        *,
        trigger: str | None = None,
        exit_code: int = 1,
        output: str = "",
        payload: dict[str, object] | None = None,
        project: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        put(self.root, relative, "content\n")
        env = {"MUNIM_HOOK_UV": str(self.executable), "FAKE_UV_LOG": str(self.log)}
        if trigger is not None:
            env |= {"FAKE_UV_TRIGGER": trigger, "FAKE_UV_EXIT": str(exit_code)}
            env["FAKE_UV_OUTPUT"] = output
        return self._run_hook(
            "post_edit",
            payload if payload is not None else write_payload(self.root / relative),
            project=self.root if project is None else project,
            cwd=self.root,
            env=env,
        )

    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        entries = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            assert entry["cwd"] == os.path.realpath(self.root)
        return [entry["args"] for entry in entries]


@pytest.fixture
def fake(tmp_path: Path, run_hook: RunHook) -> FakeUv:
    return FakeUv(tmp_path, run_hook)


def test_python_file_runs_ruff_format_then_ruff_check_without_sync(fake: FakeUv) -> None:
    assert_silent_pass(fake.run("app/module.py"))
    target = os.path.join("app", "module.py")
    assert fake.calls() == [
        [*UV_COMMAND, "ruff", "format", target],
        [*UV_COMMAND, "ruff", "check", "--fix", "--quiet", "--output-format", "concise", target],
    ]


def test_project_dir_falls_back_to_cwd_field(fake: FakeUv) -> None:
    payload = write_payload("app/module.py") | {"cwd": str(fake.root)}
    put(fake.root, "app/module.py", "content\n")
    result = fake.run("app/module.py", payload=payload, project=Path(""))
    assert_silent_pass(result)
    assert [call[3:5] for call in fake.calls()] == [["ruff", "format"], ["ruff", "check"]]


def test_template_runs_design_lint_on_the_file(fake: FakeUv) -> None:
    assert_silent_pass(fake.run(f"{WEB}/templates/base.html"))
    target = os.path.join(*WEB.split("/"), "templates", "base.html")
    assert fake.calls() == [[*UV_COMMAND, "python", "scripts/design_lint.py", target]]


def test_static_js_runs_design_lint_but_vendor_js_does_not(fake: FakeUv) -> None:
    assert_silent_pass(fake.run(f"{WEB}/static/js/vendor/htmx.min.js"))
    assert fake.calls() == []
    assert_silent_pass(fake.run(f"{WEB}/static/js/app.js"))
    assert [call[3:5] for call in fake.calls()] == [["python", "scripts/design_lint.py"]]


def test_i18n_file_runs_check_i18n_without_arguments(fake: FakeUv) -> None:
    assert_silent_pass(fake.run(f"{WEB}/i18n/hi.json"))
    assert fake.calls() == [[*UV_COMMAND, "python", "scripts/check_i18n.py"]]


def test_design_md_runs_build_tokens_then_check_contrast(fake: FakeUv) -> None:
    assert_silent_pass(fake.run("DESIGN.md"))
    assert fake.calls() == [
        [*UV_COMMAND, "python", "scripts/build_tokens.py"],
        [*UV_COMMAND, "python", "scripts/check_contrast.py"],
    ]


def test_design_md_contrast_finding_blocks(fake: FakeUv) -> None:
    finding = "DESIGN.md:40: C1: ink on bond is 3.10, below 4.5"
    result = fake.run("DESIGN.md", trigger="scripts/check_contrast.py", output=finding + "\n")
    lines = report_lines(result)
    assert lines[:3] == [
        "post_edit: checks found problems in DESIGN.md",
        "[check_contrast]",
        "  " + finding,
    ]


@pytest.mark.parametrize("relative", ["rules/clock.yaml", "docs/DOMAIN_RULES.md"])
def test_rule_files_run_only_the_rule_sync_test(fake: FakeUv, relative: str) -> None:
    assert_silent_pass(fake.run(relative))
    assert fake.calls() == [[*UV_COMMAND, "pytest", "-q", "-k", "rule_sync"]]


def test_rule_sync_with_nothing_collected_is_a_skip(fake: FakeUv) -> None:
    assert_silent_pass(fake.run("rules/clock.yaml", trigger="pytest", exit_code=5))


def test_rule_sync_failure_blocks_with_the_failed_lines(fake: FakeUv) -> None:
    output = (
        "F.                                     [100%]\n"
        "E   AssertionError: rule ids differ\n"
        "FAILED tests/unit/test_rules.py::test_rule_sync - AssertionError: rule ids differ\n"
        "1 failed, 1 passed, 200 deselected in 0.40s\n"
    )
    lines = report_lines(fake.run("rules/clock.yaml", trigger="pytest", output=output))
    assert lines[1:] == [
        "[rule sync test]",
        "  FAILED tests/unit/test_rules.py::test_rule_sync - AssertionError: rule ids differ",
        FOOTER,
    ]


@pytest.mark.parametrize(
    ("relative", "trigger", "label"),
    [
        (f"{WEB}/templates/base.html", "scripts/design_lint.py", "design_lint"),
        ("app/module.py", "check", "ruff check"),
        ("rules/clock.yaml", "pytest", "rule sync test"),
    ],
)
def test_unexpected_exit_code_is_a_one_line_tool_problem(
    fake: FakeUv, relative: str, trigger: str, label: str
) -> None:
    result = fake.run(relative, trigger=trigger, exit_code=3, output="Traceback: boom\nmore\n")
    assert result.returncode == 0
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith(f"post_edit: {label} could not check ")
    assert "exit 3, a tool problem, not blocking" in lines[0]
    assert lines[0].endswith(": Traceback: boom")


def test_ruff_format_failure_is_a_note_and_findings_still_block(fake: FakeUv) -> None:
    result = fake.run("app/module.py", trigger="format", exit_code=2, output="error: parse\n")
    assert result.returncode == 0
    assert result.stderr.splitlines() == [
        f"post_edit: ruff format could not check {os.path.join('app', 'module.py')} "
        "(exit 2, a tool problem, not blocking): error: parse"
    ]
    assert len(fake.calls()) == 2  # ruff check still ran


@pytest.mark.parametrize(("tool", "relative"), [("ruff", "app/m.py"), ("pytest", "rules/a.yaml")])
def test_tool_missing_from_venv_is_skipped_silently(fake: FakeUv, tool: str, relative: str) -> None:
    (fake.root / ".venv" / "bin" / tool).unlink()
    assert_silent_pass(fake.run(relative))
    assert fake.calls() == []


@pytest.mark.parametrize("relative", ["README.md", "docs/PRD.md", "rules/README.txt"])
def test_other_files_run_nothing(fake: FakeUv, relative: str) -> None:
    assert_silent_pass(fake.run(relative))
    assert fake.calls() == []


# ---------------------------------------------------------------- functions
def test_run_command_times_out_and_kills_the_command(load_hook: LoadHook, tmp_path: Path) -> None:
    module = load_hook("post_edit")
    hang = [sys.executable, "-c", "import threading; threading.Event().wait()"]
    done = module.run_command(hang, str(tmp_path), 0.5)
    assert done.returncode is None
    assert done.problem == "timed out after 0.5 s"


def test_run_command_reports_missing_executable(load_hook: LoadHook, tmp_path: Path) -> None:
    module = load_hook("post_edit")
    done = module.run_command([str(tmp_path / "missing")], str(tmp_path), 5.0)
    assert done.started is False
    assert done.problem is not None
    assert done.problem.startswith(f"could not start {tmp_path / 'missing'}")


def test_build_report_shares_40_lines_between_checks(load_hook: LoadHook) -> None:
    module = load_hook("post_edit")
    findings = [(f"check {name}", [f"{name} line {i}" for i in range(30)]) for name in "abc"]
    notes = ["post_edit: note one", "post_edit: note two"]
    lines = module.build_report("app/x.py", findings, notes)
    assert len(lines) == 40
    assert lines[:3] == ["post_edit: checks found problems in app/x.py", *notes]
    assert lines[-1] == FOOTER
    for name in "abc":
        assert f"[check {name}]" in lines
        assert f"  {name} line 0" in lines
        assert f"  {name} line 29" not in lines
    assert sum("more lines" in line for line in lines) == 3


def test_build_report_keeps_short_output_whole(load_hook: LoadHook) -> None:
    module = load_hook("post_edit")
    lines = module.build_report("a.py", [("ruff check", ["a.py:1:1: F821 x"])], [])
    assert lines == [
        "post_edit: checks found problems in a.py",
        "[ruff check]",
        "  a.py:1:1: F821 x",
        FOOTER,
    ]
