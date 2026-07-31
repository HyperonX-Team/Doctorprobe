"""Structured logging and request-id middleware.

- Development: human-readable plain formatter on stdout.
- Production: JSON lines (via python-json-logger) for log aggregators.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

#: Context variable carrying the request id for the current request.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the request id for the current request (or "-" outside one)."""
    return request_id_var.get()


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter that flattens the message into a `message` field."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["message"] = record.getMessage()
        log_record["level"] = record.levelname


def setup_logging() -> None:
    """Configure root logging once.

    Safe to call multiple times; handlers are only added when absent.
    """
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL.upper())

    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    if settings.ENV == "production":
        handler.setFormatter(
            CustomJsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        )
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
    root.addHandler(handler)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a unique request id and log an access line per request."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        logger = logging.getLogger("access")

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        finally:
            request_id_var.reset(token)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
