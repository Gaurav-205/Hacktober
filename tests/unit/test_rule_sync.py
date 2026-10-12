"""Rule ids, versions and message keys stay in step across the spec, the data and the code.

docs/DOMAIN_RULES.md (the specification), rules/rules.yaml (shown on the Rules page) and
munim_core.verify.catalog (used by the code) must name the same rules with the same versions.
Every i18n key the core can emit is listed in rules/message_keys.yaml, and from Gate 3 the
language files must define every listed key.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from munim_core.verify.catalog import RULES

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "packages/munim_core/src/munim_core"
I18N = ROOT / "packages/munim_web/src/munim_web/i18n"
# Rules whose findings only ever use a variant key (rule.<ID>.<variant>).
VARIANT_ONLY = {"VALUE-FORMAT", "X-DATE-ORDER"}
KEY_LITERAL = re.compile(
    r"""["']((?:check|rule|term|paper|clock|working|assumption)\.[A-Za-z0-9_.-]+)["']"""
)


def domain_rule_ids() -> set[str]:
    """Ids in the first column of the rule tables of docs/DOMAIN_RULES.md."""
    text = (ROOT / "docs/DOMAIN_RULES.md").read_text(encoding="utf-8")
    ids = set(re.findall(r"^\| `([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)` \|", text, flags=re.M))
    # The clock rule ids are named in section 5 rather than in a table.
    clock = re.search(r"Rule ids: (`CLOCK-[A-Z]+`(?:, `CLOCK-[A-Z]+`)*)", text)
    assert clock, "DOMAIN_RULES.md section 5 must name the clock rule ids"
    ids |= set(re.findall(r"`(CLOCK-[A-Z]+)`", clock.group(1)))
    return ids


def yaml_rules() -> dict[str, dict[str, str]]:
    data = yaml.safe_load((ROOT / "rules/rules.yaml").read_text(encoding="utf-8"))
    return {row["id"]: row for row in data}


def listed_keys() -> set[str]:
    return set(yaml.safe_load((ROOT / "rules/message_keys.yaml").read_text(encoding="utf-8")))


def test_rule_sync_ids_match_across_document_yaml_and_code() -> None:
    assert domain_rule_ids() == set(yaml_rules()) == set(RULES)


def test_rule_sync_versions_match_between_yaml_and_code() -> None:
    assert {k: v["version"] for k, v in yaml_rules().items()} == {
        k: spec.version for k, spec in RULES.items()
    }


def test_rule_sync_every_yaml_row_has_a_source_status_and_date() -> None:
    for rule_id, row in yaml_rules().items():
        assert row["status"] in {"verified", "assumed", "unverified"}, rule_id
        assert row["source"].strip(), rule_id
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["checked_on"]), rule_id


def test_rule_sync_every_key_the_core_can_emit_is_listed() -> None:
    literal = set()
    for path in CORE.rglob("*.py"):
        literal |= set(KEY_LITERAL.findall(path.read_text(encoding="utf-8")))
    dynamic = {
        f"rule.{rid}"
        for rid, spec in RULES.items()
        if spec.runs_in_verify and rid not in VARIANT_ONLY
    }
    dynamic |= {f"working.step.{kind}" for kind in ("month", "partial", "payment")}
    dynamic |= {f"assumption.interest_base.{base}" for base in ("invoice_total", "taxable_total")}
    missing = (literal | dynamic) - listed_keys()
    assert not missing, sorted(missing)


def test_rule_sync_listed_keys_exist_in_both_language_files_once_they_exist() -> None:
    en, hi = I18N / "en.json", I18N / "hi.json"
    if not en.exists():
        pytest.skip("i18n files arrive in Gate 3 (T3.3); until then the key list is the contract")
    for path in (en, hi):
        strings = json.loads(path.read_text(encoding="utf-8"))
        missing = listed_keys() - set(strings)
        assert not missing, (path.name, sorted(missing))
