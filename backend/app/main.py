"""Doctordrobe API application factory and entrypoint.

Endpoints live under ``/api``; ``/health`` is used by orchestrator
healthchecks. All responses use the consistent error envelope
``{"detail": "message"}``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import checkups, devices, shares, users
from app.core.config import get_settings
from app.core.logging import RequestContextMiddleware, setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: logging is configured on startup."""
    setup_logging()
    logger.info("startup complete (env=%s)", get_settings().ENV)
    yield
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description=(
            "Home health analyzer API. Produces encrypted biomarker "
            "reports from physical device readings."
        ),
        lifespan=lifespan,
    )

    # CORS — origins come from the environment (never a hardcoded list).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Never leak internals: log and return a generic 500 envelope."""
        logger.exception(
            "unhandled error",
            extra={
                "request_id": request.headers.get("X-Request-ID"),
                "path": request.url.path,
                "error": exc.__class__.__name__,
            },
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        """Liveness probe for orchestrators and load balancers."""
        return {"status": "ok"}

    app.include_router(users.router)
    app.include_router(checkups.router)
    app.include_router(devices.router)
    app.include_router(shares.router)

    return app


app = create_app()
