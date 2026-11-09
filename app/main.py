import asyncio
import importlib
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.ratelimit import SlidingWindowLimiter

log = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
RETENTION_INTERVAL_SECONDS = 3600

# (module name under app/routes, URL prefix). Each module must expose `router`.
ROUTE_MODULES = [
    ("ws", ""),
    ("events", "/api"),
    ("alerts", "/api"),
    ("stats", "/api"),
]


def error_response(status: int, code: str, detail, headers=None) -> JSONResponse:
    """Every error the API returns has this shape: {"error": ..., "detail": ...}."""
    return JSONResponse(
        content={"error": code, "detail": detail},
        status_code=status,
        headers=headers,
    )


async def _retention_loop(db, retention_days: int) -> None:
    from app import storage  # imported here until storage is needed at module level

    while True:
        try:
            removed = await run_in_threadpool(storage.purge_old_events, db, retention_days)
            if removed:
                log.info("Retention removed %d old events", removed)
        except Exception:
            log.exception("Retention job failed; will retry")
        await asyncio.sleep(RETENTION_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import open_database  # imported here so main.py loads without db.py

    settings = get_settings()
    db = open_database(settings.database_path)
    app.state.db = db
    app.state.ingest_limiter = SlidingWindowLimiter(
        settings.ingest_rate_limit, settings.ingest_rate_window_seconds
    )
    retention = asyncio.create_task(_retention_loop(db, settings.event_retention_days))
    try:
        yield
    finally:
        retention.cancel()
        with suppress(asyncio.CancelledError):
            await retention
        db.close()


def _include_routes(app: FastAPI) -> None:
    for name, prefix in ROUTE_MODULES:
        try:
            module = importlib.import_module(f"app.routes.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.routes.{name}":
                log.warning("Route module app.routes.%s not found; skipping", name)
                continue
            raise  # a missing dependency inside a route file is a real error
        router = getattr(module, "router", None)
        if router is None:
            log.warning("app.routes.%s has no `router`; skipping", name)
            continue
        app.include_router(router, prefix=prefix)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CYBER-MI6 API",
        version="1.0.0",
        description="Event ingestion, alerts, and live dashboard feed.",
        lifespan=lifespan,
    )

    if settings.origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.origins_list,
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type", "X-API-Key"],
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return error_response(422, "validation_error", errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        return error_response(exc.status_code, f"http_{exc.status_code}", exc.detail, exc.headers)

    _include_routes(app)

    # Mounted last, so static files can't shadow API routes.
    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

    return app


app = create_app()