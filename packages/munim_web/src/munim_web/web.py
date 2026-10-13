"""Rendering helpers shared by the routes: language, CSRF token, translator and templates."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from munim_core.money import format_inr
from munim_web import __version__
from munim_web.security import csrf_cookie_name, csrf_token
from munim_web.settings import Settings
from munim_web.translate import LANGS, translator

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
LANG_COOKIE = "munim_lang"
_CODE = re.compile(r"`([^`]+)`")


def with_code(text: str) -> Markup:
    """Escape the text, then show `backticked` parts as code. Safe: escaping comes first."""
    escaped = str(escape(text))
    return Markup(_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped))  # noqa: S704


def gstin_groups(value: str | None) -> list[str]:
    """A GSTIN in five groups: state, PAN, entity, Z, check (DESIGN.md 3)."""
    if not value or len(value) != 15 or not value.isalnum():
        return [value or ""]
    return [value[:2], value[2:12], value[12], value[13], value[14]]


templates.env.filters["code"] = with_code
templates.env.filters["inr"] = lambda paise: "" if paise is None else format_inr(int(paise))
templates.env.globals["gstin_groups"] = gstin_groups
templates.env.globals["version"] = __version__


def language(request: Request) -> str:
    """Cookie, then the stored setting, then the environment (PLAN_REVIEW D12)."""
    cookie = request.cookies.get(LANG_COOKIE) or ""
    if cookie in LANGS:
        return cookie
    stored = request.app.state.db.setting("language")
    if stored in LANGS:
        return str(stored)
    settings: Settings = request.app.state.settings
    return settings.lang if settings.lang in LANGS else "en"


def render(request: Request, name: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    settings: Settings = request.app.state.settings
    lang = language(request)
    t = translator(lang, settings.dev)
    choice = request.app.state.papers.choice()
    response = templates.TemplateResponse(
        request,
        name,
        {
            "t": t,
            "lang": lang,
            "csrf": csrf_token(request),
            "provider_name": choice.name,
            "path": request.url.path,
            "fix_params": {"url": settings.ollama_url, "model": settings.ollama_model},
            **context,
        },
        status_code=status_code,
    )
    set_csrf_cookie(request, response)
    return response


def set_csrf_cookie(request: Request, response: Any) -> None:
    new = getattr(request.state, "new_csrf", None)
    if new:
        settings: Settings = request.app.state.settings
        response.set_cookie(
            csrf_cookie_name(settings), new, httponly=True, samesite="strict", path="/"
        )
