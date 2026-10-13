"""Strings in English and Hindi (docs/CONTENT.md) and the display formatting of values.

Findings from the core carry a message key and string params. Params are formatted here by
their name: `*_paise` as rupees with Indian grouping, `*_date` as a date in words, `*_key` as
another translated string. Everything else is shown as given (it is text from a paper and is
autoescaped by Jinja).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from functools import cache
from importlib import resources

from munim_core.money import format_inr

__all__ = ["LANGS", "Translator", "format_date", "strings", "translator"]

LANGS = ("en", "hi")
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


@cache
def strings(lang: str) -> dict[str, str]:
    raw = resources.files("munim_web.i18n").joinpath(f"{lang}.json").read_text(encoding="utf-8")
    data: dict[str, str] = json.loads(raw)
    return data


def format_date(value: date, lang: str = "en") -> str:
    month = strings(lang).get(f"month.{value.month}") or strings("en")[f"month.{value.month}"]
    return f"{value.day:02d} {month} {value.year}"


class Translator:
    """`t(key, **params)` for one language. Missing keys show as ⟦key⟧ in development."""

    def __init__(self, lang: str, *, dev: bool = False) -> None:
        self.lang = lang if lang in LANGS else "en"
        self.dev = dev

    def raw(self, key: str) -> str:
        text = strings(self.lang).get(key)
        if text is None:
            if self.dev:
                return f"⟦{key}⟧"
            text = strings("en").get(key, key)
        return text

    def param(self, name: str, value: object) -> str:
        if value is None:
            return ""
        if name.endswith("_paise"):
            return format_inr(int(str(value)))
        if name.endswith("_date") and isinstance(value, str | date):
            try:
                day = value if isinstance(value, date) else date.fromisoformat(value)
            except ValueError:
                return str(value)
            return format_date(day, self.lang)
        if name.endswith("_key"):
            return self.raw(str(value))
        return str(value)

    def __call__(self, key: str, params: Mapping[str, object] | None = None, **kw: object) -> str:
        values = {**(params or {}), **kw}
        text = self.raw(key)
        formatted: dict[str, str] = {}
        for name, value in values.items():
            formatted[name] = self.param(name, value)
            # A template may name a param without its type suffix: {computed} for computed_paise.
            for suffix in ("_paise", "_date", "_key"):
                if name.endswith(suffix):
                    formatted.setdefault(name[: -len(suffix)], formatted[name])
        return _PLACEHOLDER.sub(lambda m: formatted.get(m.group(1), m.group(0)), text)

    def date(self, value: date | str | None) -> str:
        if value is None or value == "":
            return ""
        return self.param("x_date", value)

    def money(self, paise: int | None) -> str:
        return "" if paise is None else format_inr(paise)


@cache
def translator(lang: str, dev: bool = False) -> Translator:
    return Translator(lang, dev=dev)
