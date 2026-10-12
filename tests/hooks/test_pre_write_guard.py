"""Tests for scripts/hooks/pre_write_guard.py (docs/planning/CLAUDE_CODE_PROMPT.md, A.1).

The live guard scans this file when it is written, so it holds no secret and no 12-digit
number: secrets are assembled from pieces, and every Aadhaar-like number is a synthetic value
generated at run time with a Verhoeff implementation written here from the D5 group
formulas, independent of the tables in the script under test.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from .conftest import LoadHook, RunHook

pytestmark = pytest.mark.unit

MESSAGE = re.compile(r"^Blocked by pre_write_guard (G[1-5]): (.+)\. Fix: (.+)\.$")
DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


# ---------------------------------------------------------------- independent Verhoeff
def d5(j: int, k: int) -> int:
    """Multiply j and k in the dihedral group D5 (elements 0-4 rotations, 5-9 reflections)."""
    if j < 5 and k < 5:
        return (j + k) % 5
    if j < 5:
        return (j + k) % 5 + 5
    if k < 5:
        return (j - k) % 5 + 5
    return (j - k) % 5


BASE_PERMUTATION = (1, 5, 7, 6, 2, 8, 3, 0, 9, 4)


def permute(position: int, digit: int) -> int:
    """Apply the Verhoeff base permutation (position mod 8) times."""
    for _ in range(position % 8):
        digit = BASE_PERMUTATION[digit]
    return digit


def inverse(j: int) -> int:
    """Return the D5 inverse of j."""
    return (5 - j) % 5 if j < 5 else j


def check_digit(prefix: str) -> int:
    """Return the Verhoeff check digit for a string of digits."""
    check = 0
    for position, char in enumerate(reversed(prefix)):
        check = d5(check, permute(position + 1, int(char)))
    return inverse(check)


def synthetic_number(prefix11: str) -> str:
    """Return a synthetic 12-digit number: 11 digits plus a valid Verhoeff check digit."""
    assert len(prefix11) == 11
    return prefix11 + str(check_digit(prefix11))


def broken_number(prefix11: str) -> str:
    """Return the same synthetic number with a wrong check digit."""
    return prefix11 + str((check_digit(prefix11) + 1) % 10)


def grouped(number: str, separator: str) -> str:
    """Group a 12-digit number 4-4-4."""
    return separator.join((number[:4], number[4:8], number[8:]))


# ---------------------------------------------------------------- helpers
@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


def write(file_path: str, content: str) -> dict[str, object]:
    return {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}


def edit(file_path: str, new_string: str) -> dict[str, object]:
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": "placeholder",
            "new_string": new_string,
        },
    }


def guard(run_hook: RunHook, project: Path, payload: object) -> subprocess.CompletedProcess[str]:
    return run_hook("pre_write_guard", payload, project=project, cwd=project)


def assert_blocked(result: subprocess.CompletedProcess[str], rule: str) -> str:
    """Assert a block by the rule with the exact message format; return the message."""
    assert result.returncode == 2, result.stderr
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert len(lines) == 1, result.stderr
    match = MESSAGE.match(lines[0])
    assert match is not None, lines[0]
    assert match.group(1) == rule, lines[0]
    return lines[0]


def assert_allowed(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout == ""


# ---------------------------------------------------------------- G1: outside the project
def test_g1_blocks_absolute_path_outside_project(
    run_hook: RunHook, project: Path, tmp_path: Path
) -> None:
    message = assert_blocked(
        guard(run_hook, project, write(str(tmp_path / "outside.txt"), "hello")), "G1"
    )
    assert "outside the project directory" in message
    assert ".scratch/" in message


def test_g1_blocks_relative_path_that_climbs_out(run_hook: RunHook, project: Path) -> None:
    assert_blocked(guard(run_hook, project, write("docs/../../outside.txt", "hello")), "G1")


def test_g1_blocks_symlink_that_points_outside(
    run_hook: RunHook, project: Path, tmp_path: Path
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (project / "link").symlink_to(elsewhere, target_is_directory=True)
    assert_blocked(guard(run_hook, project, write("link/file.txt", "hello")), "G1")


@pytest.mark.parametrize("relative", [".scratch/guard_notes.txt", "docs/notes.md", "README.md"])
def test_g1_allows_paths_inside_project(run_hook: RunHook, project: Path, relative: str) -> None:
    assert_allowed(guard(run_hook, project, write(relative, "hello")))
    assert_allowed(guard(run_hook, project, write(str(project / relative), "hello")))


def test_project_dir_falls_back_to_cwd_field(
    run_hook: RunHook, project: Path, tmp_path: Path
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    inside = write(str(project / "notes.txt"), "hello") | {"cwd": str(project)}
    outside = write(str(elsewhere / "notes.txt"), "hello") | {"cwd": str(project)}
    assert_allowed(run_hook("pre_write_guard", inside, project=None, cwd=elsewhere))
    assert_blocked(run_hook("pre_write_guard", outside, project=None, cwd=elsewhere), "G1")


def test_project_dir_falls_back_to_current_directory(
    run_hook: RunHook, project: Path, tmp_path: Path
) -> None:
    assert_allowed(run_hook("pre_write_guard", write("notes.txt", "hi"), project=None, cwd=project))
    outside = write(str(tmp_path / "notes.txt"), "hi")
    assert_blocked(run_hook("pre_write_guard", outside, project=None, cwd=project), "G1")


# ---------------------------------------------------------------- G2: .env files
@pytest.mark.parametrize(
    "relative", [".env", ".env.local", "config/.env", "packages/munim_web/.env.production"]
)
def test_g2_blocks_env_files(run_hook: RunHook, project: Path, relative: str) -> None:
    message = assert_blocked(guard(run_hook, project, write(relative, "MUNIM_MODE=demo")), "G2")
    assert ".env.example" in message


@pytest.mark.parametrize("relative", [".env.example", ".envrc", "docs/env.md"])
def test_g2_allows_env_example_and_lookalikes(
    run_hook: RunHook, project: Path, relative: str
) -> None:
    assert_allowed(guard(run_hook, project, write(relative, "MUNIM_MODE=demo")))


# ---------------------------------------------------------------- G3: protected locations
@pytest.mark.parametrize(
    ("relative", "location"),
    [
        ("data/x", "data/"),
        ("data/munim.sqlite3", "data/"),
        ("eval/real/x", "eval/real/"),
        ("eval/real/invoice_01.json", "eval/real/"),
        (".git/config", ".git/"),
        (".git/hooks/pre-commit", ".git/"),
    ],
)
def test_g3_blocks_protected_paths(
    run_hook: RunHook, project: Path, relative: str, location: str
) -> None:
    message = assert_blocked(guard(run_hook, project, write(relative, "hello")), "G3")
    assert f"under {location}," in message


@pytest.mark.parametrize(
    "relative",
    ["eval/fixtures/invoice_01.json", "database.py", "docs/data/notes.md", "eval/realistic.md"],
)
def test_g3_allows_other_paths(run_hook: RunHook, project: Path, relative: str) -> None:
    assert_allowed(guard(run_hook, project, write(relative, "hello")))


def test_g3_applies_after_resolving_symlinks(run_hook: RunHook, project: Path) -> None:
    (project / "data").mkdir()
    (project / "shortcut").symlink_to(project / "data", target_is_directory=True)
    assert_blocked(guard(run_hook, project, write("shortcut/x.txt", "hello")), "G3")


# ---------------------------------------------------------------- G4: secrets
SECRETS = {
    "google-api-key": "AIza" + "x" * 35,
    "private-key": "-----BEGIN RSA PRIVATE" + " KEY-----",
    "github-token": "ghp_" + "x" * 36,
    "sk-key": "sk-" + "x" * 24,
}


@pytest.mark.parametrize("kind", sorted(SECRETS))
def test_g4_blocks_each_secret_pattern_without_echoing_it(
    run_hook: RunHook, project: Path, kind: str
) -> None:
    secret = SECRETS[kind]
    message = assert_blocked(
        guard(run_hook, project, write("src/config.py", f"KEY = '{secret}'\n")), "G4"
    )
    assert secret not in message
    assert "x" * 20 not in message
    assert "line 1 of the new text" in message


def test_g4_blocks_secret_in_edit_and_reports_its_line(run_hook: RunHook, project: Path) -> None:
    new_string = "first = 1\nsecond = 2\nKEY = '" + SECRETS["github-token"] + "'\n"
    message = assert_blocked(guard(run_hook, project, edit("src/config.py", new_string)), "G4")
    assert "line 3 of the new text" in message
    assert SECRETS["github-token"] not in message


@pytest.mark.parametrize(
    "text",
    [
        "AIza" + "x" * 34,
        "ghp_" + "x" * 35,
        "sk-" + "x" * 19,
        "-----BEGIN PUBLIC KEY-----",
        "GEMINI_API_KEY=<GEMINI_API_KEY>",
    ],
)
def test_g4_allows_near_misses(run_hook: RunHook, project: Path, text: str) -> None:
    assert_allowed(guard(run_hook, project, write("docs/notes.md", text)))


# ---------------------------------------------------------------- G5: Aadhaar-like numbers
def test_independent_verhoeff_matches_published_example() -> None:
    # The textbook example: the check digit for 236 is 3.
    assert check_digit("236") == 3


def test_guard_verhoeff_tables_match_d5_formulas(load_hook: LoadHook) -> None:
    module = load_hook("pre_write_guard")
    assert tuple(tuple(d5(j, k) for k in range(10)) for j in range(10)) == module.VERHOEFF_D
    assert tuple(tuple(permute(i, k) for k in range(10)) for i in range(8)) == module.VERHOEFF_P
    assert tuple(inverse(j) for j in range(10)) == module.VERHOEFF_INV


def test_guard_verhoeff_functions_agree_with_independent_ones(load_hook: LoadHook) -> None:
    module = load_hook("pre_write_guard")
    assert module.verhoeff_check_digit([2, 3, 6]) == 3
    assert module.verhoeff_valid([2, 3, 6, 3])
    assert not module.verhoeff_valid([2, 3, 6, 4])
    for step in range(1, 201):
        prefix = f"{(step * 7_919_191_919) % 10**11:011d}"
        digits = [int(char) for char in prefix]
        assert module.verhoeff_check_digit(digits) == check_digit(prefix)
        assert module.verhoeff_valid([int(char) for char in synthetic_number(prefix)])
        assert not module.verhoeff_valid([int(char) for char in broken_number(prefix)])


@pytest.mark.parametrize("prefix", ["23456789012", "98765432101", "50000000000"])
def test_g5_blocks_verhoeff_valid_number(run_hook: RunHook, project: Path, prefix: str) -> None:
    number = synthetic_number(prefix)
    message = assert_blocked(
        guard(run_hook, project, write("docs/notes.md", f"Customer id: {number}\n")), "G5"
    )
    assert number not in message
    assert "line 1 of the new text" in message


@pytest.mark.parametrize("separator", [" ", "-"])
def test_g5_blocks_grouped_number(run_hook: RunHook, project: Path, separator: str) -> None:
    text = f"Card: {grouped(synthetic_number('34567890123'), separator)}.\n"
    assert_blocked(guard(run_hook, project, write("docs/notes.md", text)), "G5")


def test_g5_blocks_number_in_devanagari_digits(run_hook: RunHook, project: Path) -> None:
    number = synthetic_number("45678901234").translate(DEVANAGARI_DIGITS)
    assert_blocked(guard(run_hook, project, write("docs/notes.md", f"{number}\n")), "G5")


def test_g5_finds_valid_number_overlapping_an_invalid_one(run_hook: RunHook, project: Path) -> None:
    valid = synthetic_number("67890123456")
    lead = next(
        group
        for group in ("2345", "2346", "2347")
        if not check_digit_valid(group + valid[:8])  # the earlier candidate must fail
    )
    text = f"{lead} {grouped(valid, ' ')}\n"
    assert_blocked(guard(run_hook, project, write("docs/notes.md", text)), "G5")


def check_digit_valid(number: str) -> bool:
    return check_digit(number[:-1]) == int(number[-1])


@pytest.mark.parametrize("folder", ["tests/unit", "eval/fixtures"])
def test_g5_allows_synthetic_number_in_tests_and_fixtures(
    run_hook: RunHook, project: Path, folder: str
) -> None:
    number = synthetic_number("23456789012")
    text = f"AADHAAR = '{number}'  # Synthetic test value\n"
    assert_allowed(guard(run_hook, project, write(f"{folder}/test_mask.py", text)))


def test_g5_needs_synthetic_on_the_same_line(run_hook: RunHook, project: Path) -> None:
    number = synthetic_number("23456789012")
    text = f"# synthetic values below\nAADHAAR = '{number}'\n"
    message = assert_blocked(guard(run_hook, project, write("tests/unit/test_mask.py", text)), "G5")
    assert "line 2 of the new text" in message


def test_g5_synthetic_exception_applies_only_under_tests_and_fixtures(
    run_hook: RunHook, project: Path
) -> None:
    number = synthetic_number("23456789012")
    text = f"AADHAAR = '{number}'  # synthetic\n"
    assert_blocked(guard(run_hook, project, write("docs/testing_notes.md", text)), "G5")
    assert_blocked(guard(run_hook, project, write("eval/real_tests/x.py", text)), "G5")


def test_g5_allows_verhoeff_invalid_number(run_hook: RunHook, project: Path) -> None:
    text = f"Order: {broken_number('23456789012')}\n"
    assert_allowed(guard(run_hook, project, write("docs/notes.md", text)))


@pytest.mark.parametrize("first_digit", ["0", "1"])
def test_g5_allows_number_starting_with_0_or_1(
    run_hook: RunHook, project: Path, first_digit: str
) -> None:
    number = synthetic_number(first_digit + "2345678901")
    assert_allowed(guard(run_hook, project, write("docs/notes.md", f"Ref {number}\n")))


def test_g5_allows_13_digit_run(run_hook: RunHook, project: Path) -> None:
    number = synthetic_number("23456789012")
    assert_allowed(guard(run_hook, project, write("docs/notes.md", f"Ref {number}7\n")))
    assert_allowed(guard(run_hook, project, write("docs/notes.md", f"Ref 7{number}\n")))


# ---------------------------------------------------------------- MultiEdit and input handling
def test_multiedit_new_strings_are_checked(run_hook: RunHook, project: Path) -> None:
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "src/config.py",
            "edits": [
                {"old_string": "a = 1", "new_string": "a = 2"},
                {"old_string": "KEY = ''", "new_string": f"KEY = '{SECRETS['sk-key']}'"},
            ],
        },
    }
    message = assert_blocked(guard(run_hook, project, payload), "G4")
    assert "line 2 of the new text" in message


def test_multiedit_clean_edits_are_allowed(run_hook: RunHook, project: Path) -> None:
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "src/config.py",
            "edits": [
                {"old_string": "a = 1", "new_string": "a = 2"},
                {"old_string": "b = 1", "new_string": "b = 2"},
            ],
        },
    }
    assert_allowed(guard(run_hook, project, payload))


def test_path_rules_apply_before_content_rules(run_hook: RunHook, project: Path) -> None:
    assert_blocked(guard(run_hook, project, write(".env", SECRETS["google-api-key"])), "G2")


@pytest.mark.parametrize("raw", ["{not json", "", "[1, 2]", '"text"'])
def test_malformed_input_is_not_blocked_and_leaves_a_note(
    run_hook: RunHook, project: Path, raw: str
) -> None:
    result = run_hook("pre_write_guard", raw, project=project, cwd=project)
    assert result.returncode == 0
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("pre_write_guard: the hook input is not")
    assert lines[0].endswith("nothing checked.")


def test_input_without_tool_input_is_allowed(run_hook: RunHook, project: Path) -> None:
    assert_allowed(guard(run_hook, project, {"tool_name": "Write"}))
