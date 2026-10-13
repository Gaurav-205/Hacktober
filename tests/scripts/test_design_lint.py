"""Tests for scripts/design_lint.py (DESIGN.md section 12, rules 1 to 9).

Every rule has failing and passing samples. A failing sample asserts the exact
file, line and rule number printed; a passing sample asserts exit 0 and no
finding. Files are written under ``tmp_path`` and linted with ``--root tmp_path``
so that paths print relative to it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from .conftest import load_script, run_script

pytestmark = pytest.mark.unit

FINDING_RE = re.compile(r"^(.+?):(\d+): rule (\d) \(DESIGN\.md section 7\): (.+)$")
WEB = "packages/munim_web/src/munim_web"
DEFAULT_ROOTS = ("templates", "static/css", "static/js", "i18n")


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

    @property
    def findings(self) -> list[tuple[str, int, int]]:
        """(file, line, rule) of every finding line."""
        found = []
        for line in self.out.splitlines():
            match = FINDING_RE.match(line)
            assert match, f"unexpected output line: {line!r}"
            found.append((match.group(1), int(match.group(2)), int(match.group(3))))
        return found

    @property
    def messages(self) -> list[str]:
        return [m.group(4) for m in map(FINDING_RE.match, self.out.splitlines()) if m]


Lint = Callable[[str, str], Result]


@pytest.fixture
def lint(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Lint:
    """Write ``text`` to ``tmp_path / rel`` and lint that one file in-process."""
    module = load_script("design_lint")

    def run(rel: str, text: str) -> Result:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        code = module.main(["--root", str(tmp_path), str(path)])
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return run


def assert_clean(result: Result, files: int = 1) -> None:
    assert result.code == 0, result.out
    assert result.out == ""
    assert f"design_lint: {files} files checked, 0 problems" in result.err


def css_rule(*declarations: str, selector: str = ".panel") -> str:
    """A rule block whose declarations start on line 2."""
    body = "".join(f"  {declaration}\n" for declaration in declarations)
    return f"{selector} {{\n{body}}}\n"


# ------------------------------------------------------------------ rule 1: hex colours
def test_hex_colours_in_css_values_fail(lint: Lint) -> None:
    result = lint("static/css/app.css", css_rule("color: #fff;", "background: #1F3DB8cc;"))

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 2, 1), ("static/css/app.css", 3, 1)]
    assert "raw hex colour #fff; use a colour token" in result.messages[0]
    assert "raw hex colour #1F3DB8cc" in result.messages[1]


def test_id_selectors_and_href_attribute_selectors_are_not_colours(lint: Lint) -> None:
    css = (
        css_rule("color: var(--color-ink);", selector="#main")
        + css_rule("color: var(--color-ballpoint);", selector='#add, a[href="#add"]')
        + css_rule("fill: url(#bad);", selector="#fed .icon")
    )

    assert_clean(lint("static/css/app.css", css))


def test_hex_is_allowed_inside_tokens_css_only(lint: Lint) -> None:
    tokens = ":root {\n  --color-ink: #15171C;\n  --color-sheet: #FFFFFF;\n}\n"

    assert_clean(lint("static/css/tokens.css", tokens))
    result = lint("static/css/app.css", tokens)
    assert result.code == 1
    assert result.findings == [("static/css/app.css", 2, 1), ("static/css/app.css", 3, 1)]


def test_hex_in_svg_colour_attribute_or_style_attribute_fails(lint: Lint) -> None:
    template = (
        '<svg viewBox="0 0 16 16">\n'
        '  <path fill="#1F3DB8" d="M0 0h16"/>\n'
        '  <rect style="stroke: #000" width="4"/>\n'
        "</svg>\n"
    )

    result = lint("templates/components/icons.html", template)

    assert result.code == 1
    assert result.findings == [
        ("templates/components/icons.html", 2, 1),
        ("templates/components/icons.html", 3, 1),
    ]
    assert "raw hex colour #1F3DB8 in fill=" in result.messages[0]


def test_href_fragment_and_current_color_in_templates_are_not_colours(lint: Lint) -> None:
    template = (
        '<a href="#add">{{ t("paper.add") }}</a>\n'
        '<svg><path fill="currentColor" stroke="url(#bad)" d="M0 0"/></svg>\n'
        '<p id="ace">{{ t("case.none") }}</p>\n'
    )

    assert_clean(lint("templates/cases.html", template))


def test_hex_in_a_javascript_string_fails_but_not_in_a_comment(lint: Lint) -> None:
    result = lint(
        "static/js/viewer.js",
        '// the old colour was #ffffff\nconst accent = "#1f3db8";\nlocation.hash = "#add";\n',
    )

    assert result.code == 1
    assert result.findings == [("static/js/viewer.js", 2, 1)]
    assert "raw hex colour #1f3db8" in result.messages[0]


# ------------------------------------------------------------------ rule 2: shadows, gradients
@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ("box-shadow: 0 1px 2px var(--color-ink);", "box-shadow is not allowed"),
        ("text-shadow: 0 0 1px var(--color-ink);", "text-shadow is not allowed"),
        ("backdrop-filter: blur(4px);", "backdrop-filter is not allowed"),
        ("filter: drop-shadow(0 1px 1px var(--color-ink));", "drop-shadow() is not allowed"),
        (
            "background: linear-gradient(var(--color-bond), var(--color-sheet));",
            "linear-gradient() is not allowed",
        ),
        (
            "background-image: radial-gradient(var(--color-bond), var(--color-sheet));",
            "radial-gradient() is not allowed",
        ),
        (
            "background: conic-gradient(var(--color-bond), var(--color-sheet));",
            "conic-gradient() is not allowed",
        ),
    ],
)
def test_shadows_blurs_and_gradients_fail(lint: Lint, declaration: str, message: str) -> None:
    result = lint("static/css/app.css", css_rule(declaration))

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 2, 2)]
    assert message in result.messages[0]


def test_box_shadow_marked_as_focus_ring_on_the_same_line_passes(lint: Lint) -> None:
    css = css_rule(
        "box-shadow: 0 0 0 2px var(--color-ballpoint); /* focus-ring */",
        selector=".button:focus-visible",
    ) + css_rule("box-shadow: none;")

    assert_clean(lint("static/css/app.css", css))


def test_focus_ring_marker_on_another_line_does_not_excuse_a_shadow(lint: Lint) -> None:
    css = css_rule("/* focus-ring */", "box-shadow: 0 0 0 2px var(--color-ballpoint);")

    result = lint("static/css/app.css", css)

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 3, 2)]


# ------------------------------------------------------------------ rule 3: radii
@pytest.mark.parametrize(
    "value", ["6px", "0", "2px 6px 0 0", "var(--radius-panel)", "0.375rem", "6px !important"]
)
def test_radius_up_to_six_pixels_passes(lint: Lint, value: str) -> None:
    assert_clean(lint("static/css/app.css", css_rule(f"border-radius: {value};")))


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ("border-radius: 8px;", "border-radius 8px is above 6px"),
        ("border-radius: 0.5rem;", "border-radius 0.5rem is above 6px"),
        ("border-radius: 50%;", "border-radius 50% is a percentage; no circles or pills"),
        ("border-radius: 9999px;", "border-radius 9999px makes a pill"),
        ("border-top-left-radius: 2px 12px;", "border-radius 12px is above 6px"),
    ],
)
def test_radius_above_six_pixels_or_round_fails(lint: Lint, declaration: str, message: str) -> None:
    result = lint("static/css/app.css", css_rule(declaration))

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 2, 3)]
    assert message in result.messages[0]


# ------------------------------------------------------------------ rule 4: case and tracking
def test_uppercase_outside_the_stamp_fails(lint: Lint) -> None:
    result = lint("static/css/app.css", css_rule("text-transform: uppercase;", selector=".label"))

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 2, 4)]
    assert "text-transform: uppercase is allowed only inside .stamp" in result.messages[0]


def test_uppercase_inside_the_stamp_selector_passes(lint: Lint) -> None:
    css = css_rule("text-transform: uppercase;", selector=".stamp") + css_rule(
        "text-transform: uppercase;", selector=".dossier .stamp text"
    )

    assert_clean(lint("static/css/app.css", css))


@pytest.mark.parametrize("selector", [".stamped-row", ".stamp-like", ".stamp_word"])
def test_uppercase_in_a_class_that_only_starts_with_stamp_fails(lint: Lint, selector: str) -> None:
    result = lint("static/css/app.css", css_rule("text-transform: uppercase;", selector=selector))

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 2, 4)]


@pytest.mark.parametrize(
    "selector",
    [".stamp, .label", ".label,\n.stamp", ":not(.stamp)", ".row:not(.stamp) .cell"],
    ids=["list-stamp-first", "list-stamp-last", "not-stamp", "not-stamp-descendant"],
)
def test_uppercase_reaching_beyond_the_stamp_fails(lint: Lint, selector: str) -> None:
    result = lint("static/css/app.css", css_rule("text-transform: uppercase;", selector=selector))

    assert result.code == 1
    assert [rule for _, _, rule in result.findings] == [4]


@pytest.mark.parametrize(
    "selector",
    [".stamp, .dossier .stamp", ".stamp:not(.draft)", ".stamp text, .stamp tspan"],
)
def test_uppercase_in_a_selector_list_that_is_all_stamp_passes(lint: Lint, selector: str) -> None:
    assert_clean(
        lint("static/css/app.css", css_rule("text-transform: uppercase;", selector=selector))
    )


def test_uppercase_nested_inside_a_stamp_rule_passes(lint: Lint) -> None:
    css = ".stamp {\n  & .word {\n    text-transform: uppercase;\n  }\n}\n"

    assert_clean(lint("static/css/app.css", css))


@pytest.mark.parametrize("value", ["0.02em", "-0.01em", "0", "normal", "0.3px"])
def test_letter_spacing_up_to_two_hundredths_em_passes(lint: Lint, value: str) -> None:
    assert_clean(lint("static/css/app.css", css_rule(f"letter-spacing: {value};")))


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("0.05em", "letter-spacing 0.05em is above 0.02em"),
        ("1px", "letter-spacing 1px is above 0.02em"),
        ("0.1ch", "letter-spacing 0.1ch uses 'ch'"),
    ],
)
def test_letter_spacing_above_two_hundredths_em_fails(lint: Lint, value: str, message: str) -> None:
    result = lint("static/css/app.css", css_rule(f"letter-spacing: {value};"))

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 2, 4)]
    assert message in result.messages[0]


# ------------------------------------------------------------------ rule 5: emoji, arrows, dashes
@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("Open evidence file →", "arrow or arrow-like symbol → (U+2192)"),
        ("Invoice — challan", "em dash (U+2014) is not allowed"),
        ("All done \U0001f389", "emoji or pictograph U+1F389"),
        ("✨ New case", "emoji or pictograph U+2728"),
        ("Invoice · challan", "used as a separator"),
    ],
)
def test_emoji_arrows_and_dashes_in_i18n_values_fail(lint: Lint, value: str, message: str) -> None:
    text = '{\n  "case.new": "New case",\n  "case.bad": "' + value + '"\n}\n'

    result = lint("i18n/en.json", text)

    assert result.code == 1
    assert result.findings == [("i18n/en.json", 3, 5)]
    assert message in result.messages[0]


def test_plain_i18n_values_and_keys_pass(lint: Lint) -> None:
    text = (
        "{\n"
        '  "case.new": "New case",\n'
        '  "paper.checked": "Paper checked, 3 of 3 checks passed",\n'
        '  "paper.checked.hi": "कागज़ जाँचा",\n'
        '  "range": "1 to 3: dates in DD/MM/YYYY"\n'
        "}\n"
    )

    assert_clean(lint("i18n/hi.json", text))


def test_arrow_in_template_text_fails(lint: Lint) -> None:
    template = '<a href="/rules">\n  {{ t("rules.link") }} →\n</a>\n'

    result = lint("templates/rules.html", template)

    assert result.code == 1
    assert result.findings == [("templates/rules.html", 2, 5)]


def test_arrow_written_as_an_html_entity_fails(lint: Lint) -> None:
    result = lint("templates/rules.html", '<a href="/rules">{{ t("rules.link") }} &rarr;</a>\n')

    assert result.code == 1
    assert result.findings == [("templates/rules.html", 1, 5)]
    assert "(written as &rarr;)" in result.messages[0]


# ------------------------------------------------------------------ rule 6: font families
@pytest.mark.parametrize(
    ("declaration", "family"),
    [
        ("font-family: monospace;", "monospace"),
        ("font-family: var(--font-ui), Arial;", "Arial"),
        ('font: 14px/1.4 "Courier New", var(--font-ui);', '"Courier New"'),
    ],
)
def test_undeclared_font_families_fail(lint: Lint, declaration: str, family: str) -> None:
    result = lint("static/css/app.css", css_rule(declaration, selector=".code"))

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 2, 6)]
    assert f"font family {family} is not declared" in result.messages[0]


@pytest.mark.parametrize(
    "declaration",
    [
        "font-family: var(--font-ui);",
        "font-family: var(--font-hand);",
        "font-family: Mukta, 'Noto Sans Devanagari', system-ui, sans-serif;",
        "font: 600 var(--type-h1-size)/var(--type-h1-line) var(--font-ui);",
        "font: inherit;",
    ],
)
def test_declared_font_families_pass(lint: Lint, declaration: str) -> None:
    assert_clean(lint("static/css/app.css", css_rule(declaration)))


# ------------------------------------------------------------------ rule 7: lang on Devanagari
def test_devanagari_on_a_line_with_lang_hi_passes(lint: Lint) -> None:
    template = '<p lang="hi">मुनीम</p>\n'

    assert_clean(lint("templates/about.html", template))


def test_devanagari_without_lang_hi_fails(lint: Lint) -> None:
    template = '<p lang="hi">{{ t("about.name") }}</p>\n<p>मुनीम</p>\n'

    result = lint("templates/about.html", template)

    assert result.code == 1
    assert result.findings == [("templates/about.html", 2, 7)]
    assert 'Devanagari text outside an element with lang="hi"' in result.messages[0]


def test_devanagari_inside_a_multi_line_lang_hi_element_passes(lint: Lint) -> None:
    template = '<section lang="hi">\n  <h2>\n    मुनीम\n  </h2>\n</section>\n'

    assert_clean(lint("templates/about.html", template))


def test_devanagari_after_the_lang_hi_element_closes_fails(lint: Lint) -> None:
    template = '<p lang="hi">मुनीम</p><p>मुनीम</p>\n'

    result = lint("templates/about.html", template)

    assert result.code == 1
    assert result.findings == [("templates/about.html", 1, 7)]


def test_devanagari_in_a_lang_en_child_of_a_lang_hi_parent_fails(lint: Lint) -> None:
    template = '<div lang="hi">\n  <p lang="en">\n    मुनीम\n  </p>\n</div>\n'

    result = lint("templates/about.html", template)

    assert result.code == 1
    assert result.findings == [("templates/about.html", 3, 7)]


def test_devanagari_in_an_attribute_follows_its_own_element_lang(lint: Lint) -> None:
    good = '<img lang="hi" alt="मुनीम" src="x.png">\n'
    bad = '<img alt="मुनीम" src="x.png">\n'

    assert_clean(lint("templates/good.html", good))
    result = lint("templates/bad.html", bad)
    assert result.findings == [("templates/bad.html", 1, 7)]


def test_void_elements_do_not_hold_lang_open(lint: Lint) -> None:
    template = '<div>\n  <input lang="hi" name="x">\n  <p>मुनीम</p>\n</div>\n'

    result = lint("templates/about.html", template)

    assert result.findings == [("templates/about.html", 3, 7)]


# ------------------------------------------------------------------ rule 8: entrance motion
FADE_AND_SLIDE = """\
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
"""

STAMP_LANDS = """\
@keyframes stamp-land {
  from { transform: scale(1.18) rotate(-4deg); }
  to { transform: scale(1) rotate(-2deg); }
}
"""


def test_keyframes_animating_opacity_with_translate_fail(lint: Lint) -> None:
    result = lint("static/css/app.css", STAMP_LANDS + FADE_AND_SLIDE)

    assert result.code == 1
    assert result.findings == [("static/css/app.css", 5, 8)]
    assert "'@keyframes rise' animates opacity together with translate" in result.messages[0]


def test_keyframes_without_a_fade_and_slide_pass(lint: Lint) -> None:
    assert_clean(lint("static/css/app.css", STAMP_LANDS))


def test_scroll_driven_animation_fails(lint: Lint) -> None:
    result = lint("static/css/app.css", css_rule("animation-timeline: scroll();"))

    assert result.code == 1
    assert sorted(set(result.findings)) == [("static/css/app.css", 2, 8)]
    assert any("animation-timeline (scroll-driven animation)" in m for m in result.messages)


def test_intersection_observer_in_first_party_js_fails(lint: Lint) -> None:
    js = "// reveal sections\nconst seen = new IntersectionObserver(show);\n"

    result = lint("static/js/reveal.js", js)

    assert result.code == 1
    assert result.findings == [("static/js/reveal.js", 2, 8)]
    assert "IntersectionObserver" in result.messages[0]


def test_intersection_observer_named_only_in_a_comment_passes(lint: Lint) -> None:
    assert_clean(lint("static/js/viewer.js", "// no IntersectionObserver here\nexport {};\n"))


def test_vendored_js_is_skipped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = load_script("design_lint")
    js = tmp_path / "static" / "js"
    (js / "vendor").mkdir(parents=True)
    (js / "vendor" / "lib.min.js").write_text(
        'new IntersectionObserver(f);el.style.color="#ff0000";\n', encoding="utf-8"
    )
    (js / "viewer.js").write_text("export const zoom = 1;\n", encoding="utf-8")

    code = module.main(["--root", str(tmp_path), str(js)])
    direct = module.main(["--root", str(tmp_path), str(js / "vendor" / "lib.min.js")])
    captured = capsys.readouterr()

    assert (code, direct) == (0, 0)
    assert captured.out == ""
    assert "design_lint: 1 files checked, 0 problems" in captured.err
    assert "design_lint: 0 files checked, 0 problems" in captured.err


# ------------------------------------------------------------------ rule 9: banned words
@pytest.mark.parametrize(
    ("value", "word"),
    [
        ("AI-powered reading", "AI-powered"),
        ("A magic fill", "magic"),
        ("A seamless check", "seamless"),
        ("Supercharge your claims", "Supercharge"),
        ("Unlock the file", "Unlock"),
        ("A revolutionary tool", "revolutionary"),
        ("Lorem ipsum", "Lorem"),
        ("Values verified", "verified"),
        ("Verified", "Verified"),
    ],
)
def test_banned_words_in_i18n_values_fail(lint: Lint, value: str, word: str) -> None:
    result = lint("i18n/en.json", '{\n  "x": "' + value + '"\n}\n')

    assert result.code == 1
    assert result.findings == [("i18n/en.json", 2, 9)]
    assert f'banned word "{word}"' in result.messages[0]


def test_verified_message_points_to_passed(lint: Lint) -> None:
    result = lint("i18n/en.json", '{"x": "GSTIN verified"}\n')

    assert result.messages == ['banned word "verified"; Munim says Passed, never Verified']


@pytest.mark.parametrize(
    "value", ["Bank Rate unverified", "Passed", "Doesn't match", "Check by hand"]
)
def test_allowed_words_in_i18n_values_pass(lint: Lint, value: str) -> None:
    assert_clean(lint("i18n/en.json", '{\n  "verified.key.names.are.fine": "' + value + '"\n}\n'))


def test_banned_word_in_visible_template_text_fails(lint: Lint) -> None:
    template = (
        '<div class="magic-box" data-x="seamless">\n'
        "  <p>A seamless check</p>\n"
        '  <img src="/static/x.svg" alt="Magic">\n'
        "</div>\n"
    )

    result = lint("templates/about.html", template)

    assert result.code == 1
    assert result.findings == [("templates/about.html", 2, 9), ("templates/about.html", 3, 9)]


# ------------------------------------------------------------------ roots and exit codes
def make_repo(root: Path, skip: str | None = None) -> Path:
    """A fake repository with the four default scan roots of the web package."""
    for rel in DEFAULT_ROOTS:
        if rel != skip:
            (root / WEB / rel).mkdir(parents=True, exist_ok=True)
    return root


def test_default_roots_are_found_under_root(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / WEB / "static/css/app.css").write_text(css_rule("color: var(--color-ink);"))
    (repo / WEB / "static/js/vendor").mkdir()
    (repo / WEB / "static/js/vendor/htmx.min.js").write_text("new IntersectionObserver(f);\n")

    result = run_script("design_lint", "--root", repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "design_lint: 1 files checked, 0 problems" in result.stderr


def test_findings_under_default_roots_print_paths_relative_to_root(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / WEB / "templates/cases.html").write_text("<p>{{ t('x') }}</p>\n<p>✨</p>\n")

    result = run_script("design_lint", "--root", repo)

    assert result.returncode == 1
    assert result.stdout.startswith(f"{WEB}/templates/cases.html:2: rule 5 (DESIGN.md section 7):")


@pytest.mark.parametrize("missing", DEFAULT_ROOTS)
def test_missing_default_scan_root_is_an_error(tmp_path: Path, missing: str) -> None:
    repo = make_repo(tmp_path, skip=missing)

    result = run_script("design_lint", "--root", repo)

    assert result.returncode == 2
    assert f"design_lint: error: scan root is missing: {WEB}/{missing}" in result.stderr


def test_missing_path_argument_is_an_error(tmp_path: Path) -> None:
    result = run_script("design_lint", tmp_path / "nope.css")

    assert result.returncode == 2
    assert "design_lint: error: no such file or directory:" in result.stderr
    assert "nope.css" in result.stderr


def test_unreadable_file_is_an_error(tmp_path: Path) -> None:
    bad = tmp_path / "static" / "css" / "app.css"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b".a { color: \xff; }\n")

    result = run_script("design_lint", "--root", tmp_path, bad)

    assert result.returncode == 2
    assert "design_lint: error: cannot read" in result.stderr


def test_files_with_other_extensions_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("#ffffff ✨ magic\n", encoding="utf-8")

    result = run_script("design_lint", "--root", tmp_path, tmp_path)

    assert result.returncode == 0
    assert "design_lint: 0 files checked, 0 problems" in result.stderr
