"""Request guards and response headers (docs/API.md, SECURITY_PRIVACY.md, PLAN_REVIEW D11).

- Host allow-list with the port (DNS-rebinding guard for a loopback app).
- A body cap enforced while the ASGI body streams in, before any form parsing.
- The full header set on every response, static files and errors included; no-store on
  everything but static assets.
- Double-submit CSRF: an HttpOnly cookie named per port, compared in constant time with the
  X-CSRF-Token header or the csrf_token form field on every non-GET request.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import HTTPException, Request

from munim_web.settings import Settings

__all__ = ["SecurityMiddleware", "csrf_cookie_name", "csrf_protect", "csrf_token"]

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
HEADERS = [
    (b"content-security-policy", CSP.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"x-frame-options", b"DENY"),
]
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Room for the multipart envelope and the other form fields around a 15 MB file.
ENVELOPE_BYTES = 64 * 1024


class BodyTooLarge(Exception):
    pass


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.hosts = settings.hosts()
        self.limit = settings.max_upload_bytes + ENVELOPE_BYTES

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        host = headers.get(b"host", b"").decode("latin-1")
        static = str(scope.get("path", "")).startswith("/static/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                extra = list(HEADERS)
                if not static:
                    extra.append((b"cache-control", b"no-store"))
                existing = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [
                    h for h in extra if h[0] not in existing
                ]
            await send(message)

        if (
            "*" not in self.hosts
            and host not in self.hosts
            and host.split(":")[0] not in self.hosts
        ):
            await _plain(send_with_headers, 400, b"Bad Host header")
            return
        length = headers.get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.limit:
            await _plain(send_with_headers, 413, b"Request too large")
            return
        received = 0

        async def capped_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    raise BodyTooLarge
            return message

        try:
            await self.app(scope, capped_receive, send_with_headers)
        except BodyTooLarge:
            await _plain(send_with_headers, 413, b"Request too large")


async def _plain(send: Send, status: int, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def csrf_cookie_name(settings: Settings) -> str:
    return f"munim_csrf_{settings.port}"


def csrf_token(request: Request) -> str:
    """The session's token: from the cookie, or a new one the response will set."""
    settings: Settings = request.app.state.settings
    token = request.cookies.get(csrf_cookie_name(settings))
    if not token:
        token = getattr(request.state, "new_csrf", None) or secrets.token_urlsafe(32)
        request.state.new_csrf = token
    return token


async def csrf_protect(request: Request) -> None:
    """Global dependency: refuse a non-GET request whose token does not match the cookie."""
    if request.method in SAFE_METHODS:
        return
    settings: Settings = request.app.state.settings
    cookie = request.cookies.get(csrf_cookie_name(settings), "")
    sent = request.headers.get("x-csrf-token", "")
    if not sent:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
            form = await request.form()
            value = form.get("csrf_token")
            sent = value if isinstance(value, str) else ""
    if not cookie or not sent or not secrets.compare_digest(cookie, sent):
        raise HTTPException(status_code=403, detail="error.csrf")
