"""App factory and entry point (`munim`, `make run`)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from ulid import ULID

from munim_web import __version__
from munim_web.db import Database
from munim_web.routes import api, pages
from munim_web.security import SecurityMiddleware, csrf_protect
from munim_web.services.papers import PaperService
from munim_web.settings import Settings, get_settings
from munim_web.web import render

HERE = Path(__file__).resolve().parent
log = structlog.get_logger("munim")


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


def create_app(settings: Settings | None = None) -> SecurityMiddleware:
    settings = settings or get_settings()
    settings.uploads.mkdir(parents=True, exist_ok=True)
    db = Database.open(settings.db_path)
    db.seed_bank_rates(settings.rules_dir)
    stuck = db.fail_stuck_reads()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if stuck:
            log.info("startup.failed_stuck_reads", count=stuck)
        yield
        await app.state.papers.wait_idle()
        db.close()

    app = FastAPI(
        title="Munim",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
        dependencies=[Depends(csrf_protect)],
    )
    app.state.settings = settings
    app.state.db = db
    app.state.papers = PaperService(db, settings)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.include_router(pages.router)
    app.include_router(api.router)

    @app.get("/healthz")
    async def healthz() -> dict[str, object]:
        choice = app.state.papers.choice()
        return {"status": "ok", "version": __version__, "provider": choice.name}

    async def error_page(request: Request, status: int, key: str) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                {"type": "about:blank", "title": key, "status": status, "message_key": key},
                status_code=status,
                media_type="application/problem+json",
            )
        ref = str(ULID())[-8:]
        return render(request, "error.html", status_code=status, message_key=key, ref=ref)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> Response:
        detail = exc.detail
        if isinstance(detail, dict):
            return JSONResponse(
                detail, status_code=exc.status_code, media_type="application/problem+json"
            )
        key = detail if isinstance(detail, str) and "." in detail else "error.notfound"
        if exc.status_code == 405:
            key = "error.notfound"
        return await error_page(request, exc.status_code, key)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> Response:
        return await error_page(request, 422, "error.generic")

    @app.exception_handler(Exception)
    async def crash(request: Request, exc: Exception) -> Response:
        log.error("request.failed", path=request.url.path, error=type(exc).__name__)
        return await error_page(request, 500, "error.generic")

    configure_logging()
    return SecurityMiddleware(app, settings)


def run() -> None:
    settings = get_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="warning")


if __name__ == "__main__":
    run()
